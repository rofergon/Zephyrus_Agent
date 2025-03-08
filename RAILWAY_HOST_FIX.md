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

## La solución implementada

Hemos realizado las siguientes modificaciones para solucionar ambos problemas:

### 1. Script de patch con servidor HTTP (src/railway_patch.py)

- Fuerza las variables de entorno correctas (WS_HOST=0.0.0.0)
- Implementa un servidor HTTP simple usando aiohttp para responder a los healthchecks
- Ejecuta el servidor HTTP en un hilo separado para no interferir con el WebSocket
- Inicia la aplicación principal en el hilo principal

### 2. Modificación en WebSocketServer

- Detecta automáticamente si estamos en Railway
- Fuerza el host a 0.0.0.0 en entornos Railway
- Añade logging extensivo para diagnóstico

### 3. Modificación en el servicio de ejecución de agentes

- Aplica la misma lógica para forzar 0.0.0.0 en Railway

### 4. Configuración de Railway actualizada

- Actualizado railway.toml y railway.json para usar el script de inicio correcto

## Cómo verificar que funciona

Después del despliegue, busca en los logs estas líneas:

```
[RAILWAY PATCH] Forzando WS_HOST=0.0.0.0 y WS_PORT=8080
[RAILWAY HEALTHCHECK] Iniciando servidor HTTP para healthcheck en http://0.0.0.0:8080
[RAILWAY PATCH] Servidor HTTP para healthcheck iniciado en un hilo separado
[RAILWAY PATCH] Iniciando aplicación principal...
```

Y luego:
```
Detectado entorno Railway, forzando host a 0.0.0.0
INICIANDO EN: ws://0.0.0.0:8080
WebSocket server started on ws://0.0.0.0:8080
```

## Otros posibles problemas

Si después de estos cambios sigues teniendo problemas, considera:

1. **Conflicto de puertos**: 
   - El servidor HTTP y WebSocket ahora comparten el mismo puerto
   - Esto debería funcionar correctamente, pero podría causar problemas en algunos casos

2. **Problemas de arranque**:
   - Si la aplicación no inicia correctamente, revisa los logs para más detalles
   - Railway puede terminar el proceso si tarda demasiado en iniciar

3. **Configuración de rutas WebSocket en Railway**:
   - Asegúrate de que las rutas en railway.toml son correctas

## Recursos útiles

- [Documentación sobre healthchecks en Railway](https://docs.railway.app/deploy/deployments#healthchecks)
- [Buenas prácticas para WebSockets en contenedores](https://devcenter.heroku.com/articles/websockets#websockets-with-node-js)
- [FAQ sobre redes en Railway](https://docs.railway.app/faq) 