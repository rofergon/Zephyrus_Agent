#!/usr/bin/env python
"""
Script de patch para Railway que fuerza las variables correctas y añade un servidor HTTP
para el healthcheck que Railway requiere.
"""

import os
import sys
import asyncio
import threading
from aiohttp import web

# Forzar las variables críticas antes de importar el resto
os.environ['WS_HOST'] = '0.0.0.0'
os.environ['WS_PORT'] = os.environ.get('PORT', '8080')

# Imprimir confirmación
print(f"[RAILWAY PATCH] Forzando WS_HOST=0.0.0.0 y WS_PORT={os.environ.get('PORT', '8080')}")

# Función para iniciar un servidor HTTP simple para el healthcheck de Railway
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
    
    print(f"[RAILWAY HEALTHCHECK] Iniciando servidor HTTP para healthcheck en http://0.0.0.0:{port}")
    await site.start()
    
    # Mantener el servidor en ejecución
    while True:
        await asyncio.sleep(3600)  # Cada hora comprobamos si debemos seguir ejecutando

def start_http_healthcheck():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_http_server())

# Ahora importar y ejecutar la aplicación principal en un hilo separado
def run_main_app():
    sys.path.insert(0, '.')
    from src.main import main
    
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"[ERROR] Error en la aplicación principal: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Iniciar el servidor HTTP para healthcheck en un hilo separado
    http_thread = threading.Thread(target=start_http_healthcheck)
    http_thread.daemon = True
    http_thread.start()
    
    print("[RAILWAY PATCH] Servidor HTTP para healthcheck iniciado en un hilo separado")
    print("[RAILWAY PATCH] Iniciando aplicación principal...")
    
    # Iniciar la aplicación principal en el hilo principal
    run_main_app() 