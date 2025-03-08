# Guía para solucionar problemas de WebSocket en Railway

## Problema de conexión rechazada (Connection Refused)

Si estás viendo un error como este:

```
responseDetails: "failed to forward request to upstream: connection refused"
upstreamAddress: "http://[fd12:b97:efb:0:2000:41:2c46:de16]:8765"
```

Significa que Railway está intentando conectar al puerto 8765 en lugar del puerto que asigna automáticamente.

## Solución completa

Hemos implementado una solución integral que consta de los siguientes componentes:

### 1. Script de inicio específico para Railway

El archivo `src/railway_starter.py` es un script especial que:
- Detecta automáticamente el puerto que Railway proporciona
- Fuerza la configuración correcta en las variables de entorno
- Inicia la aplicación con la configuración adecuada

### 2. Configuración actualizada en Procfile

El archivo `Procfile` ahora usa nuestro script de inicio:
```
web: python src/railway_starter.py
```

### 3. Configuración avanzada en railway.json y railway.toml

Estos archivos proporcionan configuración adicional a Railway sobre cómo manejar las rutas WebSocket.

## Instrucciones para implementar

1. **Asegúrate de hacer un push con todos estos cambios a tu repositorio**
2. **Fuerza un nuevo despliegue en Railway**:
   - Ve al dashboard de Railway
   - Selecciona tu proyecto
   - Ve a la pestaña "Deployments"
   - Haz clic en "Deploy now" para forzar un nuevo despliegue

3. **Verifica los logs**:
   - Después del despliegue, revisa los logs
   - Deberías ver mensajes como:
     - `Iniciando aplicación en Railway con PORT=XXXX`
     - `Variables de entorno establecidas: WS_PORT=XXXX, WS_HOST=0.0.0.0`
     - `WebSocket server started on ws://0.0.0.0:XXXX`

4. **Prueba la conexión WebSocket**:
   - Usa la URL correcta: `wss://zephyrusagent-production.up.railway.app/ws/agent/TU_ID_DE_AGENTE`

## Si el problema persiste

Si después de estos cambios sigues teniendo problemas:

1. **Verifica que no haya rutas hardcodeadas**:
   - Asegúrate de que en tu frontend no estés usando URLs con puertos fijos (como 8765)
   - Las conexiones WebSocket deberían usar la URL base sin puerto específico

2. **Intenta con una nueva aplicación en Railway**:
   - A veces, crear un nuevo proyecto en Railway puede evitar problemas de configuración previos
   - Clona tu repositorio, haz los cambios y crea un nuevo proyecto en Railway

3. **Contacta al soporte de Railway**:
   - Si el problema persiste, puede ser un problema específico de Railway
   - Comparte los logs y la configuración con el soporte

## Recursos útiles

- [Documentación de Railway sobre WebSockets](https://docs.railway.app/guides/websockets)
- [Deploy Considerations en Railway](https://docs.railway.app/deploy/deployments)
- [Foro de la comunidad de Railway](https://railway.app/community) 