# Solucionando el problema de host en Railway (localhost vs 0.0.0.0)

## El problema

Los logs muestran el siguiente problema:

```
Iniciando servidor WebSocket en host=localhost puerto=8080
WebSocket server started on ws://localhost:8080
```

Pero Railway intenta conectar a:
```
upstreamAddress: "http://[fd12:b97:efb:0:2000:41:2c46:de16]:8080"
responseDetails: "failed to forward request to upstream: connection refused"
```

## La causa raíz

El problema es que Railway necesita que tu aplicación escuche en todas las interfaces de red (`0.0.0.0`) y no solo en `localhost` (127.0.0.1), que solo acepta conexiones desde la misma máquina.

## La solución implementada

Hemos realizado las siguientes modificaciones para solucionar este problema:

### 1. Script de inicio específico para Railway (src/railway_starter.py)

- Crea un archivo de patch (src/railway_patch.py) que fuerza las variables de entorno correctas
- Asegura que WS_HOST sea siempre 0.0.0.0 en Railway

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
Detectado entorno Railway, forzando host a 0.0.0.0
INICIANDO EN: ws://0.0.0.0:8080 - Asegúrate de que esto sea 0.0.0.0 en Railway
WebSocket server started on ws://0.0.0.0:8080
```

## Otros posibles problemas

Si después de estos cambios sigues teniendo problemas, considera:

1. **Problemas de red interna en Railway**: 
   - Railway usa una red interna con direcciones IPv6 como se ve en el error
   - Puede ser necesario contactar al soporte de Railway

2. **Configuración de rutas WebSocket en Railway**:
   - Asegúrate de que las rutas en railway.toml son correctas

3. **Firewall o restricciones de red**:
   - Railway puede tener restricciones adicionales de red

## Recursos útiles

- [Buenas prácticas para WebSockets en contenedores](https://devcenter.heroku.com/articles/websockets#websockets-with-node-js)
- [FAQ sobre redes en Railway](https://docs.railway.app/faq)
- [Problemas comunes en Railway](https://docs.railway.app/troubleshoot/railway-up) 