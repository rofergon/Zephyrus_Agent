import asyncio
import json
import logging
import websockets
from datetime import datetime
from typing import Dict, Any

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.autonomous_agent import AutonomousAgent
from src.api.db_client import DatabaseClient
from src.utils.config import WS_HOST, WS_PORT
from src.utils.logger import setup_logger

logger = setup_logger("agent_execution_service")

async def execute_agent(agent_id: str) -> Dict[str, Any]:
    """
    Executes an agent by loading its configuration and triggering its analysis and execution cycle.
    Similar to test_agent_execution.py but designed as a reusable service function.
    
    Args:
        agent_id: The ID of the agent to execute
        
    Returns:
        Dict containing the execution results
    """
    logger.info(f"Iniciando ejecución para el agente {agent_id}")
    
    try:
        # Obtener los datos completos del agente usando DatabaseClient
        logger.info("Obteniendo datos del agente desde la base de datos...")
        async with DatabaseClient() as db_client:
            # Obtener el agente
            agent_data = await db_client.get_agent(agent_id)
            if not agent_data:
                error_msg = f"No se encontró el agente con ID {agent_id}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            
            # Obtener el contrato asociado
            contract_data = await db_client.get_contract(agent_data.contract_id)
            if not contract_data:
                error_msg = f"No se encontró el contrato asociado {agent_data.contract_id}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
                
            # Obtener las funciones del agente
            functions_data = await db_client.get_agent_functions(agent_id)
            
            # Obtener la programación del agente (opcional)
            schedule_data = await db_client.get_agent_schedule(agent_id)
            
            logger.info(f"Datos obtenidos correctamente para el agente {agent_id}")
            
            # Preparar la configuración completa para crear el agente
            config = {
                "agent_id": agent_id,
                "contract": contract_data,
                "agent": agent_data.to_dict(),
                "functions": [func.to_dict() for func in functions_data],
                "schedule": schedule_data.to_dict() if schedule_data else None
            }
            
            logger.info("Creando instancia del agente con los datos obtenidos...")
            agent = await AutonomousAgent.from_config(config)
        
        logger.info("Inicializando el agente...")
        await agent.initialize()
        
        # Trigger data para simular una ejecución manual desde el WebSocket
        trigger_data = {
            "trigger_type": "websocket",
            "timestamp": datetime.now().isoformat(),
            "execution_id": f"ws_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        }
        
        # Ejecutar el ciclo de análisis y ejecución
        logger.info("Ejecutando ciclo de análisis y ejecución...")
        results = await agent.analyze_and_execute(trigger_data)
        
        if results:
            logger.info(f"Resultados de la ejecución ({len(results)} acciones)")
            return {
                "success": True, 
                "results": results,
                "agent_id": agent_id,
                "execution_count": len(results)
            }
        else:
            logger.info("No se ejecutó ninguna acción durante el ciclo")
            return {
                "success": True,
                "results": [],
                "agent_id": agent_id,
                "execution_count": 0,
                "message": "No se ejecutó ninguna acción durante el ciclo"
            }
            
    except Exception as e:
        error_msg = f"Error durante la ejecución del agente {agent_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": error_msg,
            "agent_id": agent_id
        }

async def handle_websocket_connection(websocket, path):
    """
    Handles WebSocket connections and messages.
    Listens for 'websocket_execution' message type with agent_id.
    """
    try:
        client_address = websocket.remote_address
        logger.info(f"Nueva conexión WebSocket desde {client_address}")
        
        async for message in websocket:
            try:
                # Parsear el mensaje recibido
                data = json.loads(message)
                message_type = data.get('type')
                
                logger.info(f"Mensaje recibido: {message_type}")
                
                if message_type == "websocket_execution" or message_type == "execute":
                    # Obtener el agent_id del mensaje
                    agent_id = None
                    
                    # Intentar diferentes formatos posibles
                    if 'agent_id' in data:
                        agent_id = data.get('agent_id')
                    elif 'data' in data and isinstance(data['data'], dict) and 'agent_id' in data['data']:
                        agent_id = data['data']['agent_id']
                    elif 'data' in data and isinstance(data['data'], str):
                        # Intentar parsear si es un string
                        try:
                            data_obj = json.loads(data['data'])
                            if isinstance(data_obj, dict) and 'agent_id' in data_obj:
                                agent_id = data_obj['agent_id']
                        except:
                            pass
                    
                    if not agent_id:
                        error_response = {
                            "type": "error",
                            "data": {
                                "success": False,
                                "error": "Se requiere agent_id para la ejecución"
                            }
                        }
                        await websocket.send(json.dumps(error_response))
                        continue
                    
                    # Enviar respuesta de confirmación de que la ejecución comenzó
                    start_response = {
                        "type": "execution_response",
                        "data": {
                            "success": True,
                            "message": f"Iniciando ejecución del agente {agent_id}",
                            "status": "started"
                        }
                    }
                    await websocket.send(json.dumps(start_response))
                    
                    # Ejecutar el agente
                    results = await execute_agent(agent_id)
                    
                    # Preparar respuesta con los resultados
                    completed_response = {
                        "type": "execution_response",
                        "data": {
                            "success": results["success"],
                            "status": "completed",
                            "agent_id": agent_id
                        }
                    }
                    
                    # Agregar los resultados o errores según corresponda
                    if results["success"]:
                        completed_response["data"].update({
                            "results": results.get("results", []),
                            "execution_count": results.get("execution_count", 0)
                        })
                        if "message" in results:
                            completed_response["data"]["message"] = results["message"]
                    else:
                        completed_response["data"]["error"] = results.get("error", "Error desconocido")
                    
                    # Enviar resultados
                    await websocket.send(json.dumps(completed_response))
                    
                else:
                    # Mensaje de tipo desconocido
                    await websocket.send(json.dumps({
                        "type": "error",
                        "data": {
                            "message": f"Tipo de mensaje no reconocido: {message_type}"
                        }
                    }))
                
            except json.JSONDecodeError:
                logger.error(f"Mensaje WebSocket no válido: {message}")
                await websocket.send(json.dumps({
                    "type": "error",
                    "data": {
                        "message": "Mensaje JSON no válido"
                    }
                }))
            except Exception as e:
                logger.exception(f"Error procesando mensaje: {str(e)}")
                await websocket.send(json.dumps({
                    "type": "error",
                    "data": {
                        "message": f"Error interno del servidor: {str(e)}"
                    }
                }))
                
    except Exception as e:
        logger.exception(f"Error en la conexión WebSocket: {str(e)}")

async def start_server():
    """
    Inicia el servidor WebSocket para la ejecución de agentes.
    """
    try:
        server = await websockets.serve(
            handle_websocket_connection, 
            WS_HOST, 
            WS_PORT
        )
        
        logger.info(f"Servidor WebSocket para ejecución de agentes iniciado en {WS_HOST}:{WS_PORT}")
        
        # Mantener el servidor en ejecución
        await server.wait_closed()
        
    except Exception as e:
        logger.error(f"Error iniciando el servidor WebSocket: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    logger.info("Iniciando servicio de ejecución de agentes mediante WebSocket...")
    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        logger.info("Servicio de ejecución de agentes detenido por el usuario")
    except Exception as e:
        logger.error(f"Error en el servicio de ejecución de agentes: {str(e)}", exc_info=True) 