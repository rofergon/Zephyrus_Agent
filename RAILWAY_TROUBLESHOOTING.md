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
upstreamAddress: "http://[fd12:b97:efb:0:2000:7:7d7f:79f8]:8765"
```

Esto indica que Railway está intentando enrutar las solicitudes WebSocket a tu aplicación, pero el puerto específico (8765) no está disponible o no está correctamente configurado.

## La Solución (Implementada)

Hemos realizado la siguiente modificación en `src/utils/config.py`:

```python
# Antes:
WS_PORT = int(os.getenv('WS_PORT', '8765'))

# Después:
WS_PORT = int(os.getenv('PORT', os.getenv('WS_PORT', '8765')))
```

Este cambio hace que la aplicación:
1. Primero busque la variable `PORT` que Railway proporciona automáticamente
2. Si no encuentra `PORT`, utiliza el valor de `WS_PORT` 
3. Si ninguno está definido, usa el puerto predeterminado 8765

## Verificación

Después de implementar estos cambios y volver a desplegar la aplicación:

1. Verifica los logs de Railway para asegurarte de que el servidor se inicia correctamente
2. Busca un mensaje similar a: `WebSocket server started on ws://0.0.0.0:XXXX` (donde XXXX será el puerto asignado por Railway)
3. Intenta conectarte nuevamente a tu WebSocket

## Si el Problema Persiste

Si el problema persiste después de aplicar estos cambios:

1. **Verifica los logs de Railway**: Busca errores específicos durante el inicio del servidor
2. **Modifica el archivo principal**: Asegúrate de que el `Procfile` esté correctamente configurado:
   ```
   web: python src/main.py
   ```
3. **Comprueba las variables de entorno en Railway**: Asegúrate de que están correctamente configuradas
4. **Fuerza un reinicio**: A veces, reiniciar el servicio desde el dashboard de Railway puede resolver problemas de inicialización

## Otros Archivos Relevantes

Si necesitas hacer más depuración, estos son los archivos principales relacionados con el WebSocket:

1. `src/utils/config.py` - Configuración de host y puerto
2. `src/websocket/websocket_server.py` - Implementación del servidor WebSocket
3. `src/main.py` - Punto de entrada principal que inicia el servidor

## Recursos Adicionales

- [Guía de WebSockets en Railway](https://docs.railway.app/guides/websockets)
- [Solución de problemas en Railway](https://docs.railway.app/troubleshoot/railway-up)
- [Foro de Railway](https://railway.app/community) 