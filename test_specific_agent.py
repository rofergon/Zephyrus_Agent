#!/usr/bin/env python
"""
Script para probar directamente la ejecución del agente específico
que está causando problemas, sin usar WebSockets.
Esta versión generalizada permite que un agente autónomo:
1. Extraiga parámetros como direcciones y cantidades de su propia descripción
2. Complete todas sus tareas basándose en el comportamiento descrito
3. Refleje sobre si se han completado todas las acciones necesarias
"""
import asyncio
import logging
import sys
import os
import json
import re

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_specific_agent")

# ID del agente a probar
AGENT_ID = "aaea027b-c28c-4f20-93bf-e8d200ad77f6"

# Asegurar que podemos importar desde el directorio raíz
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api.db_client import DatabaseClient
from src.core.autonomous_agent import AutonomousAgent
from datetime import datetime

async def analyze_agent_description(description):
    """
    Analiza la descripción del agente para extraer parámetros relevantes
    como direcciones, cantidades, y patrones de comportamiento.
    
    Args:
        description: La descripción del agente
        
    Returns:
        Un diccionario con los parámetros extraídos
    """
    params = {
        "addresses": [],
        "amounts": [],
        "functions": [],
        "conditions": [],
        "behaviors": []
    }
    
    # Extraer direcciones Ethereum (0x seguido de 40 caracteres hexadecimales)
    address_pattern = r'0x[a-fA-F0-9]{40}'
    params["addresses"] = re.findall(address_pattern, description)
    
    # Extraer cantidades numéricas grandes (posiblemente tokens)
    amount_pattern = r'(\d{10,})'
    amount_matches = re.findall(amount_pattern, description)
    params["amounts"] = [int(amount) for amount in amount_matches]
    
    # Intentar identificar nombres de funciones mencionadas en la descripción
    function_pattern = r'using\s+([a-zA-Z0-9_]+)|call\s+([a-zA-Z0-9_]+)|function\s+([a-zA-Z0-9_]+)|método\s+([a-zA-Z0-9_]+)'
    function_matches = re.findall(function_pattern, description, re.IGNORECASE)
    params["functions"] = [match[0] or match[1] or match[2] or match[3] for match in function_matches if any(match)]
    
    # Intentar identificar condiciones (if, when, etc.)
    condition_pattern = r'(?:if|when|si|cuando)\s+([^.,;]+)'
    params["conditions"] = re.findall(condition_pattern, description, re.IGNORECASE)
    
    # Detectar patrones de comportamiento comunes
    if "check" in description.lower() or "verificar" in description.lower() or "comprobar" in description.lower():
        params["behaviors"].append("check")
    
    if "mint" in description.lower() or "crear" in description.lower() or "generar" in description.lower():
        params["behaviors"].append("mint")
    
    if "repeat" in description.lower() or "repetir" in description.lower() or "until" in description.lower() or "loop" in description.lower():
        params["behaviors"].append("repeat")
    
    if "balance" in description.lower() or "saldo" in description.lower():
        params["behaviors"].append("check_balance")
    
    logger.info(f"Análisis de la descripción del agente:")
    logger.info(f"  Direcciones encontradas: {params['addresses']}")
    logger.info(f"  Cantidades encontradas: {params['amounts']}")
    logger.info(f"  Funciones mencionadas: {params['functions']}")
    logger.info(f"  Comportamientos detectados: {params['behaviors']}")
    
    return params

async def extract_parameters_for_function(function_name, function_abi, agent_params, function_type):
    """
    Extrae los parámetros adecuados para una función basado en su ABI y
    los parámetros extraídos de la descripción del agente.
    
    Args:
        function_name: Nombre de la función
        function_abi: ABI de la función
        agent_params: Parámetros extraídos de la descripción del agente
        function_type: Tipo de función (read/write)
        
    Returns:
        Diccionario con los parámetros para la función
    """
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
        
        # Address parameters
        if param_type == "address" and param_name.lower() in ["to", "account", "owner", "recipient"]:
            if agent_params["addresses"]:
                params[param_name] = agent_params["addresses"][0]
        
        # Amount parameters
        elif param_type in ["uint256", "uint"] and param_name.lower() in ["amount", "value", "tokens"]:
            if agent_params["amounts"]:
                params[param_name] = agent_params["amounts"][0]
    
    return params

async def run_agent_test():
    """Ejecuta un agente autónomo extrayendo parámetros de su descripción"""
    logger.info(f"Probando agente con ID: {AGENT_ID}")
    
    try:
        # Obtener datos del agente
        async with DatabaseClient() as db_client:
            # Verificar si el agente existe
            agent_data = await db_client.get_agent(AGENT_ID)
            if not agent_data:
                logger.error(f"El agente {AGENT_ID} no existe")
                return
                
            logger.info(f"Agente encontrado: {agent_data.name}")
            logger.info(f"Descripción del agente: {agent_data.description}")
            
            # Analizar la descripción del agente para extraer parámetros
            agent_params = await analyze_agent_description(agent_data.description)
            
            # Obtener contrato
            contract_data = await db_client.get_contract(agent_data.contract_id)
            if not contract_data:
                logger.error(f"El contrato {agent_data.contract_id} no existe")
                return
                
            logger.info(f"Contrato encontrado: {contract_data.get('name', 'Sin nombre')}")
            
            # Obtener funciones
            functions = await db_client.get_agent_functions(AGENT_ID)
            logger.info(f"Funciones encontradas: {len(functions)}")
            
            for i, func in enumerate(functions, 1):
                logger.info(f"Función {i}: {func.function_name} ({func.function_type})")
                
                # Extraer parámetros específicos para esta función
                func_params = await extract_parameters_for_function(
                    func.function_name, 
                    func.abi, 
                    agent_params,
                    func.function_type
                )
                
                # Almacenar los parámetros extraídos en el objeto de función
                if hasattr(func, "extracted_params"):
                    func.extracted_params = func_params
                else:
                    setattr(func, "extracted_params", func_params)
                
                if func_params:
                    logger.info(f"  Parámetros extraídos: {json.dumps(func_params, indent=2)}")
            
            # Obtener programación
            schedule = await db_client.get_agent_schedule(AGENT_ID)
            
            # Crear configuración
            config = {
                "agent_id": AGENT_ID,
                "contract": contract_data,
                "agent": agent_data.to_dict(),
                "functions": [func.to_dict() for func in functions],
                "schedule": schedule.to_dict() if schedule else None,
                "extracted_params": agent_params  # Añadir los parámetros extraídos a la configuración
            }
            
            # Crear agente
            logger.info("Creando instancia del agente...")
            agent = await AutonomousAgent.from_config(config)
            
            # Inicializar agente
            logger.info("Inicializando agente...")
            await agent.initialize()
            
            # Datos del trigger con indicador para completar todas las tareas
            trigger_data = {
                "trigger_type": "test",
                "timestamp": datetime.now().isoformat(),
                "execution_id": f"test_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "complete_all_tasks": True,  # Indicador para completar todas las tareas
                "max_cycles": 10,  # Aumentar el número máximo de ciclos para asegurar que complete todas las tareas
                "extracted_params": agent_params  # Incluir los parámetros extraídos en el trigger
            }
            
            # Ejecutar agente
            logger.info("Ejecutando agente para completar todas las tareas...")
            results = await agent.analyze_and_execute(trigger_data)
            
            # Mostrar resultados
            if results:
                logger.info(f"Ejecución completada: {len(results)} acciones")
                for i, result in enumerate(results, 1):
                    function_name = result.get('function', 'unknown')
                    params = result.get('params', {})
                    result_data = result.get('result', {})
                    message = result.get('message', 'No message')
                    
                    logger.info(f"Acción {i}: {function_name}")
                    logger.info(f"  Parámetros: {json.dumps(params, indent=2)}")
                    logger.info(f"  Resultado: {json.dumps(result_data, indent=2) if isinstance(result_data, dict) else str(result_data)}")
                    logger.info(f"  Mensaje: {message}")
            else:
                logger.info("No se ejecutaron acciones")
                
            # Evaluar el éxito basado en los comportamientos detectados
            logger.info("\nResumen de ejecución:")
            logger.info("=====================")
            logger.info(f"Total de acciones ejecutadas: {len(results)}")
            
            # Verificar qué funciones se ejecutaron
            executed_functions = set([r.get('function') for r in results if 'function' in r])
            available_functions = set([f.function_name for f in functions])
            
            logger.info(f"Funciones ejecutadas: {', '.join(executed_functions)}")
            logger.info(f"Funciones disponibles no ejecutadas: {', '.join(available_functions - executed_functions)}")
            
            # Evaluación basada en comportamientos detectados
            logger.info("\nEvaluación de comportamientos completados:")
            behaviors_completed = {b: False for b in agent_params["behaviors"]}
            
            # Verificar si se completaron los comportamientos detectados
            for behavior in agent_params["behaviors"]:
                if behavior == "check_balance":
                    balance_checked = any(r.get('function', '').lower() in ["balanceof", "balance"] for r in results)
                    behaviors_completed["check_balance"] = balance_checked
                    logger.info(f"Verificar balance: {'✓' if balance_checked else '✗'}")
                
                if behavior == "mint":
                    mint_executed = any(r.get('function', '').lower() == "mint" for r in results)
                    behaviors_completed["mint"] = mint_executed
                    logger.info(f"Mintear tokens: {'✓' if mint_executed else '✗'}")
                
                if behavior == "repeat":
                    # Considerar repetición si hay al menos 2 llamadas a la misma función
                    function_counts = {}
                    for r in results:
                        func_name = r.get('function', '')
                        function_counts[func_name] = function_counts.get(func_name, 0) + 1
                    
                    repeated = any(count >= 2 for count in function_counts.values())
                    behaviors_completed["repeat"] = repeated
                    logger.info(f"Repetir operaciones: {'✓' if repeated else '✗'}")
            
            # Verificar direcciones utilizadas
            used_addresses = set()
            for r in results:
                params = r.get('params', {})
                for param_value in params.values():
                    if isinstance(param_value, str) and re.match(r'0x[a-fA-F0-9]{40}', param_value):
                        used_addresses.add(param_value)
            
            if agent_params["addresses"]:
                for addr in agent_params["addresses"]:
                    addr_used = addr in used_addresses
                    logger.info(f"Dirección {addr} utilizada: {'✓' if addr_used else '✗'}")
            
            # Resumen final
            completed_behaviors = sum(1 for completed in behaviors_completed.values() if completed)
            total_behaviors = len(behaviors_completed)
            
            logger.info("\nResumen final:")
            logger.info(f"Comportamientos completados: {completed_behaviors}/{total_behaviors}")
            all_completed = completed_behaviors == total_behaviors
            logger.info(f"Todos los comportamientos requeridos completados: {'SÍ' if all_completed else 'NO'}")
                
    except Exception as e:
        logger.exception(f"Error ejecutando el agente: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_agent_test()) 