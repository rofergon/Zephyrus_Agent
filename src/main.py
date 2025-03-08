import os
import sys
import asyncio
import signal
import platform
from asyncio import AbstractEventLoop

# Agregar el directorio raíz al PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.agent_manager import AgentManager
from src.utils.logger import setup_logger
from src.websocket.websocket_server import WebSocketServer

logger = setup_logger(__name__)

# Variable global para controlar el estado de la aplicación
should_exit = False

async def shutdown(websocket_server, agent_manager, loop):
    """
    Realiza un cierre limpio de la aplicación
    """
    try:
        # Detener el servidor WebSocket
        if websocket_server:
            await websocket_server.stop()
            logger.info("WebSocket server stopped")

        # Detener todos los agentes
        if agent_manager:
            for agent_id in agent_manager.agents.keys():
                agent_manager.stop_agent(agent_id)
            logger.info("All agents stopped")

        # Cancelar todas las tareas pendientes
        tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(f"Cancelled {len(tasks)} pending tasks")

    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}", exc_info=True)
    finally:
        logger.info("Shutdown complete")
        # Señalizar que la aplicación debe terminar
        global should_exit
        should_exit = True

def handle_signal(websocket_server, agent_manager, loop):
    """
    Manejador de señales para Windows y Unix
    """
    logger.info("Shutdown signal received")
    asyncio.create_task(shutdown(websocket_server, agent_manager, loop))

async def main():
    """
    Función principal de la aplicación
    """
    try:
        # Inicializar componentes
        agent_manager = AgentManager()
        websocket_server = WebSocketServer(agent_manager)
        loop = asyncio.get_running_loop()
        
        # Configurar el manejo de señales según el sistema operativo
        if platform.system() != 'Windows':
            # En sistemas Unix/Linux
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig,
                    lambda: handle_signal(websocket_server, agent_manager, loop)
                )
        else:
            # En Windows
            signal.signal(signal.SIGINT, lambda s, f: handle_signal(
                websocket_server, agent_manager, loop))
            signal.signal(signal.SIGTERM, lambda s, f: handle_signal(
                websocket_server, agent_manager, loop))

        # Iniciar el servidor WebSocket
        server_task = asyncio.create_task(websocket_server.start())
        
        # Mantener la aplicación corriendo hasta que se señalice el cierre
        while not should_exit:
            await asyncio.sleep(1)
            
        # Esperar a que el servidor termine
        await server_task

    except asyncio.CancelledError:
        logger.info("Application shutdown initiated")
    except Exception as e:
        logger.error(f"Application error: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1) 