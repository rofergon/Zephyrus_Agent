# Solucionando el error "connection refused" en Railway

Este documento proporciona pasos detallados para solucionar el problema específico de "connection refused" en despliegues de Railway con WebSockets.

## El Problema

El error que estás viendo:

```
requestId: "i09cXz7NQ1mjSfYuMItGWQ_28081791"
timestamp: "2025-03-08T04:14:36.843901539Z"
method: "GET"
path: "/ws/agent/aaeaf93a-b8b4-43fa-9ddf-da5fe70b11d1"
host: "zephyrusagent-production.up.railway.app"
httpStatus: 502
upstreamProto: "HTTP/1.1"
downstreamProto: "HTTP/1.1"
responseDetails: "failed to forward request to upstream: connection refused"
upstreamAddress: "http://[fd12:b97:efb:0:2000:3c:1517:a75c]:8765"
```

Esto indica que Railway está intentando enrutar las solicitudes WebSocket a tu aplicación, pero el puerto específico (8765) no está disponible o no está correctamente configurado.

## La Solución (Implementada)

Hemos realizado las siguientes modificaciones para solucionar este problema:

### 1. Modificación en `src/utils/config.py`:

```python
# Antes:
WS_PORT = int(os.getenv('WS_PORT', '8765'))

# Después:
WS_PORT = int(os.getenv('PORT', os.getenv('WS_PORT', '8765')))
```

### 2. Modificación en `src/websocket/websocket_server.py`:

Hemos modificado la clase WebSocketServer para obtener el puerto directamente de la variable de entorno PORT:

```python
def __init__(self, agent_manager: AgentManager):
    # Usar el WS_HOST de la configuración
    self.host = WS_HOST
    
    # Obtener puerto directamente de la variable PORT de Railway si está disponible
    # o usar WS_PORT de la configuración como respaldo
    railway_port = os.environ.get('PORT')
    if railway_port:
        self.port = int(railway_port)
        logger.info(f"Usando el puerto de Railway: {self.port}")
    else:
        self.port = WS_PORT
        logger.info(f"Usando el puerto de configuración: {self.port}")
```

### 3. Modificación en `src/services/agent_execution_service.py`:

También hemos actualizado el servicio de ejecución de agentes para usar el puerto correcto:

```python
# Obtener el puerto directamente de la variable PORT de Railway si está disponible
port = int(os.environ.get('PORT', WS_PORT))
host = os.environ.get('WS_HOST', WS_HOST)
```

## Verificación

Después de implementar estos cambios y volver a desplegar la aplicación:

1. Verifica los logs de Railway para asegurarte de que el servidor se inicia correctamente
2. Busca mensajes como:
   - `Usando el puerto de Railway: XXXX`
   - `WebSocket server started on ws://0.0.0.0:XXXX`
   - `Variables de entorno: PORT=XXXX, WS_PORT=YYYY`
3. Intenta conectarte nuevamente a tu WebSocket

## Si el Problema Persiste

Si el problema persiste después de aplicar estos cambios:

1. **Fuerza un reinicio completo de Railway**:
   - Ve al dashboard de Railway
   - Selecciona tu aplicación
   - Navega a la sección "Deployments"
   - Haz clic en "Redeploy" para forzar un nuevo despliegue completo

2. **Verifica que los logs muestren el puerto correcto**:
   - Deberías ver un mensaje como "Usando el puerto de Railway: XXXX" en los logs
   - Confirma que el puerto que muestra coincide con el que Railway está intentando usar

3. **Prueba con una configuración manual del dominio WebSocket**:
   - En tu cliente WebSocket, asegúrate de estar usando la URL correcta
   - El formato correcto sería: `wss://zephyrusagent-production.up.railway.app/ws/agent/TU_ID_DE_AGENTE`

## Otros Archivos Relevantes

Si necesitas hacer más depuración, estos son los archivos principales relacionados con el WebSocket:

1. `src/utils/config.py` - Configuración de host y puerto
2. `src/websocket/websocket_server.py` - Implementación del servidor WebSocket
3. `src/services/agent_execution_service.py` - Servicio de ejecución de agentes
4. `src/main.py` - Punto de entrada principal que inicia el servidor

## Recursos Adicionales

- [Guía de WebSockets en Railway](https://docs.railway.app/guides/websockets)
- [Solución de problemas en Railway](https://docs.railway.app/troubleshoot/railway-up)
- [Foro de Railway](https://railway.app/community) 