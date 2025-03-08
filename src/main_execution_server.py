#!/usr/bin/env python
import asyncio
import logging
import os
import signal
import sys

# Asegurar que podemos importar módulos desde el directorio raíz
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.agent_execution_service import start_server
from src.utils.config import WS_HOST, WS_PORT, LOG_LEVEL
from src.utils.logger import setup_logger

# Configurar logger principal
logger = setup_logger("execution_server", level=LOG_LEVEL)

# Variable para mantener estado de ejecución
running = True

def handle_exit_signal(signum, frame):
    """Maneja señales de finalización (SIGINT, SIGTERM)"""
    global running
    signal_name = signal.Signals(signum).name
    logger.info(f"Recibida señal {signal_name}, iniciando apagado del servidor...")
    running = False
    
    # Darse un tiempo para cerrar correctamente y luego salir
    if asyncio.get_event_loop().is_running():
        logger.info("Cerrando el bucle de eventos...")
        asyncio.get_event_loop().stop()

async def main():
    """Función principal para iniciar el servidor con manejo de interrupciones"""
    try:
        # Registrar manejadores de señales
        signal.signal(signal.SIGINT, handle_exit_signal)
        signal.signal(signal.SIGTERM, handle_exit_signal)
        
        logger.info(f"Iniciando servidor de ejecución de agentes en {WS_HOST}:{WS_PORT}")
        
        # Iniciar el servidor WebSocket
        server_task = asyncio.create_task(start_server())
        
        # Esperar a que termine, ya sea por error o por señal
        await server_task
        
    except KeyboardInterrupt:
        logger.info("Interrupción de teclado recibida, cerrando servidor...")
    except asyncio.CancelledError:
        logger.info("Tarea de servidor cancelada")
    except Exception as e:
        logger.error(f"Error fatal en el servidor: {str(e)}", exc_info=True)
        return 1
    finally:
        logger.info("Servidor de ejecución de agentes finalizado")
    
    return 0

if __name__ == "__main__":
    logger.info("=== INICIANDO SERVIDOR DE EJECUCIÓN DE AGENTES ===")
    logger.info(f"Host: {WS_HOST}, Puerto: {WS_PORT}")
    
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Interrupción recibida durante el inicio, abortando...")
        sys.exit(130)  # 128 + SIGINT(2)
    except Exception as e:
        logger.critical(f"Error fatal durante el inicio: {str(e)}", exc_info=True)
        sys.exit(1) 