from typing import Dict, List, Optional, Any
import json
import asyncio
from datetime import datetime
import logging
from openai import AsyncOpenAI
from pydantic import BaseModel
from src.utils.logger import setup_logger
from src.api.db_client import DatabaseClient
from src.models.agent import Agent, AgentFunction, AgentFunctionParam, AgentSchedule
import os
import re

logger = setup_logger(__name__)

class AutonomousAgent:
    """
    An autonomous agent that executes pre-configured behaviors on smart contracts.
    Uses OpenAI GPT to analyze state and determine actions based on the agent's description.
    """
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.agent: Optional[Agent] = None
        self.functions: List[AgentFunction] = []
        self.schedule: Optional[AgentSchedule] = None
        self.is_running = False
        self.openai_client = None
        self.contract_abi = None
        self.contract_address = None

    @classmethod
    async def from_config(cls, config_data: Dict) -> 'AutonomousAgent':
        """
        Crea una instancia de AutonomousAgent desde la configuración del frontend
        """
        async with DatabaseClient() as db_client:
            try:
                # Validar la configuración
                if not isinstance(config_data, dict):
                    raise ValueError("Configuration data must be a dictionary")

                logger.info(f"Procesando configuración recibida: {json.dumps(config_data)}")

                # 1. Extraer la información del contrato
                if 'contract' not in config_data:
                    raise ValueError("Missing contract configuration")
                
                contract_data = config_data['contract']
                
                # Determinar el ID del contrato según el tipo de datos
                contract_id = None
                if isinstance(contract_data, dict):
                    contract_id = contract_data.get('contract_id')
                elif isinstance(contract_data, str):
                    contract_id = contract_data
                
                if not contract_id:
                    raise ValueError("No se pudo determinar el ID del contrato")
                    
                logger.info(f"Usando contrato con ID {contract_id}")
                
                # Para nuestro propósito de prueba, asumimos que el contrato ya existe
                # y no necesitamos crearlo de nuevo
                
                # 2. Crear el agente (o usar uno existente si se proporciona agent_id)
                agent_id = config_data.get('agent_id')
                if agent_id:
                    logger.info(f"Usando agente existente con ID {agent_id}")
                    instance = cls(agent_id)
                    instance.agent = await db_client.get_agent(agent_id)
                    if not instance.agent:
                        raise ValueError(f"No se encontró el agente con ID {agent_id}")
                else:
                    if 'agent' not in config_data:
                        raise ValueError("Missing agent configuration")
                    
                    agent_data = config_data['agent']
                    logger.info(f"Creando nuevo agente con datos: {json.dumps(agent_data)}")
                    instance = cls(agent_data.get('agentId', ''))
                    try:
                        instance.agent = await db_client.create_agent(agent_data)
                        logger.info(f"Agente creado correctamente con ID: {instance.agent.agent_id}")
                    except Exception as agent_error:
                        logger.error(f"Error al crear el agente: {str(agent_error)}")
                        raise ValueError(f"No se pudo crear el agente: {str(agent_error)}")

                # 3. Cargar o crear las funciones
                instance.functions = []
                if 'functions' in config_data and config_data['functions']:
                    for function_data in config_data['functions']:
                        try:
                            # Si estamos cargando un agente existente, no creamos nuevas funciones
                            if agent_id:
                                function = AgentFunction.from_dict(function_data)
                            else:
                                function = await db_client.create_agent_function(instance.agent.agent_id, function_data)
                            instance.functions.append(function)
                            logger.info(f"Función {function.function_name} procesada")
                        except Exception as function_error:
                            logger.error(f"Error al procesar función: {str(function_error)}")
                            # Continuamos con otras funciones a pesar del error
                else:
                    # Si no se proporcionan funciones, cargar las existentes para el agente
                    logger.info(f"Cargando funciones existentes para el agente {instance.agent_id}")
                    instance.functions = await db_client.get_agent_functions(instance.agent_id)
                    
                # 4. Procesar la programación
                instance.schedule = None
                if 'schedule' in config_data and config_data['schedule']:
                    try:
                        schedule_data = config_data['schedule']
                        if agent_id:
                            # Si estamos cargando un agente existente, simplemente convertimos los datos
                            instance.schedule = AgentSchedule.from_dict(schedule_data)
                        else:
                            # Si estamos creando un nuevo agente, registramos la programación
                            instance.schedule = await db_client.create_agent_schedule(instance.agent.agent_id, schedule_data)
                        logger.info(f"Programación procesada correctamente")
                    except Exception as schedule_error:
                        logger.error(f"Error al procesar programación: {str(schedule_error)}")
                else:
                    # Intentar cargar la programación existente
                    instance.schedule = await db_client.get_agent_schedule(instance.agent_id)

                # Inicializar el cliente de OpenAI
                instance.openai_client = AsyncOpenAI()
                
                return instance
                
            except Exception as e:
                logger.error(f"Error en from_config: {str(e)}")
                raise ValueError(f"Error configurando el agente: {str(e)}")

    async def initialize(self):
        """
        Inicializa el agente cargando su configuración, funciones y datos del contrato
        """
        async with DatabaseClient() as db_client:
            try:
                # Cargar configuración del agente
                self.agent = await db_client.get_agent(self.agent_id)
                if not self.agent:
                    raise ValueError(f"Agent {self.agent_id} not found in database")

                # Cargar datos del contrato
                contract = await db_client.get_contract(self.agent.contract_id)
                if not contract:
                    raise ValueError(f"Contract {self.agent.contract_id} not found")
                
                # Inicializar el cliente de OpenAI
                try:
                    from openai import OpenAI
                    api_key = os.environ.get("OPENAI_API_KEY")
                    if not api_key:
                        logger.warning("No OPENAI_API_KEY found in environment variables")
                    else:
                        self.openai_client = OpenAI(api_key=api_key)
                        logger.info("OpenAI client initialized successfully")
                except ImportError:
                    logger.error("OpenAI package not installed. Please install with: pip install openai")
                except Exception as e:
                    logger.error(f"Error initializing OpenAI client: {str(e)}")
                
                # Acceder al ABI como clave en el diccionario
                self.contract_abi = contract.get('abi', None)
                if not self.contract_abi:
                    logger.warning(f"Contract {self.agent.contract_id} does not have ABI field. Contract data: {contract}")
                    # Intentar buscar el ABI en otras ubicaciones posibles
                    if 'contract_abi' in contract:
                        self.contract_abi = contract['contract_abi']
                        logger.info(f"Using 'contract_abi' field instead")
                
                # Acceder a la dirección como clave en el diccionario
                self.contract_address = contract.get('address', None)
                if not self.contract_address:
                    logger.warning(f"Contract {self.agent.contract_id} does not have address field")
                    # Si no hay dirección específica, usar el contract_id como dirección
                    self.contract_address = self.agent.contract_id
                
                logger.info(f"Contract {self.agent.contract_id} loaded: Address={self.contract_address}, ABI available: {self.contract_abi is not None}")

                # Cargar funciones del agente
                self.functions = await db_client.get_agent_functions(self.agent_id)
                
                # Cargar parámetros de las funciones (si están disponibles)
                for function in self.functions:
                    try:
                        function.params = await db_client.get_function_params(function.function_id)
                    except Exception as func_err:
                        # Si hay error obteniendo los parámetros, logueamos pero no fallamos
                        logger.warning(f"Couldn't load parameters for function {function.function_name}: {str(func_err)}")
                        function.params = []  # Inicializamos con lista vacía
                
                # Cargar programación del agente (si está disponible)
                try:
                    self.schedule = await db_client.get_agent_schedule(self.agent_id)
                except Exception as schedule_err:
                    logger.warning(f"Couldn't load schedule for agent {self.agent_id}: {str(schedule_err)}")
                    self.schedule = None
                
                logger.info(f"Agent {self.agent_id} initialized with {len(self.functions)} functions")
                
            except Exception as e:
                logger.error(f"Error initializing agent {self.agent_id}: {str(e)}")
                raise ValueError(f"Error initializing agent {self.agent_id}: {str(e)}")

    async def add_function(self, function_data: Dict) -> AgentFunction:
        """
        Agrega una nueva función al agente
        """
        async with DatabaseClient() as db_client:
            function = await db_client.create_agent_function(self.agent_id, function_data)
            self.functions.append(function)
            return function

    async def update_function(self, function_id: str, function_data: Dict) -> Optional[AgentFunction]:
        """
        Actualiza una función existente del agente
        """
        async with DatabaseClient() as db_client:
            function = await db_client.update_agent_function(self.agent_id, function_id, function_data)
            if function:
                # Actualizar la función en la lista local
                self.functions = [f for f in self.functions if f.function_id != function_id]
                self.functions.append(function)
            return function

    async def add_function_param(self, function_id: str, param_data: Dict) -> AgentFunctionParam:
        """
        Agrega un nuevo parámetro a una función
        """
        async with DatabaseClient() as db_client:
            param = await db_client.create_function_param(function_id, param_data)
            # Actualizar los parámetros en la función local
            for function in self.functions:
                if function.function_id == function_id:
                    if not hasattr(function, 'params'):
                        function.params = []
                    function.params.append(param)
            return param

    async def update_function_param(self, function_id: str, param_id: str, param_data: Dict) -> Optional[AgentFunctionParam]:
        """
        Actualiza un parámetro existente de una función
        """
        async with DatabaseClient() as db_client:
            param = await db_client.update_function_param(function_id, param_id, param_data)
            if param:
                # Actualizar el parámetro en la función local
                for function in self.functions:
                    if function.function_id == function_id and hasattr(function, 'params'):
                        function.params = [p for p in function.params if p.param_id != param_id]
                        function.params.append(param)
            return param

    async def validate_params(self, function: AgentFunction, params: Dict) -> bool:
        """
        Valida los parámetros de una función contra sus reglas de validación
        """
        if not hasattr(function, 'params'):
            return True

        for param in function.params:
            if param.param_name not in params and not param.default_value:
                logger.error(f"Missing required parameter: {param.param_name}")
                return False

            value = params.get(param.param_name, param.default_value)
            if param.validation_rules:
                # TODO: Implementar validación de reglas específicas
                pass

        return True

    async def execute_function(self, function: AgentFunction, params: Optional[Dict] = None, message: Optional[str] = None):
        """
        Ejecuta una función del agente
        
        Args:
            function: La función a ejecutar
            params: Los parámetros para la función (opcional)
            message: Mensaje opcional para incluir en el registro de ejecución
            
        Returns:
            El resultado de la ejecución
        """
        try:
            if not params:
                params = {}
            
            # Validar parámetros según reglas
            if not await self.validate_params(function, params):
                raise ValueError(f"Invalid parameters for function {function.function_name}")
            
            logger.info(f"Executing function {function.function_name} for agent {self.agent_id}")
            logger.info(f"Executing function {function.function_name} with params: {params}")
            
            # Determinar qué ABI usar para la función
            contract_address = self.agent.contract_id
            abi_to_use = None
            
            # Primero intentar usar el ABI específico de la función
            if function.abi:
                abi_to_use = function.abi
            
            # Si no hay ABI específico, usar el del contrato completo
            if not abi_to_use and self.contract_abi:
                logger.warning(f"Function {function.function_name} does not have ABI, using contract ABI")
                abi_to_use = self.contract_abi
                
            if not abi_to_use:
                raise ValueError(f"No ABI available for function {function.function_name}")
                
            # Construir el ABI completo para la API si solo tenemos la definición de la función
            if isinstance(abi_to_use, dict):
                # Si es solo la definición de una función, la envolvemos en un array
                abi_to_use = [abi_to_use]
            
            # Preparar datos para la API REST según el formato requerido por /api/contracts/read o /api/contracts/write
            execution_data = {
                "contractAddress": contract_address,
                "abi": abi_to_use,  # ABI completo para la función
                "functionName": function.function_name,
                "inputs": list(params.values()) if isinstance(params, dict) else params
            }
            
            # El tipo se usa internamente para dirigir a /read o /write pero no se envía en la solicitud
            internal_type = function.function_type
            
            # Añadir parámetros de gas solo para funciones de escritura
            if function.function_type in ['write', 'payable']:
                execution_data["gasLimit"] = self.agent.gas_limit
                execution_data["maxPriorityFee"] = self.agent.max_priority_fee

            logger.info(f"Executing function {function.function_name} with params: {params}")
            logger.debug(f"Execution data: {execution_data}")

            # Intentar registrar la ejecución, pero continuar incluso si falla
            log_entry = None
            try:
                async with DatabaseClient() as db_client:
                    log_data = {
                        "functionId": function.function_id,
                        "status": "pending",
                        "params": params,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    # Incluir mensaje si se proporciona
                    if message:
                        log_data["message"] = message
                        
                    log_entry = await db_client.create_execution_log(
                        self.agent_id,
                        log_data
                    )
            except Exception as log_err:
                logger.warning(f"Could not create execution log: {str(log_err)}")
                # Continuar con la ejecución aún sin poder registrar el log

            # Ejecutar a través de la API REST
            async with DatabaseClient() as db_client:
                # Pasamos el tipo internamente para dirigir a la API correcta
                execution_data["type"] = internal_type
                result = await db_client.execute_contract_function(execution_data)
                
                # Intentar actualizar el registro si se creó correctamente, pero no fallar si no se puede
                if log_entry:
                    try:
                        log_data = {
                            "functionId": function.function_id,
                            "status": "success",
                            "result": result,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        
                        # Incluir mensaje si se proporciona
                        if message:
                            log_data["message"] = message
                            
                        await db_client.update_execution_log(
                            self.agent_id,
                            log_data
                        )
                    except Exception as update_err:
                        logger.warning(f"Could not update execution log: {str(update_err)}")

            logger.info(f"Function {function.function_name} executed successfully, result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error executing function {function.function_name}: {str(e)}", exc_info=True)
            
            # Intentar registrar el error, pero no fallar si no se puede
            try:
                async with DatabaseClient() as db_client:
                    log_data = {
                        "functionId": function.function_id,
                        "status": "failed",
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    # Incluir mensaje si se proporciona, sino usar el error como mensaje
                    if message:
                        log_data["message"] = message
                        
                    await db_client.update_execution_log(
                        self.agent_id,
                        log_data
                    )
            except Exception as log_err:
                logger.warning(f"Could not log execution error: {str(log_err)}")
            
            raise

    def _validate_params_with_abi(self, function: AgentFunction, params: Dict) -> bool:
        """
        Valida los parámetros contra el ABI de la función
        """
        try:
            abi_inputs = function.abi['inputs']
            
            # Verificar que todos los parámetros requeridos estén presentes
            for input_param in abi_inputs:
                param_name = input_param['name']
                if param_name not in params:
                    logger.error(f"Missing required parameter: {param_name}")
                    return False
                
                # TODO: Implementar validación de tipos según el ABI
                # Por ahora solo verificamos presencia

            return True
            
        except Exception as e:
            logger.error(f"Error validating parameters: {str(e)}")
            return False

    async def analyze_and_execute(self, trigger_data: Dict):
        """
        Analiza el estado actual y determina qué funciones ejecutar
        
        Args:
            trigger_data: Datos sobre el disparador de ejecución
        
        Returns:
            Lista de resultados de ejecución
        """
        try:
            # Obtener el estado actual del contrato
            state = self.agent.contract_state if self.agent and self.agent.contract_state else {}
            
            # Analizar el estado y determinar acciones iniciales
            actions = await self.analyze_state(state, trigger_data)
            
            if not actions:
                logger.info(f"No actions determined for agent {self.agent_id}")
                return []
            
            # Lista para guardar todos los resultados de ejecución
            all_results = []
            
            # Historial de ejecución para mostrar al modelo en iteraciones posteriores
            execution_history = []
            
            # Límite de ciclos para evitar loops infinitos
            max_cycles = 5
            current_cycle = 0
            
            # Bucle para ejecutar acciones y analizar resultados
            while actions and current_cycle < max_cycles:
                current_cycle += 1
                logger.info(f"Starting execution cycle {current_cycle}/{max_cycles}")
                
                # Ejecutar las acciones determinadas
                cycle_results = []
                for action in actions:
                    try:
                        function_name = action.get('function')
                        params = action.get('params', {})
                        message = action.get('message')  # Extraer mensaje del modelo para esta acción
                        
                        # Buscar la función en las funciones configuradas del agente
                        matching_function = None
                        for func in self.functions:
                            if func.function_name == function_name:
                                matching_function = func
                                break
                        
                        if not matching_function:
                            logger.warning(f"Function {function_name} not found in agent configuration")
                            continue
                        
                        # Ejecutar la función
                        logger.info(f"Executing function {function_name} with params {params}")
                        result = await self.execute_function(matching_function, params, message)
                        
                        # Guardar resultado para devolver y para el historial
                        execution_result = {
                            "function": function_name,
                            "params": params,
                            "result": result,
                            "message": message
                        }
                        
                        cycle_results.append(execution_result)
                        all_results.append(execution_result)
                        execution_history.append(execution_result)
                        
                    except Exception as e:
                        logger.error(f"Error executing action {action}: {str(e)}")
                        error_result = {
                            "function": action.get('function'),
                            "params": action.get('params', {}),
                            "error": str(e),
                            "message": action.get('message')
                        }
                        cycle_results.append(error_result)
                        all_results.append(error_result)
                        execution_history.append(error_result)
                
                # Si ya hemos alcanzado el número máximo de ciclos, terminar
                if current_cycle >= max_cycles:
                    logger.warning(f"Reached maximum number of execution cycles ({max_cycles})")
                    break
                
                # Analizar los resultados para determinar acciones adicionales
                actions = await self.analyze_results(state, trigger_data, execution_history)
                
                if not actions:
                    logger.info(f"No further actions needed after cycle {current_cycle}")
                    break
            
            return all_results
            
        except Exception as e:
            logger.error(f"Error in analyze_and_execute for agent {self.agent_id}: {str(e)}")
            raise
            
    async def analyze_results(self, state: Dict, trigger_data: Dict, execution_history: List[Dict]) -> List[Dict]:
        """
        Analiza los resultados de las ejecuciones previas para determinar acciones adicionales
        
        Args:
            state: Estado actual del contrato
            trigger_data: Datos del disparador de ejecución
            execution_history: Historial de ejecuciones previas
        
        Returns:
            Lista de acciones adicionales a ejecutar
        """
        # Construir la lista de funciones con información detallada
        functions_info = []
        for f in self.functions:
            if f.is_enabled:
                function_info = {
                    'name': f.function_name,
                    'type': f.function_type,
                    'signature': f.function_signature,
                    'enabled': f.is_enabled,
                    'abi': f.abi
                }
                
                # Añadir detalles sobre los parámetros requeridos
                if f.abi and 'inputs' in f.abi:
                    function_info['required_params'] = [
                        {
                            'name': input_param.get('name'),
                            'type': input_param.get('type'),
                            'description': f"Parameter of type {input_param.get('type')}"
                        }
                        for input_param in f.abi['inputs']
                        if 'name' in input_param
                    ]
                
                functions_info.append(function_info)
        
        prompt = f"""
        Current contract state:
        {json.dumps(state, indent=2)}
        
        Trigger event data:
        {json.dumps(trigger_data, indent=2)}
        
        Agent description (behavior):
        {self.agent.description}
        
        Contract current state:
        {json.dumps(self.agent.contract_state, indent=2)}
        
        Available functions:
        {json.dumps(functions_info, indent=2)}
        
        Previous execution results:
        {json.dumps(execution_history, indent=2)}
        
        Based on the previous execution results, the current state, and the agent's behavior description,
        determine if additional actions are needed.
        
        If the previous results indicate that further actions are required according to the agent's description,
        return those actions as function calls with appropriate parameters.
        
        If no further actions are needed, respond with an empty array.
        
        You MUST include a 'message' field with each function call to provide comments or explanations about the execution.
        These messages will be stored in the execution logs and shown to users, serving as your communication channel.
        
        IMPORTANT INSTRUCTIONS FOR GENERATING PARAMETERS:
        1. Always use the function_call feature to respond. DO NOT respond with text.
        2. Always include a meaningful message explaining what you're doing and why.
        3. YOU are FULLY RESPONSIBLE for generating ALL parameter values - there is NO fallback system.
        4. Analyze each function's required parameters from its ABI and generate appropriate values for EVERY parameter.
        5. Generate parameter values based on:
           - The parameter's type (address, uint256, string, etc.)
           - The agent's description which contains hints about what values to use
           - The context of what the function is supposed to do
           - Any specific instructions or ranges mentioned in the description
        
        6. For specific parameter types:
           - For addresses: Use Ethereum addresses mentioned in the description, or the contract address if appropriate
           - For uint/int values: Generate sensible numeric values based on the context
           - For strings: Create appropriate text values that match the context
           - For booleans: Determine true/false based on the agent's purpose
        
        7. If the agent description mentions random or varied values (like "random amount between X and Y"),
           you should generate an appropriate random value within that range.
           
        8. Make sure all generated values are correctly formatted for their type:
           - Addresses must start with 0x and be 42 characters long
           - Numeric values should be appropriate integers (not too large or small)
           - Strings should be meaningful and contextually appropriate
        
        9. The parameters object MUST include ALL required fields with their correct names as defined in the ABI.
        
        10. The agent has NO capability to extract or generate values on its own - YOU must provide ALL parameter values.
        
        Remember: You have full authority and responsibility to decide appropriate parameter values based on context.
        """
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an autonomous agent managing a smart contract. You generate appropriate parameter values for function calls based on context and function specifications."},
                {"role": "user", "content": prompt}
            ],
            functions=[{
                "name": "execute_contract_function",
                "description": "Execute a function on the smart contract",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "function_name": {"type": "string"},
                        "parameters": {"type": "object"},
                        "message": {"type": "string", "description": "Optional message or comment to include in the execution log"}
                    },
                    "required": ["function_name", "parameters", "message"]
                }
            }]
        )
        
        return self._parse_openai_response(response)

    def _parse_openai_response(self, response) -> List[Dict]:
        """
        Parsea la respuesta de OpenAI para extraer acciones
        
        Returns:
            Lista de acciones con los campos 'function', 'params' y opcionalmente 'message'
        """
        try:
            # Verificar si hay una llamada a función en la respuesta
            if response.choices[0].message.function_call:
                function_call = response.choices[0].message.function_call
                
                # Si es una llamada a execute_contract_function, extraer los datos
                if function_call.name == "execute_contract_function":
                    args = json.loads(function_call.arguments)
                    function_name = args.get("function_name")
                    parameters = args.get("parameters", {})
                    
                    # Crear la acción en el formato esperado
                    action = {
                        "function": function_name,
                        "params": parameters
                    }
                    
                    # Incluir mensaje si está presente
                    if "message" in args:
                        action["message"] = args["message"]
                    else:
                        # Generar un mensaje genérico si no se proporcionó uno
                        action["message"] = f"Executing function {function_name} with parameters {json.dumps(parameters)}"
                        
                    return [action]  # Devolver como lista
            
            # Si no hay llamada a función, intentar parsear del contenido
            content = response.choices[0].message.content
            if not content:
                return []
                
            # Intentar extraer acciones en formato JSON
            try:
                # Buscar el patrón ```json ... ``` para extraer las acciones
                json_pattern = r"```json\s*([\s\S]*?)\s*```"
                match = re.search(json_pattern, content)
                
                if match:
                    json_str = match.group(1)
                    actions = json.loads(json_str)
                    
                    # Si es un único diccionario, convertirlo a lista
                    if isinstance(actions, dict):
                        actions = [actions]
                    
                    # Validar estructura de acciones y asegurar campos requeridos
                    validated_actions = []
                    for action in actions:
                        if "function" in action and isinstance(action, dict):
                            function_name = action["function"]
                            original_params = action.get("params", {})
                            
                            # Completar parámetros faltantes
                            completed_params = self._complete_missing_parameters(function_name, original_params)
                            
                            validated_action = {
                                "function": function_name,
                                "params": completed_params
                            }
                            
                            # Incluir el mensaje si está presente
                            if "message" in action:
                                validated_action["message"] = action["message"]
                            else:
                                # Generar un mensaje genérico
                                validated_action["message"] = f"Executing function {function_name} with parameters {json.dumps(completed_params)}"
                                
                            validated_actions.append(validated_action)
                    
                    return validated_actions
            except Exception as json_err:
                logger.warning(f"Error parsing JSON from OpenAI response: {str(json_err)}")
            
            # Si no se pudo extraer JSON, intentar hacer parsing de texto
            logger.info("Attempting to parse actions from plain text")
            
            # Buscar patrones de llamadas a funciones en el texto
            function_pattern = r"(?:Execute|Call|Run|Invoke|Use)\s+(?:function|method)?\s*['\"]?(\w+)['\"]?"
            function_matches = re.finditer(function_pattern, content, re.IGNORECASE)
            
            actions = []
            for match in function_matches:
                function_name = match.group(1)
                
                # Buscar la función en las funciones disponibles
                matching_function = None
                for func in self.functions:
                    if func.function_name == function_name:
                        matching_function = func
                        break
                
                if not matching_function:
                    continue
                
                # Extraer parámetros del texto o completarlos basados en el ABI
                params = self._extract_params_from_text(content, matching_function)
                
                # Generar un mensaje basado en el texto o un mensaje genérico
                message_match = re.search(r"(?:Mensaje|Message|Comentario|Comment):\s*(.+?)(?=\n\n|\n(?:Execute|Call|Run|Invoke|Use)|\Z)", 
                                         content[match.end():], re.IGNORECASE)
                message = message_match.group(1).strip() if message_match else f"Executing {function_name} based on agent description"
                
                # Crear acción
                action = {
                    "function": function_name,
                    "params": params,
                    "message": message
                }
                
                actions.append(action)
            
            # Si no se encontraron acciones en el texto pero hay una descripción clara,
            # intentar inferir acciones basadas en la descripción del agente
            if not actions and self.agent and self.agent.description:
                actions = self._infer_actions_from_description()
            
            return actions
                
        except Exception as e:
            logger.error(f"Error parsing OpenAI response: {str(e)}")
            return []
            
    def _complete_missing_parameters(self, function_name: str, provided_params: Dict) -> Dict:
        """
        Completa parámetros faltantes para una función basándose en la descripción del agente.
        Este método es totalmente genérico y no hace referencias a nombres específicos.
        La generación de valores complejos es delegada completamente al modelo.
        """
        # Buscar la función específica
        matching_function = next((f for f in self.functions if f.function_name == function_name), None)
        if not matching_function:
            logger.warning(f"Function {function_name} not found in agent functions")
            return provided_params
            
        # Copia de los parámetros proporcionados
        completed_params = provided_params.copy()
        
        # Obtener los parámetros esperados desde el ABI
        if 'inputs' in matching_function.abi:
            expected_inputs = matching_function.abi['inputs']
            
            # Si no hay parámetros proporcionados pero se requieren, intentar extraerlos de la descripción
            if not completed_params and expected_inputs:
                logger.info(f"No parameters provided for {function_name}, attempting to extract from description")
                return self._extract_params_from_description(matching_function)
                
            # Verificar si faltan parámetros requeridos (enfoque genérico)
            for input_param in expected_inputs:
                param_name = input_param.get('name')
                if param_name and param_name not in completed_params:
                    # Intentar obtener el valor del parámetro de la descripción 
                    param_value = self._extract_param_value_from_description(param_name, input_param.get('type'))
                    if param_value is not None:
                        completed_params[param_name] = param_value
                        logger.info(f"Added parameter {param_name}={param_value} for function {function_name}")
        
        return completed_params
        
    def _extract_params_from_description(self, function: AgentFunction) -> Dict:
        """
        Extrae parámetros para una función basándose en la descripción del agente.
        Este método es genérico y solo extrae información básica de la descripción.
        La generación de valores específicos para parámetros es delegada al modelo.
        """
        params = {}
        
        if not function.abi or 'inputs' not in function.abi:
            return params
            
        expected_inputs = function.abi['inputs']
        
        # Proceso general para todas las funciones
        for input_param in expected_inputs:
            param_name = input_param.get('name')
            param_type = input_param.get('type')
            
            if param_name:
                # Intentar extraer el valor basado en el tipo
                param_value = self._extract_param_value_from_description(param_name, param_type)
                if param_value is not None:
                    params[param_name] = param_value
        
        return params
        
    def _extract_param_value_from_description(self, param_name: str, param_type: str) -> Optional[Any]:
        """
        Extrae un valor de parámetro genérico de la descripción del agente.
        Este método es básico y solo captura información simple.
        La generación de valores complejos es totalmente delegada al modelo.
        """
        if not self.agent or not self.agent.description:
            return None
            
        description = self.agent.description.lower()
        param_name_lower = param_name.lower()
        
        # Buscar por tipo sin referencias a nombres específicos
        if param_type == 'address':
            # Buscar direcciones Ethereum en la descripción
            address_match = re.search(r'0x[a-fA-F0-9]{40}', self.agent.description)
            if address_match:
                return address_match.group(0)
                
        # Buscar números para parámetros numéricos (genérico)
        if param_type and ('int' in param_type or 'uint' in param_type):
            # Buscar contexto relacionado con el nombre del parámetro
            context_pattern = fr'(?:{param_name_lower}).+?(\d+)'
            num_match = re.search(context_pattern, description)
            if num_match:
                value = num_match.group(1)
                return int(value)
                
        # Buscar booleanos
        if param_type == 'bool':
            true_pattern = fr'(?:{param_name_lower}).+?(?:true|yes|enable|enabled|active)'
            false_pattern = fr'(?:{param_name_lower}).+?(?:false|no|disable|disabled|inactive)'
            
            if re.search(true_pattern, description, re.IGNORECASE):
                return True
            elif re.search(false_pattern, description, re.IGNORECASE):
                return False
                
        return None
        
    def _extract_params_from_text(self, text: str, function: AgentFunction) -> Dict:
        """
        Extrae parámetros para una función desde un texto libre
        """
        params = {}
        
        if not function.abi or 'inputs' not in function.abi:
            return params
            
        # Buscar parámetros en el texto
        for input_param in function.abi['inputs']:
            param_name = input_param.get('name')
            param_type = input_param.get('type')
            
            if not param_name:
                continue
                
            # Patrones de búsqueda basados en el tipo
            if param_type == 'address':
                # Buscar direcciones mencionadas cerca del nombre del parámetro
                address_pattern = fr'(?:{param_name}|address|wallet).+?(0x[a-fA-F0-9]{{40}})'
                address_match = re.search(address_pattern, text, re.IGNORECASE)
                
                if address_match:
                    params[param_name] = address_match.group(1)
                else:
                    # Buscar cualquier dirección en el texto
                    any_address = re.search(r'0x[a-fA-F0-9]{40}', text)
                    if any_address:
                        params[param_name] = any_address.group(0)
            
            # Para otros tipos, usar la extracción basada en la descripción del agente
            else:
                param_value = self._extract_param_value_from_description(param_name, param_type)
                if param_value is not None:
                    params[param_name] = param_value
                    
        return params
        
    def _infer_actions_from_description(self) -> List[Dict]:
        """
        Infiere acciones basadas en la descripción del agente cuando no hay respuesta clara del modelo
        """
        actions = []
        
        if not self.agent or not self.agent.description:
            return actions
            
        description = self.agent.description.lower()
        
        # Buscar menciones de funciones en la descripción
        for function in self.functions:
            if function.is_enabled and function.function_name.lower() in description:
                # Extraer parámetros para esta función
                params = self._extract_params_from_description(function)
                
                # Crear un mensaje genérico
                message = f"Executing {function.function_name} based on agent description"
                
                # Añadir la acción
                actions.append({
                    "function": function.function_name,
                    "params": params,
                    "message": message
                })
                
        return actions
            
    async def extract_parameters_from_description(self, function_name: str, description: str) -> Dict:
        """
        Utiliza el modelo de OpenAI para extraer parámetros para una función específica
        basándose en la descripción del agente.
        
        Args:
            function_name: Nombre de la función para la que extraer parámetros
            description: Descripción del agente que contiene instrucciones
            
        Returns:
            Un diccionario con los parámetros extraídos para la función
        """
        if not self.openai_client:
            logger.warning("OpenAI client not initialized, cannot extract parameters")
            return {}
            
        try:
            # Construir el mensaje para el modelo
            # Primero obtenemos información sobre la función
            target_function = None
            for func in self.functions:
                if func.function_name == function_name:
                    target_function = func
                    break
                    
            if not target_function:
                logger.warning(f"Function {function_name} not found in agent functions")
                return {}
                
            # Construir la información sobre los parámetros requeridos basado en el ABI
            params_info = ""
            if hasattr(target_function, 'abi') and target_function.abi:
                if 'inputs' in target_function.abi:
                    for input_param in target_function.abi['inputs']:
                        param_name = input_param.get('name', '')
                        param_type = input_param.get('type', '')
                        params_info += f"- {param_name} ({param_type})\n"
            
            system_message = (
                "Eres un asistente especializado en extraer parámetros para funciones de contratos inteligentes basándote en descripciones.\n"
                "Tu tarea es identificar valores específicos mencionados en la descripción que correspondan a los parámetros requeridos."
            )
            
            user_message = (
                f"Necesito extraer parámetros para la función '{function_name}' basados en esta descripción:\n\n"
                f"\"{description}\"\n\n"
                f"La función requiere los siguientes parámetros:\n{params_info}\n"
                f"Por favor, extrae los valores para estos parámetros de la descripción y devuélvelos en formato JSON."
            )
            
            # Hacer la llamada a la API
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.2, # Baja temperatura para respuestas más precisas
                response_format={"type": "json_object"}
            )
            
            # Extraer y parsear la respuesta
            content = response.choices[0].message.content
            
            try:
                parameters = json.loads(content)
                logger.info(f"Extracted parameters for {function_name}: {parameters}")
                return parameters
            except json.JSONDecodeError:
                logger.error(f"Failed to parse OpenAI response as JSON: {content}")
                # Intento alternativo de extracción básica si el JSON no es válido
                return self._extract_basic_parameters(content, target_function)
                
        except Exception as e:
            logger.error(f"Error extracting parameters with OpenAI: {str(e)}")
            return {}
            
    def _extract_basic_parameters(self, content: str, function: AgentFunction) -> Dict:
        """
        Método de respaldo para extraer parámetros de forma básica si falla el parseo JSON
        """
        params = {}
        
        try:
            # Si la función es balanceOf, buscamos direcciones Ethereum
            if function.function_name == "balanceOf":
                # Buscar direcciones Ethereum (0x seguido de 40 caracteres hexadecimales)
                import re
                eth_address_pattern = r"0x[a-fA-F0-9]{40}"
                matches = re.findall(eth_address_pattern, content)
                
                if matches:
                    params["account"] = matches[0]
            
            return params
        except Exception as e:
            logger.error(f"Error in basic parameter extraction: {str(e)}")
            return {}
            
    async def determine_functions_to_execute(self) -> List[Dict]:
        """
        Utiliza el modelo de OpenAI para decidir qué funciones ejecutar basado en la descripción del agente
        y las funciones disponibles.
        
        Returns:
            Una lista de diccionarios con las funciones a ejecutar y sus parámetros
        """
        if not self.openai_client:
            logger.warning("OpenAI client not initialized, cannot determine functions to execute")
            return []
            
        if not self.agent or not hasattr(self.agent, 'description'):
            logger.warning("Agent not initialized or missing description")
            return []
            
        try:
            # Recopilar información sobre las funciones disponibles
            functions_info = []
            for func in self.functions:
                if not func.is_enabled:
                    continue
                    
                # Obtener detalles de los parámetros desde el ABI
                params_info = []
                if hasattr(func, 'abi') and func.abi and 'inputs' in func.abi:
                    for input_param in func.abi['inputs']:
                        param_name = input_param.get('name', '')
                        param_type = input_param.get('type', '')
                        params_info.append(f"{param_name} ({param_type})")
                
                function_info = {
                    "name": func.function_name,
                    "type": func.function_type,
                    "signature": func.function_signature,
                    "parameters": params_info
                }
                functions_info.append(function_info)
            
            if not functions_info:
                logger.warning("No enabled functions available for execution")
                return []
            
            # Construir el mensaje para el modelo
            system_message = (
                "Eres un asistente especializado en contratos inteligentes que determina qué funciones ejecutar basándose en descripciones.\n"
                "Tu tarea es analizar la descripción de un agente y decidir qué funciones disponibles deben ejecutarse."
            )
            
            user_message = (
                f"Descripción del agente: \"{self.agent.description}\"\n\n"
                f"Las siguientes funciones están disponibles:\n"
            )
            
            for i, func_info in enumerate(functions_info, 1):
                params_str = ", ".join(func_info["parameters"]) if func_info["parameters"] else "ninguno"
                user_message += f"{i}. {func_info['name']} ({func_info['type']}): Parámetros: {params_str}\n"
            
            user_message += (
                "\nBasándote en la descripción, ¿qué funciones deberían ejecutarse y con qué parámetros?\n"
                "Devuelve tu respuesta como una lista JSON de objetos con los campos 'function_name' y 'parameters'.\n"
                "Ejemplo: [{\"function_name\": \"balanceOf\", \"parameters\": {\"account\": \"0x1234...\"}}]"
            )
            
            # Hacer la llamada a la API
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Extraer y parsear la respuesta
            content = response.choices[0].message.content
            logger.info(f"OpenAI response: {content}")
            
            try:
                result = json.loads(content)
                
                # Manejar diferentes formatos de respuesta
                if "functions_to_execute" in result:
                    # Si el modelo devuelve una lista bajo la clave "functions_to_execute"
                    functions_to_execute = result["functions_to_execute"]
                    if isinstance(functions_to_execute, list):
                        logger.info(f"Determined functions to execute (format 1): {functions_to_execute}")
                        return functions_to_execute
                elif "functions" in result:
                    # Si el modelo devuelve una lista bajo la clave "functions"
                    functions_to_execute = result["functions"]
                    if isinstance(functions_to_execute, list):
                        logger.info(f"Determined functions to execute (format 2): {functions_to_execute}")
                        return functions_to_execute
                elif isinstance(result, list):
                    # Si el modelo devuelve directamente una lista
                    logger.info(f"Determined functions to execute (format 3): {result}")
                    return result
                else:
                    # Si el modelo devuelve un único objeto de función
                    # Verificamos que tenga los campos esperados y lo convertimos en una lista
                    if "function_name" in result:
                        function_item = {
                            "function_name": result["function_name"],
                            "parameters": result.get("parameters", {})
                        }
                        logger.info(f"Determined single function to execute: {function_item}")
                        return [function_item]
                
                # Si llegamos aquí, el formato no es reconocido
                logger.error(f"Unrecognized format in OpenAI response: {content}")
                
                # Intento de último recurso: usar expresiones regulares para extraer información
                import re
                
                # Buscar patrones de función y parámetros en la respuesta
                functions_to_execute = []
                
                # Patrones de búsqueda para funciones comunes
                # 1. Buscar balanceOf
                if "balanceOf" in self.agent.description or "balanceOf" in content:
                    eth_address_pattern = r"0x[a-fA-F0-9]{40}"
                    matches = re.findall(eth_address_pattern, self.agent.description)
                    if matches:
                        logger.info(f"Regex: Found balanceOf with account={matches[0]}")
                        functions_to_execute.append({
                            "function_name": "balanceOf", 
                            "parameters": {"account": matches[0]}
                        })
                
                # 2. Buscar symbol
                if "symbol" in self.agent.description or "symbol" in content:
                    for func in self.functions:
                        if func.function_name == "symbol" and func.is_enabled:
                            logger.info(f"Regex: Found symbol function")
                            functions_to_execute.append({
                                "function_name": "symbol", 
                                "parameters": {}
                            })
                
                if functions_to_execute:
                    logger.info(f"Fallback regex extraction found functions: {functions_to_execute}")
                    return functions_to_execute
                
                return []
                    
            except json.JSONDecodeError:
                logger.error(f"Failed to parse OpenAI response as JSON: {content}")
                # Intento básico de extraer la intención si falla el JSON
                # En este caso, si la descripción menciona "balanceOf" y una dirección, asumimos que quiere ejecutar esa función
                functions_to_execute = []
                
                if "balanceOf" in self.agent.description:
                    for func in self.functions:
                        if func.function_name == "balanceOf" and func.is_enabled:
                            import re
                            eth_address_pattern = r"0x[a-fA-F0-9]{40}"
                            matches = re.findall(eth_address_pattern, self.agent.description)
                            
                            if matches:
                                logger.info(f"Fallback: Found balanceOf with account={matches[0]}")
                                functions_to_execute.append({
                                    "function_name": "balanceOf", 
                                    "parameters": {"account": matches[0]}
                                })
                
                if "symbol" in self.agent.description:
                    for func in self.functions:
                        if func.function_name == "symbol" and func.is_enabled:
                            logger.info(f"Fallback: Found symbol function")
                            functions_to_execute.append({
                                "function_name": "symbol", 
                                "parameters": {}
                            })
                
                if functions_to_execute:
                    logger.info(f"Fallback extraction found functions: {functions_to_execute}")
                    return functions_to_execute
                
                return []
                
        except Exception as e:
            logger.error(f"Error determining functions to execute: {str(e)}")
            return []

    async def analyze_state(self, state: Dict, trigger_data: Dict) -> List[Dict]:
        """
        Analiza el estado del contrato y determina acciones basadas en la descripción del agente
        
        Args:
            state: Estado actual del contrato
            trigger_data: Datos del disparador de ejecución
            
        Returns:
            Lista de acciones iniciales a ejecutar
        """
        # Construir la lista de funciones con información detallada
        functions_info = []
        for f in self.functions:
            if f.is_enabled:
                function_info = {
                    'name': f.function_name,
                    'type': f.function_type,
                    'signature': f.function_signature,
                    'enabled': f.is_enabled,
                    'abi': f.abi
                }
                
                # Añadir detalles sobre los parámetros requeridos
                if f.abi and 'inputs' in f.abi:
                    function_info['required_params'] = [
                        {
                            'name': input_param.get('name'),
                            'type': input_param.get('type'),
                            'description': f"Parameter of type {input_param.get('type')}"
                        }
                        for input_param in f.abi['inputs']
                        if 'name' in input_param
                    ]
                
                functions_info.append(function_info)
        
        prompt = f"""
        Current contract state:
        {json.dumps(state, indent=2)}
        
        Trigger event data:
        {json.dumps(trigger_data, indent=2)}
        
        Agent description (behavior):
        {self.agent.description}
        
        Contract current state:
        {json.dumps(self.agent.contract_state, indent=2)}
        
        Available functions:
        {json.dumps(functions_info, indent=2)}
        
        Based on the current state, trigger event, and the agent's behavior description,
        what actions should be taken? Consider the validation rules and function types.
        Return the actions as function calls with appropriate parameters.
        
        You MUST include a 'message' field with each function call to provide comments or explanations about the execution.
        These messages will be stored in the execution logs and shown to users, serving as your communication channel.
        
        IMPORTANT: 
        1. Always use the function_call feature to respond. DO NOT respond with text.
        2. Always include a meaningful message explaining what you're doing and why.
        3. Carefully analyze the function's ABI to identify all required parameters.
        4. For each required parameter, extract the appropriate value from the agent's description.
        5. Make sure parameter types match what is expected (addresses, numbers, booleans, etc.).
        6. For addresses, ensure they are correctly formatted with the 0x prefix.
        7. The parameters object must include all required fields with their correct names as defined in the ABI.
        """
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an autonomous agent managing a smart contract."},
                {"role": "user", "content": prompt}
            ],
            functions=[{
                "name": "execute_contract_function",
                "description": "Execute a function on the smart contract",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "function_name": {"type": "string"},
                        "parameters": {"type": "object"},
                        "message": {"type": "string", "description": "Optional message or comment to include in the execution log"}
                    },
                    "required": ["function_name", "parameters"]
                }
            }]
        )
        
        return self._parse_openai_response(response) 