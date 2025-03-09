import json
import logging
from typing import Dict, Set, List, Optional, Tuple
import uuid
import asyncio
from datetime import datetime
import os

import websockets
from websockets.exceptions import ConnectionClosedError

from src.utils.config import WS_HOST, WS_PORT
from src.utils.logger import setup_logger
from src.core.agent_manager import AgentManager
from src.core.autonomous_agent import AutonomousAgent
from src.api.db_client import DatabaseClient
from src.models.agent import Agent, AgentFunction, AgentSchedule

logger = setup_logger(__name__)

class WebSocketServer:
    def __init__(self, agent_manager: AgentManager):
        # RAILWAY FIX: Forzar 0.0.0.0 como host en Railway
        # Detectar si estamos en Railway
        is_railway = 'RAILWAY_STATIC_URL' in os.environ or 'RAILWAY_PUBLIC_DOMAIN' in os.environ or os.environ.get('RAILWAY_ENVIRONMENT') == 'production'
        
        if is_railway:
            # Si estamos en Railway, forzar 0.0.0.0 como host
            self.host = '0.0.0.0'
            logger.info("Detectado entorno Railway, forzando host a 0.0.0.0")
        else:
            # Si no estamos en Railway, usar el valor de configuración
            self.host = WS_HOST
            logger.info(f"Usando host de configuración: {self.host}")
        
        # Obtener puerto directamente de la variable PORT de Railway si está disponible
        # o usar WS_PORT de la configuración como respaldo
        railway_port = os.environ.get('PORT')
        if railway_port:
            self.port = int(railway_port)
            logger.info(f"Usando el puerto de Railway: {self.port}")
        else:
            self.port = WS_PORT
            logger.info(f"Usando el puerto de configuración: {self.port}")
            
        logger.info(f"WebSocketServer inicializado con host={self.host} puerto={self.port}")
            
        self.agent_manager = agent_manager
        self.clients = {}  # {websocket: path}
        self.running = False
        self.server = None
        self.last_created_agent_id = None  # El ID del último agente creado
        self.frontend_agent_id = None  # El ID enviado desde el frontend

    async def register(self, websocket: websockets.WebSocketServerProtocol):
        """
        Registra un nuevo cliente WebSocket
        """
        self.clients[websocket] = None
        logger.info(f"Client connected. Total clients: {len(self.clients)}")

    async def unregister(self, websocket: websockets.WebSocketServerProtocol):
        """
        Elimina un cliente WebSocket
        """
        self.clients.pop(websocket, None)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")

    async def broadcast(self, message: Dict):
        """
        Envía un mensaje a todos los clientes conectados
        """
        if not self.clients:
            return

        message_str = json.dumps(message)
        logger.debug(f"Broadcasting message: {message_str}")
        
        # Crear una copia de los clientes para evitar problemas si la lista cambia
        clients = list(self.clients.keys())
        for client in clients:
            try:
                await client.send(message_str)
            except Exception as e:
                logger.error(f"Error sending message to client: {str(e)}")

    async def send_error(self, websocket: websockets.WebSocketServerProtocol, error_message: str, logs=None):
        """
        Envía un mensaje de error al cliente
        """
        try:
            # Mejorar el log para incluir más detalles del error
            logger.error(f"Sending error to client: {error_message}")
            
            # Preparar la respuesta de error
            error_data = {
                "message": error_message
            }
            
            # Incluir logs si están disponibles, pero por defecto sin logs
            if logs is not None:
                error_data["logs"] = logs
            else:
                error_data["logs"] = []
                
            error_response = {
                "type": "error",
                "data": error_data
            }
            
            await websocket.send(json.dumps(error_response))
        except Exception as e:
            logger.error(f"Error al enviar mensaje de error: {str(e)}")

    async def handle_message(self, websocket: websockets.WebSocketServerProtocol, message: str):
        """
        Maneja los mensajes entrantes de los clientes
        """
        try:
            # Parsear el mensaje
            message_json = json.loads(message)
            message_type = message_json.get('type')
            message_data = message_json.get('data', {})
            
            # Mejorar el logging para incluir más detalles del mensaje recibido
            logger.debug(f"Received message: {message[:200]}..." if len(message) > 200 else f"Received message: {message}")
            logger.info(f"Received message type: {message_type}")
            
            # Extraer agent_id del mensaje si existe
            agent_id_frontend = None
            
            # Buscar agent_id en diferentes ubicaciones posibles
            if isinstance(message_data, dict) and ('agent_id' in message_data or 'agentId' in message_data):
                agent_id_frontend = message_data.get('agent_id') or message_data.get('agentId')
            # También verificar si está en el nivel principal
            elif 'agent_id' in message_json or 'agentId' in message_json:
                agent_id_frontend = message_json.get('agent_id') or message_json.get('agentId')
                
            if agent_id_frontend:
                self.frontend_agent_id = agent_id_frontend
                logger.info(f"Frontend agent ID detected: {self.frontend_agent_id}")
            
            # Manejar diferentes tipos de mensajes
            if message_type == "create_contract":
                try:
                    # También extraer agent_id del contrato si existe
                    if isinstance(message_data, dict) and ('agent_id' in message_data):
                        self.frontend_agent_id = message_data.get('agent_id')
                        logger.info(f"Frontend agent ID from contract: {self.frontend_agent_id}")
                        
                    async with DatabaseClient() as db_client:
                        contract_data = message_data
                        contract = await db_client.create_contract(contract_data)
                        logger.info(f"Contrato creado correctamente: {json.dumps(contract)}")
                        response = {
                            "type": "create_contract_response",
                            "data": contract
                        }
                        await websocket.send(json.dumps(response))
                except Exception as e:
                    error_msg = f"Error creating contract: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    await self.send_error(websocket, error_msg)
            
            elif message_type == "create_agent":
                try:
                    # Asegurarnos de guardar el agent_id del frontend
                    if isinstance(message_data, dict):
                        if 'agent_id' in message_data:
                            self.frontend_agent_id = message_data.get('agent_id')
                            logger.info(f"Using frontend agent ID for agent creation: {self.frontend_agent_id}")
                    
                    # Convertir contract_id a contractId si es necesario
                    if 'contract_id' in message_data and not message_data.get('contractId'):
                        message_data['contractId'] = message_data.pop('contract_id')
                        logger.info(f"Converted contract_id to contractId: {message_data['contractId']}")
                    
                    contract_id = message_data.get("contractId")
                    if not contract_id:
                        raise ValueError("contractId is required")
                    
                    # En lugar de verificar el contrato, simplemente intentamos crear el agente directamente
                    # El backend debería manejar el caso donde el contrato no existe
                    logger.info(f"Intentando crear agente para contrato {contract_id} sin verificación previa")
                    
                    async with DatabaseClient() as db_client:
                        try:
                            # Intentar crear o actualizar el agente
                            agent = await db_client.create_agent(message_data)
                            action = "actualizado" if message_data.get("agentId") else "creado"
                            logger.info(f"Agente {action} correctamente: {agent.agent_id}")
                            
                            # Guardar el ID del agente creado
                            self.last_created_agent_id = agent.agent_id
                            logger.info(f"ID del agente almacenado para uso posterior: {self.last_created_agent_id}")
                            
                            # IMPORTANTE: El ID del frontend ya no se usará para funciones/schedules
                            if self.frontend_agent_id and self.frontend_agent_id != agent.agent_id:
                                logger.info(f"AVISO: El ID del frontend ({self.frontend_agent_id}) es distinto del ID del backend ({agent.agent_id})")
                                logger.info(f"Para las operaciones con el agente SE USARÁ el ID del backend: {agent.agent_id}")
                            
                            response = {
                                "type": "create_agent_response",
                                "data": {
                                    "status": "success",
                                    "message": f"Agente {action} correctamente",
                                    "agent": agent.to_dict(),
                                    "agent_id": self.frontend_agent_id or agent.agent_id
                                }
                            }
                            await websocket.send(json.dumps(response))
                        except Exception as agent_error:
                            # Si es un error específico, manejarlo
                            error_msg = str(agent_error)
                            if "UNIQUE constraint failed" in error_msg:
                                logger.info("El agente ya existe, intentando actualizar...")
                                # El manejo específico ya está en create_agent
                            else:
                                raise agent_error
                except Exception as e:
                    error_msg = f"Error creating/updating agent: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    await self.send_error(websocket, error_msg)

            elif message_type == "create_function":
                try:
                    # Determinar qué agent_id usar
                    agent_id = None
                    
                    # Cambio de prioridades: El ID del backend es más importante que el del frontend
                    # Prioridad 1: Usar el último ID creado por el backend
                    if self.last_created_agent_id:
                        agent_id = self.last_created_agent_id
                        logger.info(f"Usando ID de backend para la función: {agent_id}")
                    # Prioridad 2: Usar el ID proporcionado explícitamente en este mensaje
                    elif message_data.get("agent_id") or message_data.get("agentId"):
                        agent_id = message_data.get("agent_id") or message_data.get("agentId")
                        logger.info(f"Usando ID explícito del mensaje: {agent_id}")
                    # Prioridad 3: Usar el ID del frontend guardado anteriormente
                    elif self.frontend_agent_id:
                        agent_id = self.frontend_agent_id
                        logger.info(f"Usando ID del frontend: {agent_id}")
                    else:
                        raise ValueError("No agent ID available. Please create an agent first.")
                    
                    logger.info(f"Creando función para agente {agent_id}")
                    
                    # Convertir los datos de la función al formato esperado según la guía
                    function_api_data = {
                        "function_name": message_data.get("function_name"),
                        "function_signature": message_data.get("function_signature"),
                        "function_type": message_data.get("function_type"),
                        "is_enabled": message_data.get("is_enabled", True),
                        "validation_rules": message_data.get("validation_rules", {}),
                        "abi": message_data.get("abi", {})
                    }

                    # Verificar que los campos requeridos no estén vacíos
                    required_fields = ["function_name", "function_signature", "function_type"]
                    for field in required_fields:
                        if not function_api_data.get(field):
                            raise ValueError(f"{field} must be a non-empty string")
                    
                    logger.info(f"Creando función para agente {agent_id} con datos: {json.dumps(function_api_data)}")
                    
                    # Implementar reintentos para la creación de funciones
                    max_retries = 3
                    retry_count = 0
                    last_error = None
                    
                    async with DatabaseClient() as db_client:
                        while retry_count < max_retries:
                            try:
                                # Intentar crear la función
                                function = await db_client.create_agent_function(agent_id, function_api_data)
                                logger.info(f"Función {function.function_name} creada correctamente para el agente {agent_id}")
                                response = {
                                    "type": "create_function_response",
                                    "data": {
                                        "status": "success",
                                        "function": function.to_dict()
                                    }
                                }
                                await websocket.send(json.dumps(response))
                                break
                            except Exception as e:
                                last_error = e
                                # Si el error indica que el agente no existe, verificar con otro ID
                                if "not found" in str(e).lower() and retry_count == 0 and agent_id != self.last_created_agent_id:
                                    logger.warning(f"Agente {agent_id} no encontrado, intentando con ID del backend: {self.last_created_agent_id}")
                                    agent_id = self.last_created_agent_id
                                    retry_count += 1
                                    await asyncio.sleep(1)
                                    continue
                                # Si es otro tipo de error o ya intentamos con el ID del backend
                                logger.warning(f"Error al crear función (intento {retry_count + 1}/{max_retries}): {str(e)}")
                                retry_count += 1
                                if retry_count < max_retries:
                                    await asyncio.sleep(1)
                                else:
                                    raise last_error
                except Exception as e:
                    error_msg = f"Error creating function: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    await self.send_error(websocket, error_msg)

            elif message_type == "create_schedule":
                try:
                    # Determinar qué agent_id usar
                    agent_id = None
                    
                    # Cambio de prioridades: El ID del backend es más importante que el del frontend
                    # Prioridad 1: Usar el último ID creado por el backend
                    if self.last_created_agent_id:
                        agent_id = self.last_created_agent_id
                        logger.info(f"Usando ID de backend para el schedule: {agent_id}")
                    # Prioridad 2: Usar el ID proporcionado explícitamente en este mensaje
                    elif message_data.get("agent_id") or message_data.get("agentId"):
                        agent_id = message_data.get("agent_id") or message_data.get("agentId")
                        logger.info(f"Usando ID explícito del mensaje para schedule: {agent_id}")
                    # Prioridad 3: Usar el ID del frontend guardado anteriormente
                    elif self.frontend_agent_id:
                        agent_id = self.frontend_agent_id
                        logger.info(f"Usando ID del frontend para schedule: {agent_id}")
                    else:
                        raise ValueError("No agent ID available. Please create an agent first.")
                    
                    logger.info(f"Creando schedule para agente {agent_id}")
                    
                    # Convertir los datos del schedule al formato esperado según la guía
                    schedule_api_data = {
                        "schedule_type": message_data.get("schedule_type", message_data.get("scheduleType")),
                        "cron_expression": message_data.get("cron_expression", message_data.get("cronExpression", "")),
                        "is_active": message_data.get("is_active", message_data.get("isActive", True)),
                        "next_execution": message_data.get("next_execution", message_data.get("nextExecution"))
                    }

                    # Verificar que los campos requeridos no estén vacíos
                    if not schedule_api_data["schedule_type"]:
                        raise ValueError("schedule_type must be a non-empty string")
                    
                    if schedule_api_data["schedule_type"] == "cron" and not schedule_api_data["cron_expression"]:
                        raise ValueError("cron_expression is required for cron schedule type")
                    
                    logger.info(f"Creando schedule para agente {agent_id} con datos: {json.dumps(schedule_api_data)}")
                    
                    # Implementar reintentos para la creación de schedules
                    max_retries = 3
                    retry_count = 0
                    last_error = None
                    
                    async with DatabaseClient() as db_client:
                        while retry_count < max_retries:
                            try:
                                # Intentar crear el schedule
                                schedule = await db_client.create_agent_schedule(agent_id, schedule_api_data)
                                logger.info(f"Schedule creado correctamente para el agente {agent_id}")
                                response = {
                                    "type": "create_schedule_response",
                                    "data": {
                                        "status": "success",
                                        "schedule": schedule.to_dict()
                                    }
                                }
                                await websocket.send(json.dumps(response))
                                break
                            except Exception as e:
                                last_error = e
                                # Si el error indica que el agente no existe, verificar con otro ID
                                if "not found" in str(e).lower() and retry_count == 0 and agent_id != self.last_created_agent_id:
                                    logger.warning(f"Agente {agent_id} no encontrado, intentando con ID del backend: {self.last_created_agent_id}")
                                    agent_id = self.last_created_agent_id
                                    retry_count += 1
                                    await asyncio.sleep(1)
                                    continue
                                # Si es otro tipo de error o ya intentamos con el ID del backend
                                logger.warning(f"Error al crear schedule (intento {retry_count + 1}/{max_retries}): {str(e)}")
                                retry_count += 1
                                if retry_count < max_retries:
                                    await asyncio.sleep(1)
                                else:
                                    raise last_error
                except Exception as e:
                    error_msg = f"Error creating schedule: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    await self.send_error(websocket, error_msg)

            elif message_type == "create_notification":
                try:
                    # Determinar qué agent_id usar, con la misma lógica de prioridades
                    agent_id = None
                    
                    # Prioridad 1: Usar el último ID creado por el backend
                    if self.last_created_agent_id:
                        agent_id = self.last_created_agent_id
                        logger.info(f"Usando ID de backend para la notificación: {agent_id}")
                    # Prioridad 2: Usar el ID proporcionado explícitamente en este mensaje
                    elif message_data.get("agent_id") or message_data.get("agentId"):
                        agent_id = message_data.get("agent_id") or message_data.get("agentId")
                        logger.info(f"Usando ID explícito del mensaje para notificación: {agent_id}")
                    # Prioridad 3: Usar el ID del frontend guardado anteriormente
                    elif self.frontend_agent_id:
                        agent_id = self.frontend_agent_id
                        logger.info(f"Usando ID del frontend para notificación: {agent_id}")
                    else:
                        raise ValueError("No agent ID available. Please create an agent first.")
                    
                    logger.info(f"Creando notificación para agente {agent_id}")
                    
                    async with DatabaseClient() as db_client:
                        notification = await db_client.create_agent_notification(agent_id, message_data)
                        response = {
                            "type": "create_notification_response",
                            "data": {
                                "status": "success",
                                "notification": notification
                            }
                        }
                        await websocket.send(json.dumps(response))
                except Exception as e:
                    error_msg = f"Error creating notification: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    await self.send_error(websocket, error_msg)

            # Manejar mensaje de configuración completa del agente
            elif message_type == "configure_agent":
                try:
                    agent_id = None
                    
                    # Usar el mismo orden de prioridad que hemos establecido
                    if self.last_created_agent_id:
                        agent_id = self.last_created_agent_id
                        logger.info(f"Usando ID de backend para mensaje configure_agent: {agent_id}")
                    elif message_data.get("agent_id") or message_data.get("agentId"):
                        agent_id = message_data.get("agent_id") or message_data.get("agentId")
                        logger.info(f"Usando ID explícito para mensaje configure_agent: {agent_id}")
                    elif self.frontend_agent_id:
                        agent_id = self.frontend_agent_id
                        logger.info(f"Usando ID del frontend para mensaje configure_agent: {agent_id}")
                    
                    if not agent_id:
                        raise ValueError("No agent ID available for configure_agent")
                    
                    logger.info(f"Recibido mensaje configure_agent para agente {agent_id}")
                    
                    # Enviar respuesta de éxito
                    response = {
                        "type": "configure_agent_response",
                        "data": {
                            "status": "success",
                            "message": "Agente configurado correctamente",
                            "agent_id": agent_id
                        }
                    }
                    await websocket.send(json.dumps(response))
                    
                    # También enviamos un mensaje agent_configured para mantener consistencia con el frontend
                    agent_configured = {
                        "type": "agent_configured",
                        "data": {
                            "status": "success",
                            "agent_id": agent_id,
                            "message": "Agente configurado y listo para usar"
                        }
                    }
                    await websocket.send(json.dumps(agent_configured))
                    
                    logger.info(f"Agente {agent_id} configurado correctamente")
                except Exception as e:
                    error_msg = f"Error en configuración de agente: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    await self.send_error(websocket, error_msg)

            # Manejar mensajes de control de agente
            elif message_type == "start_agent":
                agent_id = message_data.get("agent_id")
                if agent_id:
                    await self.agent_manager.start_agent(agent_id)
                    await self.broadcast({
                        "type": "agent_started",
                        "data": {"agent_id": agent_id}
                    })
                else:
                    await self.send_error(websocket, "agent_id is required")

            elif message_type == "stop_agent":
                agent_id = message_data.get("agent_id")
                if agent_id:
                    self.agent_manager.stop_agent(agent_id)
                    await self.broadcast({
                        "type": "agent_stopped",
                        "data": {"agent_id": agent_id}
                    })
                else:
                    await self.send_error(websocket, "agent_id is required")

            elif message_type == "remove_agent":
                agent_id = message_data.get("agent_id")
                if agent_id:
                    self.agent_manager.remove_agent(agent_id)
                    await self.broadcast({
                        "type": "agent_removed",
                        "data": {"agent_id": agent_id}
                    })
                else:
                    await self.send_error(websocket, "agent_id is required")

            # Manejar la ejecución de un agente
            elif message_type == "execute" or message_type == "websocket_execution":
                try:
                    # Obtener el ID del agente
                    agent_id = None
                    
                    # Usar el mismo orden de prioridad pero con mejor logging
                    # 1. ID explícito en el mensaje (ya sea en data o en nivel principal)
                    if message_data.get("agent_id") or message_data.get("agentId"):
                        agent_id = message_data.get("agent_id") or message_data.get("agentId")
                        logger.info(f"Usando ID explícito en message.data para ejecución: {agent_id}")
                    elif message_json.get("agent_id") or message_json.get("agentId"):
                        agent_id = message_json.get("agent_id") or message_json.get("agentId")
                        logger.info(f"Usando ID explícito en nivel principal para ejecución: {agent_id}")
                    # 2. Último agente creado por el backend
                    elif self.last_created_agent_id:
                        agent_id = self.last_created_agent_id
                        logger.info(f"Usando ID de backend (último creado) para ejecución: {agent_id}")
                    # 3. ID proporcionado por el frontend previamente
                    elif self.frontend_agent_id:
                        agent_id = self.frontend_agent_id
                        logger.info(f"Usando ID del frontend (almacenado) para ejecución: {agent_id}")
                    
                    if not agent_id:
                        error_msg = "No agent ID available for execute"
                        logger.error(f"Error en ejecución: {error_msg}")
                        raise ValueError(error_msg)
                    
                    # Log detallado de la ejecución
                    logger.info(f"Ejecutando agente {agent_id} (tipo de mensaje: {message_type})")
                    
                    # Enviar respuesta de que el proceso de ejecución ha comenzado
                    response = {
                        "type": "execute_response",
                        "data": {
                            "status": "processing",
                            "message": "Ejecución del agente iniciada",
                            "agent_id": agent_id
                        }
                    }
                    await websocket.send(json.dumps(response))
                    
                    # Ejecutar el análisis y ejecución en un task separado para no bloquear
                    asyncio.create_task(self._load_and_execute_agent(agent_id, websocket))
                    
                except Exception as e:
                    error_msg = f"Error al ejecutar agente: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    await self.send_error(websocket, error_msg)

            else:
                await self.send_error(websocket, f"Unknown message type: {message_type}")

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON message received", exc_info=True)
            await self.send_error(websocket, "Invalid JSON message")
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}", exc_info=True)
            await self.send_error(websocket, str(e))

    async def _load_and_execute_agent(self, agent_id: str, websocket):
        """
        Carga un agente desde la base de datos y lo ejecuta
        """
        # Lista para almacenar los logs de ejecución internos (para depuración)
        execution_logs = []
        
        # Lista para almacenar solo los comentarios del agente que se enviarán al frontend
        agent_comments = []
        
        try:
            logger.info(f"Cargando agente {agent_id} desde la base de datos")
            execution_logs.append({
                "timestamp": datetime.now().isoformat(),
                "level": "info",
                "message": f"Cargando agente {agent_id} desde la base de datos"
            })
            
            # Obtener los datos del agente desde la base de datos
            async with DatabaseClient() as db_client:
                # Obtener el agente
                agent_data = await db_client.get_agent(agent_id)
                if not agent_data:
                    error_msg = f"No se encontró el agente con ID {agent_id}"
                    logger.error(error_msg)
                    execution_logs.append({
                        "timestamp": datetime.now().isoformat(),
                        "level": "error",
                        "message": error_msg
                    })
                    await self.send_error(websocket, error_msg, [])
                    return
                
                execution_logs.append({
                    "timestamp": datetime.now().isoformat(),
                    "level": "info",
                    "message": f"Agente encontrado: {agent_data.name}"
                })
                
                # Obtener el contrato asociado
                contract_data = await db_client.get_contract(agent_data.contract_id)
                if not contract_data:
                    error_msg = f"No se encontró el contrato asociado {agent_data.contract_id}"
                    logger.error(error_msg)
                    execution_logs.append({
                        "timestamp": datetime.now().isoformat(),
                        "level": "error",
                        "message": error_msg
                    })
                    await self.send_error(websocket, error_msg, [])
                    return
                    
                execution_logs.append({
                    "timestamp": datetime.now().isoformat(),
                    "level": "info",
                    "message": f"Contrato encontrado: {contract_data.get('name', 'Sin nombre')}"
                })
                
                # Obtener las funciones del agente
                functions_data = await db_client.get_agent_functions(agent_id)
                
                execution_logs.append({
                    "timestamp": datetime.now().isoformat(),
                    "level": "info",
                    "message": f"Funciones encontradas: {len(functions_data)}"
                })
                
                # Obtener la programación del agente (opcional)
                schedule_data = await db_client.get_agent_schedule(agent_id)
                
                logger.info(f"Datos obtenidos correctamente para el agente {agent_id}")
                execution_logs.append({
                    "timestamp": datetime.now().isoformat(),
                    "level": "info",
                    "message": f"Datos obtenidos correctamente para el agente"
                })
                
                # Preparar la configuración completa para crear el agente
                config = {
                    "agent_id": agent_id,
                    "contract": contract_data,
                    "agent": agent_data.to_dict(),
                    "functions": [func.to_dict() for func in functions_data],
                    "schedule": schedule_data.to_dict() if schedule_data else None
                }
                
                logger.info("Creando instancia del agente con los datos obtenidos...")
                execution_logs.append({
                    "timestamp": datetime.now().isoformat(),
                    "level": "info",
                    "message": "Creando instancia del agente con los datos obtenidos"
                })
                
                agent = await AutonomousAgent.from_config(config)
            
            # Una vez cargado, inicializar y ejecutar el agente
            await self._execute_agent(agent, agent_id, websocket)
            
        except Exception as e:
            error_msg = f"Error cargando o ejecutando el agente {agent_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            execution_logs.append({
                "timestamp": datetime.now().isoformat(),
                "level": "error",
                "message": error_msg
            })
            
            # Enviar mensaje de error al cliente (sin logs)
            error_response = {
                "type": "execute_response",
                "data": {
                    "status": "error",
                    "agent_id": agent_id,
                    "message": error_msg,
                    "logs": []  # No enviar logs en caso de error
                }
            }
            await websocket.send(json.dumps(error_response))

    async def _execute_agent(self, agent: AutonomousAgent, agent_id: str, websocket):
        """
        Ejecuta un agente autónomo y envía los resultados al cliente
        """
        logger.info(f"Iniciando método _execute_agent para agente {agent_id}")
        
        # Lista para almacenar los logs de ejecución internos (para depuración)
        execution_logs = []
        
        # Lista para almacenar solo los comentarios del agente que se enviarán al frontend
        agent_comments = []
        
        try:
            # Inicializar el agente - siempre llamamos a initialize() 
            # ya que parece que el método maneja correctamente si ya está inicializado
            logger.info(f"Inicializando el agente {agent_id}")
            execution_logs.append({
                "timestamp": datetime.now().isoformat(),
                "level": "info",
                "message": f"Inicializando el agente {agent_id}"
            })
            
            await agent.initialize()
            logger.info(f"Agente {agent_id} inicializado correctamente")
            execution_logs.append({
                "timestamp": datetime.now().isoformat(),
                "level": "info",
                "message": f"Agente inicializado correctamente"
            })
            
            # Datos del disparador para la ejecución (en este caso, una ejecución manual)
            trigger_data = {
                "trigger_type": "manual",
                "timestamp": datetime.now().isoformat(),
                "execution_id": f"ws_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            }
            
            # Extraer parámetros de la descripción del agente
            try:
                if hasattr(agent, 'agent') and agent.agent and hasattr(agent.agent, 'description'):
                    # Importar la función de análisis de descripción desde donde sea necesario
                    # Esto es temporal - lo ideal sería tener esta función en una ubicación común
                    import re
                    
                    def analyze_agent_description(description):
                        """Analiza la descripción del agente para extraer parámetros relevantes"""
                        params = {
                            "addresses": [],
                            "amounts": [],
                            "functions": [],
                            "conditions": [],
                            "behaviors": []
                        }
                        
                        # Extraer direcciones Ethereum
                        address_pattern = r'0x[a-fA-F0-9]{40}'
                        params["addresses"] = re.findall(address_pattern, description)
                        
                        # Extraer cantidades numéricas grandes
                        amount_pattern = r'(\d{10,})'
                        amount_matches = re.findall(amount_pattern, description)
                        params["amounts"] = [int(amount) for amount in amount_matches]
                        
                        # Identificar nombres de funciones
                        function_pattern = r'using\s+([a-zA-Z0-9_]+)|call\s+([a-zA-Z0-9_]+)|function\s+([a-zA-Z0-9_]+)|método\s+([a-zA-Z0-9_]+)'
                        function_matches = re.findall(function_pattern, description, re.IGNORECASE)
                        params["functions"] = [match[0] or match[1] or match[2] or match[3] for match in function_matches if any(match)]
                        
                        # Identificar condiciones
                        condition_pattern = r'(?:if|when|si|cuando)\s+([^.,;]+)'
                        params["conditions"] = re.findall(condition_pattern, description, re.IGNORECASE)
                        
                        # Detectar patrones de comportamiento
                        if "check" in description.lower() or "verificar" in description.lower() or "comprobar" in description.lower():
                            params["behaviors"].append("check")
                        if "balance" in description.lower():
                            params["behaviors"].append("check_balance")
                        if "mint" in description.lower() or "crear" in description.lower() or "generar" in description.lower():
                            params["behaviors"].append("mint")
                        if "repeat" in description.lower() or "repetir" in description.lower() or "until" in description.lower() or "loop" in description.lower():
                            params["behaviors"].append("repeat")
                            
                        return params
                    
                    def extract_parameters_for_function(function_name, function_abi, agent_params, function_type):
                        """Extrae los parámetros adecuados para una función basado en su ABI y los parámetros extraídos"""
                        params = {}
                        
                        if not function_abi or "inputs" not in function_abi:
                            # Si no hay información ABI, intentar inferir parámetros por el nombre
                            if function_name.lower() in ["balanceof", "balance"]:
                                if agent_params["addresses"]:
                                    params = {"account": agent_params["addresses"][0]}
                                return params
                            
                            if function_name.lower() in ["mint", "transfer", "send"]:
                                if agent_params["addresses"]:
                                    params = {"to": agent_params["addresses"][0]}
                                    if agent_params["amounts"]:
                                        params["amount"] = agent_params["amounts"][0]
                                return params
                            
                            return params
                        
                        # Procesar cada parámetro de entrada según el ABI
                        for input_param in function_abi["inputs"]:
                            param_name = input_param.get("name", "")
                            param_type = input_param.get("type", "")
                            
                            # Parámetros de dirección (address)
                            if param_type == "address" and param_name.lower() in ["to", "account", "owner", "recipient"]:
                                if agent_params["addresses"]:
                                    params[param_name] = agent_params["addresses"][0]
                            
                            # Parámetros de cantidad (uint)
                            if param_type.startswith("uint") and param_name.lower() in ["amount", "value", "quantity"]:
                                if agent_params["amounts"]:
                                    # Para funciones mint, usar el segundo monto si está disponible
                                    if function_name.lower() == "mint" and len(agent_params["amounts"]) > 1:
                                        params[param_name] = agent_params["amounts"][1]
                                    else:
                                        params[param_name] = agent_params["amounts"][0]
                        
                        return params
                    
                    # Extraer parámetros y añadirlos al trigger_data
                    extracted_params = analyze_agent_description(agent.agent.description)
                    trigger_data["extracted_params"] = extracted_params
                    
                    # También preparar los parámetros para cada función
                    if hasattr(agent, '_functions') and agent._functions:
                        for func_name, func in agent._functions.items():
                            if hasattr(func, 'abi') and func.abi:
                                func_params = extract_parameters_for_function(
                                    func.name, 
                                    func.abi, 
                                    extracted_params,
                                    func.function_type
                                )
                                
                                if hasattr(func, "extracted_params"):
                                    func.extracted_params = func_params
                                else:
                                    setattr(func, "extracted_params", func_params)
                                
                                logger.info(f"Parámetros para {func.name}: {func_params}")
                    
                    # Añadir flag para completar todas las tareas
                    trigger_data["complete_all_tasks"] = True
                    
                    # Aumentar el número máximo de ciclos
                    trigger_data["max_cycles"] = 10
                    
                    # Log para depuración
                    logger.info(f"Parámetros extraídos: {extracted_params}")
                    execution_logs.append({
                        "timestamp": datetime.now().isoformat(),
                        "level": "info",
                        "message": f"Parámetros extraídos de la descripción del agente"
                    })
                
            except Exception as e:
                logger.error(f"Error extrayendo parámetros: {str(e)}")
                execution_logs.append({
                    "timestamp": datetime.now().isoformat(),
                    "level": "error",
                    "message": f"Error extrayendo parámetros: {str(e)}"
                })
            
            # Enviar un mensaje de log informando que la ejecución comienza
            log_start = {
                "type": "log",
                "data": {
                    "agent_id": agent_id,
                    "level": "info",
                    "message": f"Iniciando ejecución del agente {agent_id}..."
                }
            }
            await websocket.send(json.dumps(log_start))
            execution_logs.append({
                "timestamp": datetime.now().isoformat(),
                "level": "info",
                "message": f"Iniciando ejecución del agente"
            })
            
            # Obtener los logs de ejecución de la base de datos antes de la ejecución
            # para calcular cuáles son nuevos después
            previous_logs = []
            try:
                async with DatabaseClient() as db_client:
                    logs_url = f"{db_client.base_url}/agents/{agent_id}/logs"
                    async with db_client.session.get(logs_url) as response:
                        if response.status == 200:
                            previous_logs = await response.json()
                            logger.info(f"Obtenidos {len(previous_logs)} logs previos")
            except Exception as e:
                logger.error(f"Error obteniendo logs previos: {str(e)}")
            
            # Ejecutar el agente
            results = await agent.analyze_and_execute(trigger_data)
            
            # Obtener los logs de ejecución de la base de datos después de la ejecución
            new_logs = []
            try:
                async with DatabaseClient() as db_client:
                    logs_url = f"{db_client.base_url}/agents/{agent_id}/logs"
                    async with db_client.session.get(logs_url) as response:
                        if response.status == 200:
                            all_logs = await response.json()
                            logger.info(f"Obtenidos {len(all_logs)} logs totales")
                            
                            # Filtrar los logs nuevos (los que no estaban antes)
                            if previous_logs:
                                previous_ids = {log['execution_log_id'] for log in previous_logs if 'execution_log_id' in log}
                                new_logs = [log for log in all_logs if 'execution_log_id' in log and log['execution_log_id'] not in previous_ids]
                            else:
                                new_logs = all_logs
                                
                            logger.info(f"Identificados {len(new_logs)} logs nuevos")
                            
                            # Extraer mensajes significativos del agente
                            for log in new_logs:
                                error_message = log.get('error_message', '')
                                
                                # Solo guardar mensajes que parezcan comentarios del agente (no mensajes técnicos)
                                if error_message and error_message not in ["", "null"]:
                                    # Filtrar mensajes técnicos y genéricos
                                    if not any(generic in error_message.lower() for generic in [
                                        "executing", "based on agent", "executing function", 
                                        "checking if", "checking write"
                                    ]):
                                        # Es un comentario significativo del agente
                                        if error_message not in agent_comments:
                                            agent_comments.append(error_message)
            except Exception as e:
                logger.error(f"Error obteniendo logs de ejecución: {str(e)}")
                execution_logs.append({
                    "timestamp": datetime.now().isoformat(),
                    "level": "error",
                    "message": f"Error obteniendo logs de ejecución: {str(e)}"
                })
            
            # Log detallado de los resultados
            if results:
                logger.info(f"Ejecución completada para agente {agent_id}: {len(results)} acciones")
                execution_logs.append({
                    "timestamp": datetime.now().isoformat(),
                    "level": "info",
                    "message": f"Ejecución completada: {len(results)} acciones"
                })
                
                # Procesar y formatear los resultados para el frontend
                formatted_results = []
                
                for i, action in enumerate(results, 1):
                    # Extraer los datos relevantes
                    function_name = action.get('function_name', action.get('function', 'unknown'))
                    status = action.get('status', 'completed')
                    params = action.get('params', action.get('parameters', {}))
                    message = action.get('message', '')
                    
                    # Extraer resultado o error
                    if 'result' in action:
                        if isinstance(action['result'], dict):
                            if 'success' in action['result'] and action['result']['success'] is True:
                                result_value = action['result'].get('data', '')
                                result_summary = f"Resultado: {result_value}"
                                success = True
                            elif 'success' in action['result'] and action['result']['success'] is False:
                                error_msg = action['result'].get('error', 'Error desconocido')
                                # Extraer mensaje principal de error
                                if isinstance(error_msg, str) and "execution reverted" in error_msg:
                                    import re
                                    match = re.search(r'"([^"]+)"', error_msg)
                                    if match:
                                        error_msg = match.group(1)
                                result_summary = f"Error: {error_msg}"
                                success = False
                            else:
                                result_summary = str(action['result'])
                                success = True
                        else:
                            result_summary = str(action['result'])
                            success = True
                    elif 'error' in action:
                        result_summary = f"ERROR: {action['error']}"
                        success = False
                    else:
                        result_summary = "No hay información de resultado"
                        success = None
                    
                    # Crear entrada formateada para el resultado
                    formatted_result = {
                        "function": function_name,
                        "params": params,
                        "result": result_summary,
                        "success": success
                    }
                    
                    # Si hay un mensaje, guardarlo para los comentarios del agente
                    if message and message not in ["", "null"] and message not in agent_comments:
                        # Filtrar mensajes técnicos y genéricos
                        if not any(generic in message.lower() for generic in [
                            "executing", "based on agent", "executing function", 
                            "checking if", "checking write"
                        ]):
                            agent_comments.append(message)
                    
                    formatted_results.append(formatted_result)
                
                # Reemplazar los resultados con la versión formateada
                results = formatted_results
            else:
                logger.info(f"Ejecución completada para agente {agent_id}: sin acciones")
                execution_logs.append({
                    "timestamp": datetime.now().isoformat(),
                    "level": "info",
                    "message": f"Ejecución completada: sin acciones"
                })
            
            # Formatear los comentarios del agente para el frontend
            agent_logs = []
            for comment in agent_comments:
                agent_logs.append({
                    "timestamp": datetime.now().isoformat(),
                    "level": "info",
                    "message": comment
                })
            
            # Preparar la respuesta con los resultados y SOLO los comentarios del agente
            execution_result = {
                "type": "execute_response",
                "data": {
                    "status": "success",
                    "agent_id": agent_id,
                    "results": results if results else [],
                    "message": "Ejecución completada con éxito",
                    "logs": agent_logs  # Solo incluir los comentarios del agente
                }
            }
            
            # Enviar los resultados al cliente
            logger.info(f"Enviando resultados de ejecución al cliente para agente {agent_id}")
            await websocket.send(json.dumps(execution_result))
            
            # También emitir un mensaje de log para el agente con el resumen
            log_message = {
                "type": "log",
                "data": {
                    "agent_id": agent_id,
                    "level": "info",
                    "message": f"Ejecución completada: {len(results) if results else 0} acciones realizadas"
                }
            }
            await websocket.send(json.dumps(log_message))
            
        except Exception as e:
            error_msg = f"Error durante la ejecución del agente {agent_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            execution_logs.append({
                "timestamp": datetime.now().isoformat(),
                "level": "error",
                "message": error_msg
            })
            
            # Enviar mensaje de error al cliente
            error_response = {
                "type": "execute_response",
                "data": {
                    "status": "error",
                    "agent_id": agent_id,
                    "message": error_msg,
                    "logs": []  # No enviar logs en caso de error
                }
            }
            await websocket.send(json.dumps(error_response))

    async def ws_handler(self, websocket):
        """
        Maneja una conexión WebSocket
        """
        try:
            # Registrar el cliente
            client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
            logger.info(f"Nueva conexión WebSocket desde {client_info}")
            await self.register(websocket)
            
            # Procesar mensajes
            try:
                async for message in websocket:
                    try:
                        logger.debug(f"Mensaje recibido desde {client_info} [{len(message)} bytes]")
                        await self.handle_message(websocket, message)
                    except Exception as e:
                        # Sólo capturar excepciones del procesamiento de mensajes
                        # para mantener la conexión abierta
                        logger.error(f"Error procesando mensaje desde {client_info}: {str(e)}", exc_info=True)
                        await self.send_error(websocket, str(e))
            except ConnectionClosedError as e:
                logger.info(f"Conexión cerrada por el cliente {client_info}: {e.code} {e.reason}")
            except Exception as e:
                logger.error(f"Error en el bucle de mensajes para {client_info}: {str(e)}", exc_info=True)
                
        except Exception as e:
            logger.error(f"Error en ws_handler: {str(e)}", exc_info=True)
        finally:
            # Asegurar que el cliente sea eliminado incluso si hay errores
            await self.unregister(websocket)
            logger.info(f"Conexión WebSocket cerrada con {client_info if 'client_info' in locals() else 'cliente desconocido'}")

    async def start(self):
        """
        Inicia el servidor WebSocket
        """
        try:
            # Registrar información adicional para depuración
            logger.info(f"Iniciando servidor WebSocket en host={self.host} puerto={self.port}")
            logger.info(f"Variables de entorno: PORT={os.environ.get('PORT')}, WS_PORT={os.environ.get('WS_PORT')}, WS_HOST={os.environ.get('WS_HOST')}")
            
            # RAILWAY FIX: Último chequeo para asegurar que estamos usando 0.0.0.0 si estamos en Railway
            if 'RAILWAY_STATIC_URL' in os.environ or 'RAILWAY_PUBLIC_DOMAIN' in os.environ:
                if self.host != '0.0.0.0':
                    logger.warning(f"¡CORRECCIÓN! Detectado Railway pero host es {self.host}. Forzando a 0.0.0.0")
                    self.host = '0.0.0.0'
            
            logger.info(f"INICIANDO EN: ws://{self.host}:{self.port} - Asegúrate de que esto sea 0.0.0.0 en Railway")
            
            self.server = await websockets.serve(
                self.ws_handler,
                self.host,
                self.port
            )
            logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")
            
            # Mantener el servidor corriendo
            await asyncio.Future()
            
        except Exception as e:
            logger.error(f"Error starting WebSocket server: {str(e)}", exc_info=True)
            raise

    async def stop(self):
        """
        Detiene el servidor WebSocket
        """
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("WebSocket server stopped") 