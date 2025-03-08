import asyncio
import websockets
import json
import sys
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('websocket_execution_client')

# URL del servidor WebSocket
WS_URL = "ws://localhost:8765"

async def trigger_agent_execution(agent_id):
    """
    Envía un mensaje WebSocket para ejecutar un agente específico
    
    Args:
        agent_id: ID del agente a ejecutar
    """
    try:
        logger.info(f"Conectando al servidor WebSocket en {WS_URL}")
        async with websockets.connect(WS_URL) as websocket:
            logger.info(f"Conexión establecida, enviando solicitud de ejecución para el agente {agent_id}")
            
            # Crear mensaje de ejecución
            message = {
                "type": "execute", 
                "agent_id": agent_id
            }
            
            # Enviar solicitud
            await websocket.send(json.dumps(message))
            logger.info("Solicitud de ejecución enviada")
            
            # Esperar y procesar respuestas
            while True:
                try:
                    response = await websocket.recv()
                    response_data = json.loads(response)
                    
                    # Mostrar respuesta formateada
                    logger.info(f"Respuesta recibida: {json.dumps(response_data, indent=2)}")
                    
                    # Si la ejecución ha completado, podemos salir
                    if (response_data.get("type") == "execution_response" and 
                        response_data.get("data", {}).get("status") == "completed"):
                        logger.info("Ejecución completada!")
                        
                        # Obtener datos de la respuesta
                        data = response_data.get("data", {})
                        
                        # Mostrar resumen
                        if data.get("success"):
                            execution_count = data.get("execution_count", 0)
                            if execution_count > 0:
                                logger.info(f"El agente ejecutó {execution_count} acciones con éxito")
                            else:
                                logger.info("El agente no ejecutó ninguna acción")
                        else:
                            logger.error(f"La ejecución falló: {data.get('error')}")
                        
                        break
                        
                except websockets.ConnectionClosed:
                    logger.warning("Conexión cerrada por el servidor")
                    break
                except Exception as e:
                    logger.error(f"Error procesando respuesta: {str(e)}")
                    break
                    
    except Exception as e:
        logger.error(f"Error de conexión: {str(e)}")

if __name__ == "__main__":
    # Obtener el agent_id como argumento de línea de comandos o usar uno predeterminado
    agent_id = sys.argv[1] if len(sys.argv) > 1 else "8191feef-546d-46a8-a26f-b92073882f5c"
    
    logger.info(f"Ejecutando cliente de prueba para la ejecución del agente {agent_id}")
    asyncio.run(trigger_agent_execution(agent_id)) 