import asyncio
import signal
from src.core.agent_manager import AgentManager
from src.utils.logger import setup_logger
from src.websocket.websocket_server import WebSocketServer

logger = setup_logger(__name__)

async def main():
    """
    Punto de entrada principal de la aplicación
    """
    # Crear el manager de agentes
    agent_manager = AgentManager()

    # Crear y configurar el servidor WebSocket
    websocket_server = WebSocketServer(agent_manager)

    # Manejar señales de terminación
    def handle_shutdown(signum, frame):
        logger.info("Shutting down...")
        asyncio.create_task(cleanup(agent_manager, websocket_server))

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        # Iniciar el servidor WebSocket
        await websocket_server.start()
        
        # Mantener la aplicación corriendo
        while True:
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Error in main loop: {str(e)}")
        await cleanup(agent_manager, websocket_server)

async def cleanup(agent_manager: AgentManager, websocket_server: WebSocketServer):
    """
    Limpia los recursos antes de terminar
    """
    try:
        await agent_manager.cleanup()
        await websocket_server.stop()
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
    finally:
        asyncio.get_event_loop().stop()

if __name__ == "__main__":
    asyncio.run(main()) 