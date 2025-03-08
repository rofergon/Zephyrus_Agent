#!/usr/bin/env python
"""
Script de patch para Railway que integra un servidor HTTP para healthcheck
junto con el servidor WebSocket en la misma aplicación.
"""

import os
import sys
import asyncio
import threading
import logging
import json
from aiohttp import web

# Forzar las variables críticas antes de importar el resto
os.environ['WS_HOST'] = '0.0.0.0'
os.environ['WS_PORT'] = os.environ.get('PORT', '8080')

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('railway_patch')

# Imprimir confirmación
print(f"[RAILWAY PATCH] Forzando WS_HOST=0.0.0.0 y WS_PORT={os.environ.get('PORT', '8080')}")

# Función para el healthcheck HTTP
async def handle_healthcheck(request):
    return web.Response(text="OK", status=200)

# Clase adaptadora para hacer compatible WebSocketResponse de aiohttp con websockets
class WebSocketAdapter:
    def __init__(self, ws_response):
        self._ws = ws_response
        
    async def send(self, data):
        """
        Adapta el método send() de websockets a send_str() de aiohttp
        """
        if isinstance(data, str):
            return await self._ws.send_str(data)
        elif isinstance(data, dict):
            return await self._ws.send_json(data)
        elif isinstance(data, bytes):
            return await self._ws.send_bytes(data)
        else:
            # Si es otro tipo, intentamos convertirlo a string
            return await self._ws.send_str(str(data))
            
    # Implementar otros métodos que pueda necesitar
    async def close(self, code=1000, reason=""):
        return await self._ws.close(code=code, message=reason)
        
    # Añadir cualquier otro método necesario para la compatibilidad

# Integramos ambos servidores en la misma aplicación
async def start_integrated_server():
    # Importamos los módulos necesarios aquí para no interferir con las configuraciones
    sys.path.insert(0, '.')
    
    # Creamos la aplicación aiohttp
    app = web.Application()
    
    # Añadimos rutas para el healthcheck
    app.router.add_get('/', handle_healthcheck)
    app.router.add_get('/health', handle_healthcheck)
    
    # Obtenemos el puerto de Railway
    port = int(os.environ.get('PORT', '8080'))
    
    # Ahora importamos e iniciamos el AgentManager desde nuestra aplicación original
    print("[RAILWAY PATCH] Iniciando AgentManager...")
    from src.core.agent_manager import AgentManager
    
    # Creamos el AgentManager
    agent_manager = AgentManager()
    
    # En lugar de iniciar el WebSocketServer directamente, creamos un manejador
    # que use el contexto de nuestra aplicación aiohttp
    from src.websocket.websocket_server import WebSocketServer
    
    # Creamos la instancia del servidor pero no la iniciamos
    ws_server = WebSocketServer(agent_manager)
    
    # Añadimos la ruta WebSocket a nuestra aplicación aiohttp
    # Esto requiere modificar la lógica para integrarse con aiohttp
    async def handle_websocket(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        # Creamos un adaptador para hacer compatible la interfaz
        adapter = WebSocketAdapter(ws)
        
        # Registrar el websocket usando el adaptador
        await ws_server.register(adapter)
        
        # Extraer el agent_id de la URL
        agent_id = request.match_info.get('agent_id', 'unknown')
        print(f"WebSocket connection established for agent: {agent_id}")
        
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
    
    # Añadimos la ruta WebSocket
    app.router.add_get('/ws/agent/{agent_id}', handle_websocket)
    
    # Iniciamos el servidor
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    print(f"[RAILWAY INTEGRATED SERVER] Iniciando servidor HTTP+WebSocket en http://0.0.0.0:{port}")
    await site.start()
    
    # Mantener el servidor en ejecución
    # Creamos un bucle infinito para mantener el servidor activo
    while True:
        await asyncio.sleep(3600)  # Comprueba cada hora

# Función principal
if __name__ == "__main__":
    try:
        # Ejecutamos el servidor integrado
        asyncio.run(start_integrated_server())
    except Exception as e:
        print(f"[ERROR] Error iniciando el servidor integrado: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 