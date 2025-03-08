import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import asyncio
import uuid
import os

import aiohttp

from src.models.agent import Agent, AgentFunction, AgentSchedule, AgentFunctionParam
from src.utils.config import DB_API_URL
from src.utils.logger import setup_logger

# Definición de URLs de API
DB_API_URL = os.getenv('DB_API_URL', 'https://3ea5d3427422.ngrok.app/api/db')
# URL base para la API de contratos (sin /db)
CONTRACT_API_URL = os.getenv('CONTRACT_API_URL', 
                          DB_API_URL.replace('/api/db', '/api') if '/api/db' in DB_API_URL 
                          else 'https://3ea5d3427422.ngrok.app/api')

logger = setup_logger(__name__)

class DatabaseClient:
    def __init__(self, base_url: str = DB_API_URL):
        self.base_url = base_url
        self.session = None
        self.last_created_agent_id = None  # Propiedad para rastrear el último ID de agente creado

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def configure_agent(self, config_data: Dict) -> Tuple[Agent, List[AgentFunction], Optional[AgentSchedule]]:
        """
        Configura un agente con toda su información desde el frontend
        """
        try:
            # Validar la estructura del config_data
            required_fields = ['agent', 'functions']
            for field in required_fields:
                if field not in config_data:
                    raise ValueError(f"Missing required field: {field}")

            # 1. Verificar que el contrato existe y crearlo si no existe
            contract_id = config_data['agent']['contractId']
            contract_exists = False
            
            try:
                contract = await self.get_contract(contract_id)
                logger.info(f"Contrato {contract_id} encontrado en la base de datos")
                contract_exists = True
            except Exception as e:
                logger.warning(f"No se pudo encontrar el contrato {contract_id}: {str(e)}")
            
            if not contract_exists:
                logger.info(f"Intentando crear el contrato {contract_id} en la base de datos")
                try:
                    # Datos necesarios para crear un contrato según la guía de integración
                    contract_data = {
                        "contract_id": contract_id,
                        "address": contract_id,
                        "chain_id": 1,  # Valor por defecto para Ethereum mainnet
                        "name": config_data['agent']['name'] + " Contract",
                        "type": "ERC20",  # Tipo por defecto
                        "abi": json.dumps([]),  # ABI mínimo
                        "deployed_at": datetime.now().isoformat(),
                        "owner_address": config_data['agent']['owner']
                    }
                    await self.create_contract(contract_data)
                    logger.info(f"Contrato {contract_id} creado en la base de datos")
                    # Esperar un momento para asegurar que el contrato está completamente creado en la base de datos
                    await asyncio.sleep(0.5)
                except Exception as create_err:
                    logger.error(f"No se pudo crear el contrato {contract_id}: {str(create_err)}")
                    raise ValueError(f"El contrato {contract_id} no existe y no se pudo crear: {str(create_err)}")
                
            # 2. Procesar el agente
            agent_data = config_data['agent']
            agent = Agent.from_dict(agent_data)
            
            # 3. Procesar las funciones
            functions = [AgentFunction.from_dict(func) for func in config_data['functions']]
            
            # 4. Procesar el schedule si existe
            schedule = None
            if 'schedule' in config_data and config_data['schedule']:
                schedule = AgentSchedule.from_dict(config_data['schedule'])

            return agent, functions, schedule

        except Exception as e:
            logger.error(f"Error configuring agent: {str(e)}")
            raise

    async def get_agent(self, agent_id: str) -> Optional[Agent]:
        """
        Obtiene un agente por su ID
        """
        try:
            # Usar la ruta correcta para obtener un agente por ID
            async with self.session.get(f"{self.base_url}/agents/getById/{agent_id}") as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                result = await response.json()
                
                # Verificar que la respuesta sea exitosa y contiene datos
                if not result.get('success', False) or 'data' not in result:
                    logger.warning(f"Respuesta sin éxito o sin datos para el agente {agent_id}: {result}")
                    return None
                
                # Los datos del agente están dentro del objeto 'data'
                agent_data = result['data']
                
                # Verificar si data es una lista y obtener el primer elemento
                if isinstance(agent_data, list):
                    if not agent_data:  # Lista vacía
                        return None
                    # Usar el primer agente en la lista
                    agent_data = agent_data[0]
                
                # Crear y devolver el objeto Agent
                logger.info(f"Agente {agent_id} obtenido correctamente")
                return Agent.from_dict(agent_data)
        except Exception as e:
            logger.error(f"Error getting agent {agent_id}: {str(e)}")
            return None

    async def update_agent(self, agent_id: str, data: Dict) -> Optional[Agent]:
        """
        Actualiza un agente
        """
        try:
            async with self.session.patch(f"{self.base_url}/agents/{agent_id}", json=data) as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                data = await response.json()
                return Agent.from_dict(data)
        except Exception as e:
            logger.error(f"Error updating agent {agent_id}: {str(e)}")
            raise

    async def get_agent_functions(self, agent_id: str) -> List[AgentFunction]:
        """
        Obtiene las funciones de un agente
        """
        try:
            async with self.session.get(f"{self.base_url}/agents/{agent_id}/functions") as response:
                response.raise_for_status()
                data = await response.json()
                return [AgentFunction.from_dict(func) for func in data]
        except Exception as e:
            logger.error(f"Error getting functions for agent {agent_id}: {str(e)}")
            raise

    async def create_execution_log(self, agent_id: str, log_data: Dict) -> Dict:
        """
        Crea un registro de ejecución
        """
        try:
            # Formato correcto para la creación de logs
            formatted_log_data = {
                "function_id": log_data.get("functionId"),
                "status": log_data.get("status", "pending"),
                "execution_time": log_data.get("timestamp", datetime.utcnow().isoformat()),
            }
            
            # Añadir campos adicionales si están presentes
            if "params" in log_data:
                formatted_log_data["params"] = log_data["params"]
            
            if "transaction_hash" in log_data:
                formatted_log_data["transaction_hash"] = log_data["transaction_hash"]
                
            if "gas_used" in log_data:
                formatted_log_data["gas_used"] = log_data["gas_used"]
                
            if "gas_price" in log_data:
                formatted_log_data["gas_price"] = log_data["gas_price"]
                
            # Añadir mensaje o comentario del modelo cuando esté presente
            if "message" in log_data:
                formatted_log_data["error_message"] = log_data["message"]
            
            logger.info(f"Creating execution log for agent {agent_id} with data: {formatted_log_data}")
            
            async with self.session.post(f"{self.base_url}/agents/{agent_id}/logs", json=formatted_log_data) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"Error creating execution log for agent {agent_id}: {str(e)}")
            raise

    async def create_agent_function(self, agent_id: str, function_data: Dict) -> AgentFunction:
        """
        Crea una función para un agente específico
        """
        try:
            if not agent_id:
                raise ValueError("agent_id is required")
            
            # Validar campos requeridos
            required_fields = ["function_name", "function_signature", "function_type"]
            for field in required_fields:
                if field not in function_data or not function_data[field]:
                    raise ValueError(f"{field} is required")
            
            # Preparar los datos en el formato snake_case que espera el backend
            api_data = {
                "function_name": function_data.get("function_name"),
                "function_signature": function_data.get("function_signature"),
                "function_type": function_data.get("function_type"),
                "is_enabled": function_data.get("is_enabled", True),
                "validation_rules": function_data.get("validation_rules", {}),
                "abi": function_data.get("abi", {})
            }
            
            logger.info(f"Enviando datos de función para agente {agent_id}: {json.dumps(api_data)}")
            
            # Manejamos reintentos
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # Para el primer intento, usamos el ID proporcionado
                    # Para reintentos, podemos probar con el ID del backend si está disponible
                    target_agent_id = agent_id
                    if retry_count > 0 and hasattr(self, 'last_created_agent_id') and self.last_created_agent_id:
                        target_agent_id = self.last_created_agent_id
                        logger.info(f"Reintento {retry_count+1}: Probando con el ID alternativo para función: {target_agent_id}")
                    
                    endpoint = f"{self.base_url}/agents/{target_agent_id}/functions"
                    headers = {"Content-Type": "application/json"}
                    
                    logger.info(f"POST a {endpoint}")
                    response = await self.session.post(endpoint, json=api_data, headers=headers)
                    
                    if response.status >= 400:
                        error_text = await response.text()
                        logger.warning(f"Error al crear función (intento {retry_count + 1}/{max_retries}): {response.status} - {error_text}")
                        retry_count += 1
                        
                        if retry_count < max_retries:
                            await asyncio.sleep(1)
                            continue
                        else:
                            response.raise_for_status()
                    else:
                        # Proceso exitoso
                        break
                
                except Exception as e:
                    logger.warning(f"Error en intento {retry_count + 1}/{max_retries}: {str(e)}")
                    retry_count += 1
                    
                    if retry_count < max_retries:
                        await asyncio.sleep(1)
                    else:
                        raise e
            
            result = await response.json()
            
            # Obtener valores manteniendo compatibilidad con ambos formatos (camelCase y snake_case)
            function_id = result.get("function_id", result.get("functionId", ""))
            agent_id = result.get("agent_id", result.get("agentId", ""))
            function_name = result.get("function_name", result.get("functionName", ""))
            function_signature = result.get("function_signature", result.get("functionSignature", ""))
            function_type = result.get("function_type", result.get("functionType", ""))
            is_enabled = result.get("is_enabled", result.get("isEnabled", True))
            validation_rules = result.get("validation_rules", result.get("validationRules", {}))
            abi = result.get("abi", {})
            created_at = result.get("created_at", result.get("createdAt", ""))
            updated_at = result.get("updated_at", result.get("updatedAt", ""))
            
            # Crear objeto AgentFunction
            function = AgentFunction(
                function_id=function_id,
                agent_id=agent_id,
                function_name=function_name,
                function_signature=function_signature,
                function_type=function_type,
                is_enabled=is_enabled,
                validation_rules=validation_rules,
                abi=abi,
                created_at=created_at,
                updated_at=updated_at
            )
            
            return function
            
        except Exception as e:
            logger.error(f"Error creating function for agent {agent_id}: {str(e)}")
            raise

    async def update_agent_function(self, agent_id: str, function_id: str, function_data: Dict) -> Optional[AgentFunction]:
        """
        Actualiza una función existente de un agente
        """
        try:
            async with self.session.patch(f"{self.base_url}/agents/{agent_id}/functions/{function_id}", json=function_data) as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                data = await response.json()
                return AgentFunction.from_dict(data)
        except Exception as e:
            logger.error(f"Error updating function {function_id} for agent {agent_id}: {str(e)}")
            raise

    async def get_function_params(self, function_id: str) -> List[AgentFunctionParam]:
        """
        Obtiene los parámetros de una función
        """
        try:
            async with self.session.get(f"{self.base_url}/functions/{function_id}/params") as response:
                if response.status == 404:
                    logger.warning(f"No parameters found for function {function_id}")
                    return []
                response.raise_for_status()
                data = await response.json()
                return [AgentFunctionParam.from_dict(param) for param in data]
        except Exception as e:
            logger.error(f"Error getting parameters for function {function_id}: {str(e)}")
            # Devolver lista vacía en lugar de lanzar excepción
            return []

    async def create_function_param(self, function_id: str, param_data: Dict) -> AgentFunctionParam:
        """
        Crea un nuevo parámetro para una función
        """
        try:
            async with self.session.post(f"{self.base_url}/functions/{function_id}/params", json=param_data) as response:
                response.raise_for_status()
                data = await response.json()
                return AgentFunctionParam.from_dict(data)
        except Exception as e:
            logger.error(f"Error creating parameter for function {function_id}: {str(e)}")
            raise

    async def update_function_param(self, function_id: str, param_id: str, param_data: Dict) -> Optional[AgentFunctionParam]:
        """
        Actualiza un parámetro existente de una función
        """
        try:
            async with self.session.patch(f"{self.base_url}/functions/{function_id}/params/{param_id}", json=param_data) as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                data = await response.json()
                return AgentFunctionParam.from_dict(data)
        except Exception as e:
            logger.error(f"Error updating parameter {param_id} for function {function_id}: {str(e)}")
            raise

    async def get_contract(self, contract_id: str) -> Dict:
        """
        Obtiene un contrato de la base de datos por su ID
        """
        try:
            if not contract_id:
                raise ValueError("contract_id is required")
                
            # Usar la ruta correcta para obtener el contrato
            endpoint = f"{self.base_url}/agents/{contract_id}"
            logger.info(f"Obteniendo contrato {contract_id} desde {endpoint}")
            
            async with self.session.get(endpoint) as response:
                # Si falla con un 404, nos aseguramos de manejar ese caso específico
                if response.status == 404:
                    logger.warning(f"Contrato {contract_id} no encontrado (404)")
                    return None
                    
                # Para otros errores, lanzar la excepción
                response.raise_for_status()
                result = await response.json()
                
                # Si la respuesta es una lista, buscar el contrato con el ID correcto
                if isinstance(result, list):
                    logger.info(f"Recibida lista de {len(result)} contratos")
                    # Buscar el contrato específico con este ID
                    for contract in result:
                        if contract.get('contract_id') == contract_id:
                            logger.info(f"Contrato {contract_id} encontrado en la lista")
                            return contract
                    
                    # Si llegamos aquí, no se encontró el contrato en la lista
                    logger.warning(f"No se encontró el contrato {contract_id} en la lista de respuesta")
                    return None
                
                # Verificar si el contrato está envuelto en un objeto de respuesta
                if isinstance(result, dict):
                    if 'data' in result and result.get('success', False):
                        contract = result['data']
                        # Si data es una lista, procesar como arriba
                        if isinstance(contract, list):
                            for item in contract:
                                if item.get('contract_id') == contract_id:
                                    logger.info(f"Contrato {contract_id} encontrado en data")
                                    return item
                            logger.warning(f"No se encontró el contrato {contract_id} en data")
                            return None
                        return contract
                    
                    # Si el diccionario tiene contract_id y coincide
                    if result.get('contract_id') == contract_id:
                        return result
                
                logger.info(f"Contrato {contract_id} obtenido")
                return result
        except Exception as e:
            # Si hay un error de conexión o similar, no queremos que se propague
            if "404" in str(e):
                logger.warning(f"Contrato {contract_id} no encontrado: {str(e)}")
                return None
            logger.error(f"Error getting contract {contract_id}: {str(e)}")
            # No lanzamos la excepción, para permitir reintentos
            return None

    async def get_agent_schedule(self, agent_id: str) -> Optional[AgentSchedule]:
        """
        Obtiene la programación de un agente
        """
        try:
            # Usar la ruta correcta con 'schedules' en plural
            async with self.session.get(f"{self.base_url}/agents/{agent_id}/schedules") as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                data = await response.json()
                
                # Verificar si hay alguna programación
                if not data:
                    return None
                    
                # Si es una lista, tomar el primer elemento
                if isinstance(data, list):
                    if not data:
                        return None
                    data = data[0]
                    
                return AgentSchedule.from_dict(data)
        except Exception as e:
            logger.error(f"Error getting schedule for agent {agent_id}: {str(e)}")
            return None

    async def execute_contract_function(self, execution_data: Dict) -> Dict:
        """
        Ejecuta una función del contrato a través de la API REST
        
        Nota: Utiliza la URL de la API de contratos, no la URL de la base de datos
        """
        try:
            # Usar la URL de la API de contratos en lugar de la URL de la base de datos
            contract_endpoint = "/contracts/execute"
            if execution_data["type"] == "read":
                contract_endpoint = "/contracts/read"
            elif execution_data["type"] == "write" or execution_data["type"] == "payable":
                contract_endpoint = "/contracts/write"
                
            logger.info(f"Executing contract function: {execution_data['functionName']} via {CONTRACT_API_URL}{contract_endpoint}")
            
            async with self.session.post(f"{CONTRACT_API_URL}{contract_endpoint}", json=execution_data) as response:
                response.raise_for_status()
                result = await response.json()
                logger.info(f"Contract function execution result: {result}")
                return result
        except Exception as e:
            logger.error(f"Error executing contract function: {str(e)}")
            raise

    async def update_execution_log(self, agent_id: str, log_data: Dict) -> Dict:
        """
        Actualiza un registro de ejecución
        """
        try:
            # Formato correcto para la actualización de logs
            formatted_log_data = {
                "function_id": log_data.get("functionId"),
                "status": log_data.get("status", "success"),
                "execution_time": log_data.get("timestamp", datetime.utcnow().isoformat())
            }
            
            # Añadir campos adicionales según el resultado
            if log_data.get("status") == "success":
                # Para ejecuciones exitosas
                if "result" in log_data and isinstance(log_data["result"], dict):
                    # Si hay un hash de transacción en el resultado
                    if "transactionHash" in log_data["result"]:
                        formatted_log_data["transaction_hash"] = log_data["result"]["transactionHash"]
                    
                    # Si hay información de gas
                    if "gasUsed" in log_data["result"]:
                        formatted_log_data["gas_used"] = log_data["result"]["gasUsed"]
                    
                    if "gasPrice" in log_data["result"]:
                        formatted_log_data["gas_price"] = log_data["result"]["gasPrice"]
                
                # Incluir el resultado completo como datos adicionales
                if "result" in log_data:
                    formatted_log_data["result"] = log_data["result"]
                    
                # Incluir mensaje para casos de éxito si está presente
                if "message" in log_data:
                    formatted_log_data["error_message"] = log_data["message"]
            
            elif log_data.get("status") == "failed":
                # Para ejecuciones fallidas
                if "error" in log_data:
                    formatted_log_data["error"] = log_data["error"]
                    # Usar el mensaje de error como error_message si no hay mensaje específico
                    if "message" not in log_data:
                        formatted_log_data["error_message"] = log_data["error"]
                
                # Permitir mensajes personalizados que sustituyan el mensaje de error predeterminado
                if "message" in log_data:
                    formatted_log_data["error_message"] = log_data["message"]
            
            logger.info(f"Updating execution log for agent {agent_id} with data: {formatted_log_data}")
            
            # La ruta correcta es simplemente POST a /agents/{agent_id}/logs para actualizaciones también
            async with self.session.post(f"{self.base_url}/agents/{agent_id}/logs", json=formatted_log_data) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"Error updating execution log: {str(e)}")
            raise

    async def create_contract(self, contract_data: Dict) -> Dict:
        """
        Crea un contrato en la base de datos o devuelve el existente si ya existe
        """
        try:
            # Verificar campos obligatorios
            required_fields = ["contract_id", "address", "chain_id", "name", "type", "abi", "deployed_at", "owner_address"]
            for field in required_fields:
                if field not in contract_data:
                    raise ValueError(f"El campo {field} es obligatorio para crear un contrato")

            # Los datos ya vienen en snake_case del frontend, no necesitamos convertirlos
            logger.info(f"Creando contrato con datos: {json.dumps(contract_data)}")
            
            try:
                # Primero intentar obtener el contrato existente
                try:
                    existing_contract = await self.get_contract(contract_data["contract_id"])
                    if existing_contract:
                        logger.info(f"Contrato {contract_data['contract_id']} ya existe, retornando datos existentes")
                        return existing_contract
                except Exception as e:
                    if "404" not in str(e):  # Si el error no es 404 (no encontrado), propagarlo
                        raise
            
                # Si no existe, crear el contrato
                async with self.session.post(f"{self.base_url}/contracts/create", json=contract_data) as response:
                    if response.status == 500:
                        # Si es error 500, verificar si es por duplicado
                        error_text = await response.text()
                        if "UNIQUE constraint failed" in error_text:
                            # Intentar obtener el contrato existente nuevamente
                            logger.info(f"Contrato duplicado detectado, intentando obtener datos existentes")
                            try:
                                existing_contract = await self.get_contract(contract_data["contract_id"])
                                if existing_contract:
                                    return existing_contract
                            except Exception as get_error:
                                logger.error(f"Error obteniendo contrato existente: {str(get_error)}")
                                raise ValueError(f"El contrato existe pero no se pudo obtener: {str(get_error)}")
                        else:
                            # Si no es error de duplicado, propagar el error original
                            response.raise_for_status()
                    else:
                        # Si no es error 500, verificar otros códigos de estado
                        response.raise_for_status()
                        data = await response.json()
                        logger.info(f"Contrato creado correctamente: {json.dumps(data)}")
                        return data
            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    # Un último intento de obtener el contrato existente
                    try:
                        existing_contract = await self.get_contract(contract_data["contract_id"])
                        if existing_contract:
                            return existing_contract
                    except Exception:
                        pass
                raise
        except Exception as e:
            logger.error(f"Error creating contract: {str(e)}")
            raise

    async def create_agent(self, agent_data: Dict) -> Agent:
        """
        Crea un agente asociado a un contrato existente.
        Precondición: El contrato debe existir en la base de datos.
        """
        try:
            # Convertir contract_id a contractId si es necesario
            if 'contract_id' in agent_data and not agent_data.get('contractId'):
                agent_data['contractId'] = agent_data.pop('contract_id')
                logger.info(f"Converted contract_id to contractId in db_client: {agent_data['contractId']}")
            
            # Validar que los campos requeridos estén presentes
            required_fields = ["contractId", "name", "owner"]
            for field in required_fields:
                if not agent_data.get(field):
                    raise ValueError(f"{field} is required")
            
            # Obtener el ID del contrato
            contract_id = agent_data["contractId"]
            
            # En lugar de verificar el contrato de forma estricta primero,
            # continuamos con la creación del agente y dejamos que la API maneje
            # el error si el contrato no existe
            logger.info(f"Preparando datos para crear agente asociado al contrato {contract_id}")
            
            # Convertir de camelCase a snake_case para la API (según el patrón que hemos observado)
            api_data = {
                "agent_id": agent_data.get("agent_id"),  # Usar el ID enviado desde el frontend si existe
                "contractId": agent_data["contractId"],  # Mantener en camelCase como lo espera el API
                "name": agent_data["name"],
                "description": agent_data.get("description", ""),
                "status": agent_data.get("status", "paused"),
                "gas_limit": agent_data.get("gasLimit", agent_data.get("gas_limit", "300000")),
                "max_priority_fee": agent_data.get("maxPriorityFee", agent_data.get("max_priority_fee", "1.5")),
                "owner": agent_data["owner"],
                "contract_state": agent_data.get("contractState", agent_data.get("contract_state", {}))
            }
            
            logger.info(f"Creando/actualizando agente con datos: {json.dumps(api_data)}")  # Loguear api_data en lugar de agent_data
            
            # Implementar reintentos para creación de agente
            max_retries = 3
            retry_count = 0
            last_exception = None
            
            while retry_count < max_retries:
                try:
                    endpoint = f"{self.base_url}/agents"
                    
                    # Si existe agentId, intentar actualizar
                    if agent_data.get("agentId"):
                        endpoint = f"{endpoint}/{agent_data['agentId']}"
                        response = await self.session.put(endpoint, json=api_data)
                    else:
                        response = await self.session.post(endpoint, json=api_data)
                    
                    # Si el status es 400 o mayor pero no 404, podría ser un error temporal
                    if response.status >= 400 and response.status != 404:
                        error_text = await response.text()
                        logger.warning(f"Error al crear/actualizar agente (intento {retry_count + 1}/{max_retries}): {response.status} - {error_text}")
                        
                        # Si es error de clave foránea (contrato no existe), esperamos y reintentamos
                        if "FOREIGN KEY constraint failed" in error_text:
                            logger.info(f"Contrato {contract_id} posiblemente aún no sincronizado en la base de datos, esperando...")
                            retry_count += 1
                            await asyncio.sleep(1)
                            continue
                        
                        # Para otros errores, lanzar excepción
                        response.raise_for_status()
                    else:
                        # Procesar respuesta exitosa
                        response.raise_for_status()
                        break
                        
                except Exception as e:
                    logger.warning(f"Error en intento {retry_count + 1}/{max_retries}: {str(e)}")
                    last_exception = e
                    retry_count += 1
                    
                    # Solo esperamos y reintentamos si no hemos alcanzado el máximo
                    if retry_count < max_retries:
                        await asyncio.sleep(1)
                    else:
                        # Si es el último intento, relanzamos la excepción
                        raise e
            
            # Procesamos la respuesta (solo llegamos aquí si tuvimos éxito)
            result = await response.json()
            
            # Obtener valores manteniendo compatibilidad con ambos formatos (camelCase y snake_case)
            agent_id = result.get("agent_id", result.get("agentId", ""))
            contract_id = result.get("contract_id", result.get("contractId", ""))
            name = result.get("name", "")
            description = result.get("description", "")
            status = result.get("status", "")
            gas_limit = result.get("gas_limit", result.get("gasLimit", ""))
            max_priority_fee = result.get("max_priority_fee", result.get("maxPriorityFee", ""))
            owner = result.get("owner", "")
            contract_state = result.get("contract_state", result.get("contractState", {}))
            
            # Manejar created_at y updated_at como strings para evitar problemas con isoformat()
            created_at = result.get("created_at", result.get("createdAt", ""))
            updated_at = result.get("updated_at", result.get("updatedAt", ""))

            # Crear y devolver un objeto Agent
            agent = Agent(
                agent_id=agent_id,
                contract_id=contract_id,
                name=name,
                description=description,
                status=status,
                gas_limit=gas_limit,
                max_priority_fee=max_priority_fee,
                owner=owner,
                contract_state=contract_state,
                created_at=created_at,
                updated_at=updated_at
            )
            
            # Almacenar el ID del agente creado para uso posterior
            self.last_created_agent_id = agent_id
            logger.info(f"ID del agente almacenado para uso posterior: {self.last_created_agent_id}")
            
            return agent
            
        except Exception as e:
            logger.error(f"Error creating/updating agent: {str(e)}")
            raise

    async def create_agent_schedule(self, agent_id: str, schedule_data: Dict) -> AgentSchedule:
        """
        Crea una programación para un agente
        """
        try:
            if not agent_id:
                raise ValueError("agent_id is required")
            
            # Validar que los campos requeridos estén presentes
            schedule_type = schedule_data.get("schedule_type", schedule_data.get("scheduleType"))
            if not schedule_type:
                raise ValueError("schedule_type/scheduleType is required")
            
            # Si es tipo cron, verificar que haya expresión cron
            if schedule_type == "cron":
                cron_expression = schedule_data.get("cron_expression", schedule_data.get("cronExpression"))
                if not cron_expression:
                    raise ValueError("cron_expression/cronExpression is required for cron schedule type")
            
            # Usar snake_case para la API
            api_data = {
                "schedule_type": schedule_type,
                "cron_expression": schedule_data.get("cron_expression", schedule_data.get("cronExpression", "")),
                "is_active": schedule_data.get("is_active", schedule_data.get("isActive", True)),
                "next_execution": schedule_data.get("next_execution", schedule_data.get("nextExecution"))
            }
            
            logger.info(f"Creando programación para agente {agent_id} con datos: {json.dumps(schedule_data)}")
            
            # Manejamos reintentos
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # Para el primer intento, usamos el ID proporcionado
                    # Para reintentos, podemos probar con el ID del backend si está disponible
                    target_agent_id = agent_id
                    if retry_count > 0 and hasattr(self, 'last_created_agent_id') and self.last_created_agent_id:
                        target_agent_id = self.last_created_agent_id
                        logger.info(f"Reintento {retry_count+1}: Probando con el ID alternativo para schedule: {target_agent_id}")
                    
                    endpoint = f"{self.base_url}/agents/{target_agent_id}/schedules"
                    logger.info(f"POST a {endpoint}")
                    response = await self.session.post(endpoint, json=api_data)
                    
                    if response.status >= 400:
                        error_text = await response.text()
                        logger.warning(f"Error al crear programación (intento {retry_count + 1}/{max_retries}): {response.status} - {error_text}")
                        
                        # Si el error es de agente no encontrado, esperamos y reintentamos
                        if "not found" in error_text.lower() and "agent" in error_text.lower():
                            logger.info(f"Agente {agent_id} posiblemente aún no sincronizado, esperando...")
                            retry_count += 1
                            await asyncio.sleep(1)
                            continue
                            
                        # Para otros errores, lanzar excepción
                        response.raise_for_status()
                    else:
                        # Proceso exitoso
                        response.raise_for_status()
                        break
                
                except Exception as e:
                    logger.warning(f"Error en intento {retry_count + 1}/{max_retries}: {str(e)}")
                    retry_count += 1
                    
                    if retry_count < max_retries:
                        await asyncio.sleep(1)
                    else:
                        raise e
            
            result = await response.json()
            
            # Obtener valores manteniendo compatibilidad con ambos formatos (camelCase y snake_case)
            schedule_id = result.get("schedule_id", result.get("scheduleId", ""))
            agent_id = result.get("agent_id", result.get("agentId", ""))
            schedule_type = result.get("schedule_type", result.get("scheduleType", ""))
            cron_expression = result.get("cron_expression", result.get("cronExpression", ""))
            is_active = result.get("is_active", result.get("isActive", True))
            next_execution = result.get("next_execution", result.get("nextExecution"))
            created_at = result.get("created_at", result.get("createdAt", ""))
            updated_at = result.get("updated_at", result.get("updatedAt", ""))
            
            # Crear objeto AgentSchedule
            schedule = AgentSchedule(
                schedule_id=schedule_id,
                agent_id=agent_id,
                schedule_type=schedule_type,
                cron_expression=cron_expression,
                is_active=is_active,
                next_execution=next_execution,
                created_at=created_at,
                updated_at=updated_at
            )
            
            return schedule
            
        except Exception as e:
            logger.error(f"Error creating schedule for agent {agent_id}: {str(e)}")
            raise

    async def create_agent_notification(self, agent_id: str, notification_data: Dict) -> Dict:
        """
        Crea una notificación para un agente
        """
        try:
            # Verificar campos obligatorios
            required_fields = ["notification_type", "configuration"]
            for field in required_fields:
                if field not in notification_data:
                    raise ValueError(f"El campo {field} es obligatorio para crear una notificación")

            # Convertir los datos a snake_case como espera el backend
            api_data = {
                "notification_type": notification_data.get("notification_type", notification_data.get("notificationType")),
                "configuration": notification_data["configuration"],
                "is_enabled": notification_data.get("is_enabled", notification_data.get("isEnabled", True))
            }
            
            # Registrar los datos que estamos enviando para depuración
            logger.info(f"Creando notificación para agente {agent_id} con datos: {json.dumps(api_data)}")
            
            # Implementar reintentos para manejar posibles problemas de sincronización
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # Para el primer intento, usamos el ID proporcionado
                    # Para reintentos, podemos probar con el ID del backend si está disponible
                    target_agent_id = agent_id
                    if retry_count > 0 and hasattr(self, 'last_created_agent_id') and self.last_created_agent_id:
                        target_agent_id = self.last_created_agent_id
                        logger.info(f"Reintento {retry_count+1}: Probando con el ID alternativo para notificación: {target_agent_id}")
                    
                    endpoint = f"{self.base_url}/agents/{target_agent_id}/notifications"
                    logger.info(f"POST a {endpoint}")
                    
                    async with self.session.post(endpoint, json=api_data) as response:
                        if response.status >= 400:
                            error_text = await response.text()
                            logger.warning(f"Error al crear notificación (intento {retry_count + 1}/{max_retries}): {response.status} - {error_text}")
                            retry_count += 1
                            
                            if retry_count < max_retries:
                                await asyncio.sleep(1)
                                continue
                            else:
                                response.raise_for_status()
                        
                        data = await response.json()
                        break
                except Exception as e:
                    logger.warning(f"Error en intento {retry_count + 1}/{max_retries}: {str(e)}")
                    retry_count += 1
                    
                    if retry_count < max_retries:
                        await asyncio.sleep(1)
                    else:
                        raise e
            
            # Adaptar la respuesta de la API al formato esperado
            notification_response = {
                "notificationId": data.get("notification_id"),
                "agentId": target_agent_id,  # Usar el ID que funcionó
                "notificationType": data.get("notification_type"),
                "configuration": data.get("configuration", {}),
                "isEnabled": data.get("is_enabled", True),
                "created_at": data.get("created_at", datetime.now().isoformat()),
                "updated_at": data.get("updated_at", datetime.now().isoformat())
            }
            
            return notification_response
        except Exception as e:
            logger.error(f"Error creating notification for agent {agent_id}: {str(e)}")
            raise 