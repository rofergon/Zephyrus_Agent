# Solucionando problemas de Railway: Host y Healthcheck

## Problema 1: Host incorrecto (localhost vs 0.0.0.0)

Los logs mostraban el siguiente problema:

```
Iniciando servidor WebSocket en host=localhost puerto=8080
WebSocket server started on ws://localhost:8080
```

Pero Railway intentaba conectar a:
```
upstreamAddress: "http://[fd12:b97:efb:0:2000:41:2c46:de16]:8080"
responseDetails: "failed to forward request to upstream: connection refused"
```

### Causa raíz
El problema es que Railway necesita que tu aplicación escuche en todas las interfaces de red (`0.0.0.0`) y no solo en `localhost` (127.0.0.1), que solo acepta conexiones desde la misma máquina.

## Problema 2: Fallos en el Healthcheck

El segundo problema identificado es que Railway realiza un healthcheck a la ruta "/" y espera una respuesta HTTP, pero nuestra aplicación es solo un servidor WebSocket y no responde a solicitudes HTTP estándar:

```
Attempt #1 failed with service unavailable. Continuing to retry for 4m49s
Attempt #2 failed with service unavailable. Continuing to retry for 4m48s
Attempt #3 failed with service unavailable. Continuing to retry for 4m46s
```

### Causa raíz
Railway espera que tu aplicación responda a solicitudes HTTP en la ruta "/" para verificar que está funcionando correctamente, pero los servidores WebSocket puros no suelen responder a estas solicitudes.

## Problema 3: Conflicto de puertos

Después de implementar una solución inicial, nos encontramos con un nuevo problema:

```
Error starting WebSocket server: [Errno 98] error while attempting to bind on address ('0.0.0.0', 8080): [errno 98] address already in use
```

### Causa raíz
Nuestro enfoque anterior ejecutaba el servidor HTTP y el servidor WebSocket como procesos separados, ambos intentando usar el mismo puerto (8080), lo que causaba un conflicto.

## La solución implementada

Hemos realizado las siguientes modificaciones para solucionar todos estos problemas:

### 1. Servidor integrado HTTP+WebSocket (src/railway_patch.py)

En lugar de ejecutar dos servidores separados, ahora:
- Implementamos un único servidor aiohttp que maneja tanto HTTP como WebSocket
- Las rutas HTTP ('/' y '/health') responden a los healthchecks de Railway
- La ruta WebSocket ('/ws/agent/{agent_id}') maneja las conexiones WebSocket
- Todo funciona en el mismo puerto, sin conflictos

### 2. Modificación en cómo se inicia la aplicación

- Ahora usamos la aplicación aiohttp como punto de entrada principal
- Inicializamos el AgentManager dentro de esta aplicación
- Integramos el WebSocketServer con aiohttp en lugar de ejecutarlo por separado

### 3. Configuración de Railway actualizada

- Configuración para usar el script de inicio correcto

## Cómo verificar que funciona

Después del despliegue, busca en los logs estas líneas:

```
[RAILWAY PATCH] Forzando WS_HOST=0.0.0.0 y WS_PORT=8080
[RAILWAY INTEGRATED SERVER] Iniciando servidor HTTP+WebSocket en http://0.0.0.0:8080
```

Y deberías ver que el healthcheck pasa correctamente.

## Cómo funciona la integración

1. **Un único servidor**:
   - En lugar de ejecutar dos servidores separados que compiten por el mismo puerto, ahora usamos un solo servidor aiohttp
   - Este servidor maneja tanto las solicitudes HTTP como las conexiones WebSocket

2. **Rutas diferenciadas**:
   - Rutas HTTP: '/' y '/health' para el healthcheck
   - Ruta WebSocket: '/ws/agent/{agent_id}' para las conexiones WebSocket

3. **Sin conflictos de puerto**:
   - Aiohttp puede manejar ambos protocolos (HTTP y WebSocket) en el mismo puerto
   - Railway hace el healthcheck HTTP a '/' y los clientes se conectan al WebSocket en '/ws/agent/{agent_id}'

## Recursos útiles

- [Documentación sobre healthchecks en Railway](https://docs.railway.app/deploy/deployments#healthchecks)
- [Soporte de WebSocket en aiohttp](https://docs.aiohttp.org/en/stable/web_quickstart.html#websockets)
- [FAQ sobre redes en Railway](https://docs.railway.app/faq) 