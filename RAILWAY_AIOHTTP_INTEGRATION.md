# Integración de HTTP y WebSocket con aiohttp para Railway

Este documento explica cómo hemos integrado un servidor HTTP y WebSocket usando aiohttp para solucionar problemas de despliegue en Railway.

## ¿Por qué aiohttp?

Elegimos aiohttp por varias razones:

1. **Soporte nativo para HTTP y WebSocket**: Permite manejar ambos protocolos desde una única aplicación
2. **Basado en asyncio**: Compatible con el enfoque asíncrono de nuestra aplicación existente
3. **Ligero y eficiente**: Consumo de recursos reducido
4. **Amplia adopción**: Biblioteca madura y bien documentada

## Estructura de la integración

La integración se realiza en tres capas:

1. **Capa de servidor**: Aplicación aiohttp que escucha en el puerto asignado por Railway
2. **Capa de adaptación**: WebSocketAdapter que hace compatible aiohttp con el código existente
3. **Capa de lógica**: Código original de WebSocketServer, AgentManager, etc.

## Código de la integración

### 1. Creación de la aplicación

```python
# Creamos la aplicación aiohttp
app = web.Application()

# Añadimos rutas para el healthcheck
app.router.add_get('/', handle_healthcheck)
app.router.add_get('/health', handle_healthcheck)

# Obtenemos el puerto de Railway
port = int(os.environ.get('PORT', '8080'))
```

### 2. Manejadores de rutas

```python
# Healthcheck para Railway
async def handle_healthcheck(request):
    return web.Response(text="OK", status=200)

# Manejador de WebSocket
async def handle_websocket(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    # Creamos un adaptador para hacer compatible la interfaz
    adapter = WebSocketAdapter(ws)
    
    # Registrar el websocket usando el adaptador
    await ws_server.register(adapter)
    
    # Extraer el agent_id de la URL
    agent_id = request.match_info.get('agent_id', 'unknown')
    
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                # Usar el adaptador para manejar mensajes
                await ws_server.handle_message(adapter, msg.data)
            elif msg.type == web.WSMsgType.ERROR:
                print(f'WebSocket connection closed with exception {ws.exception()}')
    finally:
        # Usamos el adaptador para desregistrar
        await ws_server.unregister(adapter)
        
    return ws
```

### 3. Inicialización y ejecución

```python
# Añadimos la ruta WebSocket
app.router.add_get('/ws/agent/{agent_id}', handle_websocket)

# Iniciamos el servidor
runner = web.AppRunner(app)
await runner.setup()
site = web.TCPSite(runner, '0.0.0.0', port)

print(f"[RAILWAY INTEGRATED SERVER] Iniciando servidor HTTP+WebSocket en http://0.0.0.0:{port}")
await site.start()

# Mantener el servidor en ejecución
while True:
    await asyncio.sleep(3600)
```

## Ventajas de este enfoque

1. **Un solo servidor**: Elimina el conflicto de puertos
2. **Healthchecks funcionales**: Railway puede verificar que la aplicación está viva
3. **Rutas diferenciadas**: 
   - '/' y '/health' para healthchecks
   - '/ws/agent/{agent_id}' para WebSockets
4. **Sin modificaciones en el código original**: Gracias al adaptador

## Consideraciones importantes

### URL para conectarse

```
wss://zephyrusagent-production.up.railway.app/ws/agent/TU_ID_DE_AGENTE
```

Puntos importantes:
- Usar `wss://` (WebSocket Seguro) en producción
- No especificar puerto en la URL

### Mensajes y formato de datos

El adaptador WebSocket maneja automáticamente la conversión de formatos:
- JSON para estructuras de datos
- Texto para mensajes simples

## Referencias

- [Documentación de aiohttp sobre WebSockets](https://docs.aiohttp.org/en/stable/web_quickstart.html#websockets)
- [Guía de Railway sobre servidores web](https://docs.railway.app/deploy/exposing-your-app)
- [FAQ de Railway sobre puertos](https://docs.railway.app/reference/public-networking#port-selection) 