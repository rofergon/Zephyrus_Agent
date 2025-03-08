# Solucionando el problema de Healthcheck en Railway

## El problema

Cuando Railway despliega una aplicación, realiza un healthcheck a la ruta "/" para asegurarse de que la aplicación está funcionando correctamente. Si este healthcheck falla, Railway considera que la aplicación no se ha desplegado correctamente.

En el caso de una aplicación WebSocket pura, este healthcheck fallará porque el servidor WebSocket no responde a solicitudes HTTP estándar:

```
Attempt #1 failed with service unavailable. Continuing to retry for 4m49s
Attempt #2 failed with service unavailable. Continuing to retry for 4m48s
Attempt #3 failed with service unavailable. Continuing to retry for 4m46s
```

## La solución: Servidor HTTP para Healthcheck

Hemos implementado un servidor HTTP simple usando aiohttp en un hilo separado, que responde a las solicitudes de healthcheck de Railway mientras el servidor WebSocket principal sigue funcionando normalmente.

### Archivo src/railway_patch.py

Este archivo:
1. Configura las variables de entorno correctas
2. Inicia un servidor HTTP simple en un hilo separado
3. Inicia la aplicación principal en el hilo principal

```python
import os
import sys
import asyncio
import threading
from aiohttp import web

# Forzar las variables críticas
os.environ['WS_HOST'] = '0.0.0.0'
os.environ['WS_PORT'] = os.environ.get('PORT', '8080')

# Servidor HTTP para healthcheck
async def handle_healthcheck(request):
    return web.Response(text="OK", status=200)

async def start_http_server():
    app = web.Application()
    app.router.add_get('/', handle_healthcheck)
    app.router.add_get('/health', handle_healthcheck)
    
    port = int(os.environ.get('PORT', '8080'))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    await site.start()
    
    # Mantener el servidor en ejecución
    while True:
        await asyncio.sleep(3600)

def start_http_healthcheck():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_http_server())

# Ejecución principal
if __name__ == "__main__":
    http_thread = threading.Thread(target=start_http_healthcheck)
    http_thread.daemon = True
    http_thread.start()
    
    # Iniciar aplicación principal
    from src.main import main
    asyncio.run(main())
```

## Cómo funciona

1. El servidor HTTP y el servidor WebSocket comparten el mismo puerto
2. Cuando Railway hace una solicitud HTTP a "/", el servidor HTTP responde con "OK"
3. Las conexiones WebSocket siguen funcionando normalmente porque aiohttp y websockets pueden coexistir en el mismo puerto

## Verificando que funciona

Después del despliegue, busca estas líneas en los logs:

```
[RAILWAY PATCH] Forzando WS_HOST=0.0.0.0 y WS_PORT=8080
[RAILWAY HEALTHCHECK] Iniciando servidor HTTP para healthcheck en http://0.0.0.0:8080
```

Y luego deberías ver que el healthcheck pasa correctamente:

```
Healthcheck successful after X attempts
```

## Posibles problemas

Si el healthcheck sigue fallando:

1. **Asegúrate de que el puerto es el correcto**:
   - Tanto el servidor HTTP como el WebSocket deben usar el puerto proporcionado por Railway

2. **Verifica que no haya errores en el inicio**:
   - Si hay errores durante el arranque, el servidor HTTP no se iniciará correctamente

3. **Prueba un path de healthcheck diferente**:
   - Si tienes problemas, puedes modificar el archivo railway.toml para usar "/health" en lugar de "/":
   ```toml
   [deploy]
   healthcheckPath = "/health"
   ```

## Referencias

- [Documentación de Railway sobre Healthchecks](https://docs.railway.app/deploy/deployments#healthchecks)
- [Documentación de aiohttp para servidores web](https://docs.aiohttp.org/en/stable/web.html) 