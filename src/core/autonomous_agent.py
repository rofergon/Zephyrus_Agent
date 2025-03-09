from typing import Dict, List, Optional, Any
import json
import asyncio
from datetime import datetime
import logging
from openai import OpenAI
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
                try:
                    api_key = os.environ.get("OPENAI_API_KEY")
                    if not api_key:
                        logger.warning("No OPENAI_API_KEY found in environment variables")
                    else:
                        instance.openai_client = OpenAI(api_key=api_key)
                        logger.info("OpenAI client initialized successfully")
                except Exception as e:
                    logger.error(f"Error initializing OpenAI client: {str(e)}")
                
                # Retornar la instancia configurada
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
                    api_key = os.environ.get("OPENAI_API_KEY")
                    if not api_key:
                        logger.warning("No OPENAI_API_KEY found in environment variables")
                    else:
                        self.openai_client = OpenAI(api_key=api_key)
                        logger.info("OpenAI client initialized successfully")
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
            
            # Verificar si debemos asegurar completar todas las tareas
            complete_all_tasks = trigger_data.get('complete_all_tasks', False)
            
            # Obtener parámetros extraídos si existen
            extracted_params = trigger_data.get('extracted_params', {})
            
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
            max_cycles = trigger_data.get('max_cycles', 5) if complete_all_tasks else 5
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
                        
                        # Si no hay parámetros definidos y tenemos parámetros extraídos, intentar usarlos
                        if not params and extracted_params:
                            # Buscar la función en las funciones disponibles
                            matching_function = None
                            for func in self.functions:
                                if func.function_name == function_name:
                                    matching_function = func
                                    break
                            
                            if matching_function:
                                # Intentar determinar parámetros basados en el tipo de función y los parámetros extraídos
                                if matching_function.function_type == "read" and function_name.lower() in ["balanceof", "balance"]:
                                    if extracted_params.get("addresses"):
                                        params = {"account": extracted_params["addresses"][0]}
                                
                                elif matching_function.function_type == "write" and function_name.lower() in ["mint", "transfer"]:
                                    if extracted_params.get("addresses"):
                                        params = {"to": extracted_params["addresses"][0]}
                                        if extracted_params.get("amounts"):
                                            params["amount"] = extracted_params["amounts"][0]
                        
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

    async def analyze_state(self, state: Dict, trigger_data: Dict) -> List[Dict]:
        """
        Analiza el estado actual y determina qué funciones ejecutar
        
        Args:
            state: Estado actual del contrato
            trigger_data: Datos del disparador de ejecución
            
        Returns:
            Lista de acciones a ejecutar
        """
        try:
            # Obtener parámetros extraídos si existen
            extracted_params = trigger_data.get('extracted_params', {})
            
            # Inicializar acciones a ejecutar
            actions = []
            
            # Si hay parámetros extraídos, podemos usarlos para determinar acciones iniciales
            if extracted_params:
                logger.info(f"Analyzing extracted parameters: {extracted_params}")
                behaviors = extracted_params.get("behaviors", [])
                addresses = extracted_params.get("addresses", [])
                amounts = extracted_params.get("amounts", [])
                conditions = extracted_params.get("conditions", [])
                
                # Determinar umbrales y cantidades de minteo
                threshold_amount = None
                mint_amount = None
                
                # Intentar obtener cantidades de los parámetros extraídos
                if amounts:
                    if len(amounts) >= 1:
                        # La primera cantidad suele ser el umbral
                        threshold_amount = amounts[0]
                    if len(amounts) >= 2:
                        # La segunda cantidad suele ser la cantidad a mintear
                        mint_amount = amounts[1]
                
                # Si no tenemos cantidades pero tenemos condiciones, intentar extraerlas
                if threshold_amount is None and conditions:
                    for condition in conditions:
                        # Buscar patrones como "less than X"
                        match = re.search(r'less than\s+(\d+)', condition)
                        if match:
                            threshold_amount = int(match.group(1))
                            logger.info(f"Extracted threshold from condition: {threshold_amount}")
                            break
                
                # Buscar en la descripción para la cantidad a mintear si no la tenemos
                if mint_amount is None:
                    description = self.agent.description.lower()
                    # Buscar patrones como "mint X at a time"
                    match = re.search(r'mint\s+(\d+)', description)
                    if match:
                        mint_amount = int(match.group(1))
                        logger.info(f"Extracted mint amount from description: {mint_amount}")
                
                # Valores por defecto si no se han encontrado
                if threshold_amount is None:
                    if "less than" in str(conditions).lower():
                        # Usar 5 como valor por defecto razonable
                        threshold_amount = 5
                        logger.info(f"Using default threshold amount: {threshold_amount}")
                
                if mint_amount is None and threshold_amount is not None:
                    # Usar 1 como valor por defecto o el umbral dividido por 2
                    mint_amount = max(1, threshold_amount // 2)
                    logger.info(f"Using default mint amount: {mint_amount}")
                
                # Actualizar los parámetros extraídos con los nuevos valores
                if threshold_amount is not None and threshold_amount not in amounts:
                    amounts.append(threshold_amount)
                if mint_amount is not None and mint_amount not in amounts:
                    amounts.append(mint_amount)
                
                # Actualizar los parámetros extraídos en trigger_data
                extracted_params["amounts"] = amounts
                trigger_data["extracted_params"] = extracted_params
                
                # Si se espera verificar un balance, empezar con esa acción
                if any(behavior in behaviors for behavior in ["check_balance", "check", "balance"]):
                    # Buscar función de balance
                    balance_function = None
                    for func in self.functions:
                        if func.function_name.lower() in ["balanceof", "balance"]:
                            balance_function = func
                            break
                    
                    if balance_function:
                        # Crear parámetros para la función
                        params = {}
                        if addresses:
                            # Para balanceOf, normalmente el parámetro se llama "account"
                            param_name = "account"
                            # Intentar obtener el nombre del parámetro del ABI
                            if balance_function.abi and "inputs" in balance_function.abi:
                                for input_param in balance_function.abi["inputs"]:
                                    if input_param.get("type") == "address":
                                        param_name = input_param.get("name", "account")
                                        break
                            
                            params[param_name] = addresses[0]
                            
                            # Añadir acción de verificación de balance
                            actions.append({
                                "function": balance_function.function_name,
                                "params": params,
                                "message": f"Checking balance for address {addresses[0]}"
                            })
                            
                            logger.info(f"Added balance check action for address {addresses[0]}")
                
                # Si no hay acciones específicas pero se menciona "mint" en los comportamientos,
                # y tenemos una operación de mint disponible, programarla directamente
                if not actions and "mint" in behaviors:
                    mint_function = None
                    for func in self.functions:
                        if func.function_name.lower() == "mint" and func.function_type == "write":
                            mint_function = func
                            break
                    
                    if mint_function and addresses:
                        # Determinar la cantidad a mintear
                        mint_amount = mint_amount if mint_amount is not None else 5000000
                        
                        # Crear parámetros para la función mint
                        to_param_name = "to"
                        amount_param_name = "amount"
                        
                        if mint_function.abi and "inputs" in mint_function.abi:
                            for input_param in mint_function.abi["inputs"]:
                                if input_param.get("type") == "address":
                                    to_param_name = input_param.get("name", "to")
                                elif input_param.get("type") in ["uint256", "uint"]:
                                    amount_param_name = input_param.get("name", "amount")
                        
                        params = {
                            to_param_name: addresses[0],
                            amount_param_name: mint_amount
                        }
                        
                        actions.append({
                            "function": mint_function.function_name,
                            "params": params,
                            "message": f"Minting {mint_amount} tokens to {addresses[0]}"
                        })
                        
                        logger.info(f"Added mint action for {mint_amount} tokens to {addresses[0]}")
                
                # Si no hay acciones específicas, usar el algoritmo normal
                if not actions:
                    logger.info("No specific actions determined from extracted parameters, using fallback algorithm")
                    actions = await self._determine_initial_actions_from_description()
            
            # Si no hay acciones determinadas, usar OpenAI para analizar
            if not actions:
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
                
                Based on the current state, the agent's behavior description, and available functions,
                what actions should be taken? Consider the validation rules and function types.
                Return the actions as function calls with appropriate parameters.
                
                You MUST include a 'message' field with each function call to provide comments or explanations about the execution.
                These messages will be stored in the execution logs and shown to users, serving as your communication channel.
                """
                
                try:
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "You are an autonomous agent managing a smart contract. You generate appropriate parameter values for function calls based on context and function specifications."},
                            {"role": "user", "content": prompt}
                        ],
                        tools=[{
                            "type": "function",
                            "function": {
                                "name": "execute_functions",
                                "description": "Execute functions on the smart contract",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "functions": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "function_name": {"type": "string", "description": "Name of the function to execute"},
                                                    "parameters": {"type": "object", "description": "Parameters for the function"},
                                                    "message": {"type": "string", "description": "Optional message or comment to include in the execution log"}
                                                },
                                                "required": ["function_name", "parameters", "message"]
                                            }
                                        }
                                    },
                                    "required": ["functions"]
                                }
                            }
                        }],
                        tool_choice="auto"
                    )
                    
                    actions = self._parse_openai_response(response)
                    
                except Exception as e:
                    logger.error(f"Error calling OpenAI for analyze_state: {str(e)}")
                    
                    # Si hay un error con OpenAI, intentar determinar acciones basadas en los parámetros extraídos
                    if extracted_params:
                        logger.info(f"Fallback: Determinando acciones basadas en parámetros extraídos: {extracted_params}")
                        actions = await self._determine_initial_actions_from_description()
                        
                        # Si no se pudieron determinar acciones, intentar crear acciones basadas en comportamientos
                        if not actions and "behaviors" in extracted_params:
                            behaviors = extracted_params["behaviors"]
                            addresses = extracted_params.get("addresses", [])
                            amounts = extracted_params.get("amounts", [])
                            
                            # Si se requiere verificar balances
                            if "check_balance" in behaviors or "check" in behaviors:
                                for func_name, func in self._functions.items():
                                    if func.name.lower() == "balanceof" and addresses:
                                        actions.append({
                                            "function_name": func.name,
                                            "parameters": {"account": addresses[0]},
                                            "message": f"Checking balance for address {addresses[0]}"
                                        })
                                        break
                            
                            # Si se requiere mintear tokens
                            if "mint" in behaviors and not actions:
                                for func_name, func in self._functions.items():
                                    if func.name.lower() == "mint" and addresses:
                                        amount = amounts[1] if len(amounts) > 1 else (amounts[0] if amounts else 5000000)
                                        actions.append({
                                            "function_name": func.name,
                                            "parameters": {"to": addresses[0], "amount": amount},
                                            "message": f"Minting {amount} tokens to {addresses[0]}"
                                        })
                                        break
            
            logger.info(f"Determined {len(actions)} initial actions for agent {self.agent_id}")
            return actions
            
        except Exception as e:
            logger.error(f"Error in analyze_state for agent {self.agent_id}: {str(e)}")
            return []

    async def _determine_initial_actions_from_description(self) -> List[Dict]:
        """
        Determina acciones iniciales basadas en la descripción del agente
        y las funciones disponibles
        
        Returns:
            Lista de acciones iniciales
        """
        actions = []
        description = self.agent.description.lower() if self.agent and self.agent.description else ""
        
        # Extraer direcciones y cantidades de la descripción
        address_pattern = r'0x[a-fA-F0-9]{40}'
        addresses = re.findall(address_pattern, description)
        
        # Nueva expresión regular que captura cualquier número, incluidos pequeños
        amount_pattern = r'(?:less than|mint|equals|equal to|greater than|more than|minimum|maximum|min|max|about|around|approximately|exactly|precisely)\s+(\d+)'
        threshold_amounts = [int(amount) for amount in re.findall(amount_pattern, description)]
        
        # Otra expresión para capturar números sueltos, especialmente en el formato "mint X at a time"
        direct_amount_pattern = r'\b(\d+)\s+(?:at a time|tokens|coin|coins|wei|gwei|eth|ether|token)\b'
        direct_amounts = [int(amount) for amount in re.findall(direct_amount_pattern, description)]
        
        # También capturar números solos (pero evitando direcciones hexadecimales)
        standalone_pattern = r'(?<![a-fA-F0-9])\b(\d+)\b(?![a-fA-F0-9])'
        standalone_amounts = []
        for amount in re.findall(standalone_pattern, description):
            # Evitar duplicados
            num = int(amount)
            if num not in threshold_amounts and num not in direct_amounts:
                standalone_amounts.append(num)
        
        # Combinar todas las cantidades, dando prioridad a las que tienen contexto
        amounts = threshold_amounts + direct_amounts + standalone_amounts
        
        logger.info(f"Extracted from description - Addresses: {addresses}, Amounts: {amounts}")
        
        # Buscar acciones basadas en patrones comunes en la descripción
        
        # Verificar si hay funciones de lectura de balance
        if "balance" in description or "check" in description:
            for func in self.functions:
                if func.function_name.lower() in ["balanceof", "balance"] and func.function_type == "read":
                    params = {}
                    if addresses:
                        # Buscar el nombre del parámetro en el ABI
                        param_name = "account"
                        if func.abi and "inputs" in func.abi:
                            for input_param in func.abi["inputs"]:
                                if input_param.get("type") == "address":
                                    param_name = input_param.get("name", "account")
                                    break
                        
                        params[param_name] = addresses[0]
                    
                    actions.append({
                        "function": func.function_name,
                        "params": params,
                        "message": f"Checking balance for address {addresses[0] if addresses else 'owner'}"
                    })
                    break
        
        # Verificar si hay funciones de mint o transfer
        if "mint" in description or "transfer" in description or "send" in description:
            # Si ya hay funciones de lectura, no añadir funciones de escritura en la primera pasada
            if not actions:
                for func in self.functions:
                    if func.function_name.lower() in ["mint", "transfer", "send"] and func.function_type == "write":
                        params = {}
                        if addresses:
                            # Buscar el nombre del parámetro en el ABI
                            to_param_name = "to"
                            amount_param_name = "amount"
                            
                            if func.abi and "inputs" in func.abi:
                                for input_param in func.abi["inputs"]:
                                    if input_param.get("type") == "address":
                                        to_param_name = input_param.get("name", "to")
                                    elif input_param.get("type") in ["uint256", "uint"]:
                                        amount_param_name = input_param.get("name", "amount")
                            
                            params[to_param_name] = addresses[0]
                            if amounts:
                                params[amount_param_name] = amounts[0]
                            elif "amount" not in params:
                                # Valor por defecto si no se especifica
                                params[amount_param_name] = 5000000
                        
                        actions.append({
                            "function": func.function_name,
                            "params": params,
                            "message": f"Minting tokens to {addresses[0] if addresses else 'address'}"
                        })
                        break
        
        return actions

    async def analyze_results(self, state: Dict, trigger_data: Dict, execution_history: List[Dict]) -> List[Dict]:
        """
        Analiza los resultados de la ejecución anterior y determina las siguientes acciones
        
        Args:
            state: Estado actual del contrato
            trigger_data: Datos del disparador
            execution_history: Historial de ejecuciones previas
            
        Returns:
            Lista de acciones a ejecutar
        """
        # Obtener parámetros extraídos si existen
        extracted_params = trigger_data.get('extracted_params', {})
        
        # Si hay tareas pendientes de ejecuciones previas, devolverlas
        pending_tasks = self._get_pending_tasks(execution_history)
        
        # Analizar explícitamente el historial de ejecución para detectar si necesitamos continuar 
        # basándonos en la descripción del agente y las condiciones extraídas
        if execution_history and extracted_params:
            # Extraer información relevante de los parámetros
            addresses = extracted_params.get("addresses", [])
            amounts = extracted_params.get("amounts", [])
            behaviors = extracted_params.get("behaviors", [])
            
            # Verificar si la descripción implica verificar balance y mintear si es necesario
            if "check_balance" in behaviors or "check" in behaviors:
                # Buscar la última ejecución de balanceOf
                last_balance_check = None
                for execution in reversed(execution_history):
                    if execution.get("function") and execution.get("function").lower() in ["balanceof", "balance"]:
                        last_balance_check = execution
                        break
                
                # Si se verificó el balance y tenemos información sobre las condiciones
                if last_balance_check and "result" in last_balance_check and last_balance_check["result"].get("success"):
                    # Obtener el valor del balance
                    balance_result = last_balance_check["result"].get("data")
                    if balance_result:
                        try:
                            current_balance = int(balance_result)
                            logger.info(f"Detected current balance: {current_balance}")
                            
                            # Verificar condición de balance mínimo
                            # Si no hay cantidades extraídas pero hay una condición de "menos que", intentar extraerla
                            conditions = extracted_params.get("conditions", [])
                            threshold_amount = None
                            mint_amount = None
                            
                            # Intentar obtener cantidades de los parámetros extraídos
                            if amounts:
                                if len(amounts) >= 1:
                                    # La primera cantidad suele ser el umbral
                                    threshold_amount = amounts[0]
                                if len(amounts) >= 2:
                                    # La segunda cantidad suele ser la cantidad a mintear
                                    mint_amount = amounts[1]
                            
                            # Si no tenemos cantidades pero tenemos condiciones, intentar extraerlas
                            if threshold_amount is None and conditions:
                                for condition in conditions:
                                    # Buscar patrones como "less than X"
                                    match = re.search(r'less than\s+(\d+)', condition)
                                    if match:
                                        threshold_amount = int(match.group(1))
                                        logger.info(f"Extracted threshold from condition: {threshold_amount}")
                                        break
                            
                            # Buscar en la descripción para la cantidad a mintear si no la tenemos
                            if mint_amount is None:
                                description = self.agent.description.lower()
                                # Buscar patrones como "mint X at a time"
                                match = re.search(r'mint\s+(\d+)', description)
                                if match:
                                    mint_amount = int(match.group(1))
                                    logger.info(f"Extracted mint amount from description: {mint_amount}")
                            
                            # Valores por defecto si no se han encontrado
                            if threshold_amount is None:
                                # Usar 5 como valor por defecto razonable
                                threshold_amount = 5
                                logger.info(f"Using default threshold amount: {threshold_amount}")
                            
                            if mint_amount is None:
                                # Usar 1 como valor por defecto o el umbral dividido por 2
                                mint_amount = max(1, threshold_amount // 2)
                                logger.info(f"Using default mint amount: {mint_amount}")
                            
                            # Comparar el balance actual con el umbral
                            logger.info(f"Comparing balance {current_balance} with threshold {threshold_amount}")
                            if current_balance < threshold_amount and "mint" in behaviors:
                                logger.info(f"Balance {current_balance} is below threshold {threshold_amount}, need to mint tokens")
                                
                                # Buscar función de mint
                                for func in self.functions:
                                    if func.function_name.lower() == "mint" and func.function_type == "write":
                                        # Crear la acción de mint
                                        mint_action = {
                                            "function": func.function_name,
                                            "params": {
                                                "to": addresses[0] if addresses else self.agent.owner,
                                                "amount": mint_amount
                                            },
                                            "message": f"Minting {mint_amount} tokens to {addresses[0] if addresses else 'owner'} to meet threshold of {threshold_amount}"
                                        }
                                        return [mint_action]
                            
                            # Si el balance es menor que el umbral pero ya hemos ejecutado mint recientemente,
                            # programar otra verificación de balance
                            elif current_balance < threshold_amount:
                                # Verificar si la última acción fue un mint
                                last_action = execution_history[-1]
                                if last_action.get("function") and last_action.get("function").lower() == "mint":
                                    # Programar otra verificación de balance para ver si el mint fue efectivo
                                    for func in self.functions:
                                        if func.function_name.lower() in ["balanceof", "balance"] and func.function_type == "read":
                                            check_action = {
                                                "function": func.function_name,
                                                "params": {
                                                    "account": addresses[0] if addresses else self.agent.owner
                                                },
                                                "message": f"Checking updated balance after mint for {addresses[0] if addresses else 'owner'}"
                                            }
                                            return [check_action]
                        except (ValueError, TypeError) as e:
                            logger.error(f"Error parsing balance result '{balance_result}': {str(e)}")
        
        # Si no necesitamos consultar a OpenAI y tenemos tareas pendientes, devolver las tareas pendientes
        if not trigger_data.get("complete_all_tasks", False) and pending_tasks:
            return pending_tasks
        
        # Resto del código original para consultar a OpenAI
        # Construir el prompt para el modelo
        messages = [
            {
                "role": "system",
                "content": f"""Eres un asistente que analiza el estado de un contrato inteligente y determina qué acciones tomar.
                
Contrato: {self.agent.contract_id if self.agent else 'Desconocido'}
Nombre: {self.agent.name if self.agent else 'Desconocido'}
Descripción: {self.agent.description if self.agent else 'Desconocido'}

Estado actual: {json.dumps(state, indent=2)}

Historial de ejecución:
{json.dumps(execution_history, indent=2)}

Tu tarea es revisar el estado, el historial de ejecución y determinar qué funciones se deben ejecutar a continuación.
"""
            }
        ]
        
        # Agregar información sobre las funciones disponibles
        function_descriptions = ""
        for func in self.functions:
            function_descriptions += f"- {func.function_name} ({func.function_type}): {func.function_signature}\n"
        
        messages.append({
            "role": "user",
            "content": f"""Basándote en la descripción del agente y el historial de ejecución, determina qué acciones se deben tomar a continuación.
            
Funciones disponibles:
{function_descriptions}

Determina si se necesitan ejecutar más funciones o si todas las tareas se han completado.
"""
        })
        
        # Construir la definición de herramientas para el formato de OpenAI
        tools = [{
            "type": "function",
            "function": {
                "name": "determine_actions",
                "description": "Determina las próximas acciones a ejecutar basándose en el estado y el historial",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "functions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "function_name": {"type": "string", "description": "Name of the function to execute"},
                                    "parameters": {"type": "object", "description": "Parameters for the function"},
                                    "message": {"type": "string", "description": "Optional message or comment to include in the execution log"}
                                },
                                "required": ["function_name", "parameters", "message"]
                            }
                        }
                    },
                    "required": ["functions"]
                }
            }
        }]
        
        # Enviar consulta al modelo de OpenAI solo si no tenemos tareas pendientes predefinidas
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4", 
                messages=messages,
                tools=tools
            )
            
            # Procesar la respuesta
            return self._parse_openai_response(response)
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            # Si hay un error con la API, pero tenemos tareas pendientes, devolver esas
            if pending_tasks:
                return pending_tasks
            return []

    def _parse_openai_response(self, response) -> List[Dict]:
        """
        Parsea la respuesta de OpenAI para extraer las acciones a ejecutar
        
        Args:
            response: Respuesta de OpenAI
            
        Returns:
            Lista de acciones a ejecutar
        """
        actions = []
        
        try:
            # Obtener el primer mensaje del asistente
            if not response or not hasattr(response, 'choices') or not response.choices:
                logger.warning("OpenAI response is empty or missing 'choices'")
                return []
                
            choice = response.choices[0]
            if not hasattr(choice, 'message'):
                logger.warning("OpenAI response choice is missing 'message'")
                return []
                
            message = choice.message
            
            # Verificar si hay una herramienta llamada
            if hasattr(message, 'tool_calls') and message.tool_calls:
                logger.info(f"Found tool_calls in response: {len(message.tool_calls)}")
                
                for tool_call in message.tool_calls:
                    try:
                        if hasattr(tool_call, 'function') and tool_call.function:
                            function_data = tool_call.function
                            
                            # Para el formato de execute_functions que devuelve una lista
                            if function_data.name == 'execute_functions':
                                args = json.loads(function_data.arguments)
                                
                                if 'functions' in args and isinstance(args['functions'], list):
                                    for func_info in args['functions']:
                                        action = {
                                            'function': func_info.get('function_name'),
                                            'params': func_info.get('parameters', {}),
                                            'message': func_info.get('message', '')
                                        }
                                        actions.append(action)
                            
                            # Para el formato antiguo de función directa
                            else:
                                args = json.loads(function_data.arguments)
                                action = {
                                    'function': function_data.name,
                                    'params': args,
                                    'message': args.get('message', '')
                                }
                                actions.append(action)
                                
                    except Exception as e:
                        logger.error(f"Error parsing tool call: {str(e)}")
            
            # Verificar formato antiguo de function_call
            elif hasattr(message, 'function_call') and message.function_call:
                function_call = message.function_call
                
                try:
                    args = json.loads(function_call.arguments)
                    
                    # Para el formato de execute_functions que devuelve una lista
                    if function_call.name == 'execute_functions':
                        if 'functions' in args and isinstance(args['functions'], list):
                            for func_info in args['functions']:
                                action = {
                                    'function': func_info.get('function_name'),
                                    'params': func_info.get('parameters', {}),
                                    'message': func_info.get('message', '')
                                }
                                actions.append(action)
                    
                    # Para el formato antiguo de llamada directa
                    else:
                        action = {
                            'function': function_call.name,
                            'params': args,
                            'message': args.get('message', '')
                        }
                        actions.append(action)
                
                except Exception as e:
                    logger.error(f"Error parsing function call: {str(e)}")
            
            # Si no hay tool_calls ni function_call, verificar si hay un mensaje de texto con un formato específico
            elif hasattr(message, 'content') and message.content:
                content = message.content.strip()
                
                # Intentar buscar funciones en el texto
                if content:
                    try:
                        # Verificar si parece un JSON
                        if content.startswith('{') and content.endswith('}') or content.startswith('[') and content.endswith(']'):
                            data = json.loads(content)
                            
                            # Si es un objeto, convertirlo a lista
                            if isinstance(data, dict):
                                data = [data]
                            
                            # Procesar lista de acciones
                            if isinstance(data, list):
                                for item in data:
                                    if isinstance(item, dict) and 'function' in item:
                                        action = {
                                            'function': item.get('function'),
                                            'params': item.get('params', {}),
                                            'message': item.get('message', '')
                                        }
                                        actions.append(action)
                    
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse message content as JSON: {content}")
            
            logger.info(f"Parsed {len(actions)} actions from OpenAI response")
            
        except Exception as e:
            logger.error(f"Error in _parse_openai_response: {str(e)}")
        
        return actions

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
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3, # Baja temperatura para respuestas más precisas
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

    def _get_pending_tasks(self, execution_history: List[Dict]) -> List[Dict]:
        """
        Determina si hay tareas pendientes basadas en el historial de ejecución
        y la descripción del agente
        
        Args:
            execution_history: Historial de ejecuciones previas
            
        Returns:
            Lista de tareas pendientes
        """
        # Extraer las funciones ya ejecutadas
        executed_functions = [history_item.get('function') for history_item in execution_history]
        
        # Extraer los resultados específicos de lecturas y acciones importantes
        domain_separator_result = None
        admin_role_result = None
        
        # Crear tracking de direcciones que ya recibieron minteo
        minted_addresses = set()
        
        for r in execution_history:
            if r.get('function') == "DOMAIN_SEPARATOR" and 'result' in r and isinstance(r['result'], dict) and 'data' in r['result']:
                domain_separator_result = r['result']['data']
            elif r.get('function') == "ADMIN_ROLE" and 'result' in r and isinstance(r['result'], dict) and 'data' in r['result']:
                admin_role_result = r['result']['data']
            elif r.get('function') == "mint" and 'params' in r and 'to' in r['params']:
                minted_addresses.add(r['params']['to'])
        
        # Extraer las direcciones esperadas de la descripción
        description = self.agent.description.lower() if self.agent and hasattr(self.agent, 'description') else ""
        expected_addresses = []
        
        # Buscar direcciones Ethereum en la descripción
        address_pattern = r'0x[a-fA-F0-9]{40}'
        addresses_in_description = re.findall(address_pattern, description)
        if addresses_in_description:
            expected_addresses = addresses_in_description
        
        # Definir tareas pendientes basadas en la descripción y lo ya ejecutado
        pending_tasks = []
        
        # Si no se ha ejecutado DOMAIN_SEPARATOR y está en la descripción
        if "domain_separator" in description and "DOMAIN_SEPARATOR" not in executed_functions:
            pending_tasks.append({
                "function_name": "DOMAIN_SEPARATOR",
                "parameters": {},
                "message": "Getting the domain separator data as described in the behavior."
            })
        
        # Si no se ha ejecutado ADMIN_ROLE y está en la descripción
        if ("admin_role" in description or "admin role" in description) and "ADMIN_ROLE" not in executed_functions:
            pending_tasks.append({
                "function_name": "ADMIN_ROLE",
                "parameters": {},
                "message": "Reading the ADMIN_ROLE value as required in the agent description."
            })
        
        # Mintear tokens a direcciones mencionadas que aún no se han procesado
        for addr in expected_addresses:
            if addr not in minted_addresses and "mint" in description:
                # Busca un valor específico para mintear en la descripción cerca de esta dirección
                amount_pattern = r'(\d+)(?:\s+tokenes|\s+tokens)'
                amounts = re.findall(amount_pattern, description)
                amount = 5000000  # Valor por defecto
                
                if amounts:
                    try:
                        amount = int(amounts[0])
                    except ValueError:
                        pass
                
                pending_tasks.append({
                    "function_name": "mint",
                    "parameters": {
                        "to": addr,
                        "amount": amount
                    },
                    "message": f"Minting {amount} tokens to {addr} as specified in the agent description."
                })
        
        return pending_tasks 