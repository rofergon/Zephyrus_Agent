# Integración de WebSocket con aiohttp para Railway

Este documento explica cómo hemos integrado nuestro servidor WebSocket con aiohttp para resolver problemas de despliegue en Railway.

## Problema

Railway requiere un servidor HTTP para realizar healthchecks, pero nuestra aplicación era originalmente un servidor WebSocket puro. Al intentar ejecutar ambos servidores en el mismo puerto, obtuvimos un error:

```
Error starting WebSocket server: [Errno 98] error while attempting to bind on address ('0.0.0.0', 8080): [errno 98] address already in use
```

## Solución: Integración con aiohttp

En lugar de ejecutar dos servidores separados, hemos integrado el servidor WebSocket dentro de una aplicación aiohttp:

```python
# Creamos la aplicación aiohttp
app = web.Application()

# Añadimos rutas para el healthcheck
app.router.add_get('/', handle_healthcheck)
app.router.add_get('/health', handle_healthcheck)

# Creamos una instancia del WebSocketServer
ws_server = WebSocketServer(agent_manager)

# Añadimos un manejador para las conexiones WebSocket
async def handle_websocket(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    # Registrar el websocket
    await ws_server.register(ws)
    
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                await ws_server.handle_message(ws, msg.data)
            elif msg.type == web.WSMsgType.ERROR:
                print(f'WebSocket connection closed with exception {ws.exception()}')
    finally:
        await ws_server.unregister(ws)
        
    return ws

# Añadimos la ruta WebSocket
app.router.add_get('/ws/agent/{agent_id}', handle_websocket)
```

## Cómo funciona

### 1. Manejador de HTTP para healthchecks

```python
async def handle_healthcheck(request):
    return web.Response(text="OK", status=200)
```

Este manejador responde a las solicitudes HTTP a '/' y '/health' con un simple "OK", permitiendo que Railway verifique que la aplicación está funcionando correctamente.

### 2. Manejador de WebSocket

El manejador de WebSocket realiza las siguientes acciones:
1. Crea un objeto `WebSocketResponse` para manejar la comunicación
2. Registra la conexión con nuestro `WebSocketServer` existente
3. Procesa los mensajes recibidos del cliente y los pasa a nuestro `handle_message` existente
4. Desregistra la conexión cuando se cierra

### 3. Estructura de rutas

- **Rutas HTTP**: '/' y '/health' para los healthchecks
- **Ruta WebSocket**: '/ws/agent/{agent_id}' para las conexiones WebSocket

## Adaptaciones necesarias

Para que esta integración funcione, hemos tenido que adaptar cómo interactuamos con las conexiones WebSocket:

1. **Compatibilidad con aiohttp**: Ahora usamos objetos `WebSocketResponse` de aiohttp en lugar de objetos `WebSocketServerProtocol` de websockets
2. **Manejo de mensajes**: Procesamos los mensajes dentro del handler de aiohttp
3. **Uso del parámetro agent_id**: Extraemos el ID del agente directamente de la URL

## Beneficios

Esta integración nos proporciona varias ventajas:

1. **Un solo servidor**: Eliminamos el conflicto de puertos
2. **Healthchecks funcionales**: Railway puede verificar correctamente que nuestra aplicación está viva
3. **Integración limpia**: No necesitamos hilos separados ni procesos adicionales

## Actualización del frontend

Si estabas conectándote al servidor WebSocket usando una URL como:

```
wss://zephyrusagent-production.up.railway.app/ws/agent/TU_ID_DE_AGENTE
```

Esa URL seguirá funcionando con esta nueva implementación, no es necesario cambiar nada en el frontend.

## Referencias

- [Documentación de WebSockets en aiohttp](https://docs.aiohttp.org/en/stable/web_quickstart.html#websockets)
- [Guía de WebSockets en Railway](https://docs.railway.app/guides/websockets) 