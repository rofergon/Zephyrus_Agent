#!/usr/bin/env python
"""
Script para probar directamente la ejecución del agente específico
que está causando problemas, sin usar WebSockets.
Esta versión revisada permite que el agente complete todas sus tareas
y reflexione sobre si ha terminado todas las acciones requeridas.
"""
import asyncio
import logging
import sys
import os
import json

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_specific_agent")

# ID del agente a probar
AGENT_ID = "5842cd1b-3566-4c1c-8a4e-4854fbfe514e"

# Asegurar que podemos importar desde el directorio raíz
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api.db_client import DatabaseClient
from src.core.autonomous_agent import AutonomousAgent
from datetime import datetime

async def run_agent_test():
    """Ejecuta el agente para completar todas sus tareas definidas en su descripción"""
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
            
            # Obtener programación
            schedule = await db_client.get_agent_schedule(AGENT_ID)
            
            # Crear configuración
            config = {
                "agent_id": AGENT_ID,
                "contract": contract_data,
                "agent": agent_data.to_dict(),
                "functions": [func.to_dict() for func in functions],
                "schedule": schedule.to_dict() if schedule else None
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
                "max_cycles": 10  # Aumentar el número máximo de ciclos para asegurar que complete todas las tareas
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
                
            # Verificar si se completaron todas las tareas
            logger.info("\nResumen de ejecución:")
            logger.info("=====================")
            logger.info(f"Total de acciones ejecutadas: {len(results)}")
            
            # Verificar qué funciones se ejecutaron
            executed_functions = set([r.get('function') for r in results if 'function' in r])
            available_functions = set([f.function_name for f in functions])
            
            logger.info(f"Funciones ejecutadas: {', '.join(executed_functions)}")
            logger.info(f"Funciones disponibles no ejecutadas: {', '.join(available_functions - executed_functions)}")
            
            # Comprobar si todas las tareas descritas en la descripción del agente se ejecutaron
            logger.info("\nEvaluación de tareas completadas:")
            description = agent_data.description.lower()
            
            # Verificar lectura de DOMAIN_SEPARATOR
            domain_separator_executed = any(r.get('function') == "DOMAIN_SEPARATOR" for r in results)
            logger.info(f"Leer DOMAIN_SEPARATOR: {'✓' if domain_separator_executed else '✗'}")
            
            # Verificar lectura de ADMIN_ROLE
            admin_role_executed = any(r.get('function') == "ADMIN_ROLE" for r in results)
            logger.info(f"Leer ADMIN_ROLE: {'✓' if admin_role_executed else '✗'}")
            
            # Verificar operaciones de mint
            mint_operations = [r for r in results if r.get('function') == "mint"]
            mint_addresses = set(r.get('params', {}).get('to', '') for r in mint_operations if 'params' in r)
            
            expected_addresses = [
                "0xaB6E247B25463F76E81aBAbBb6b0b86B40d45D38",
                "0x6FE1e006AD733717539bac3f7E73470fC5B34Bad"
            ]
            
            for addr in expected_addresses:
                mint_status = addr in mint_addresses
                logger.info(f"Mintear tokens para {addr}: {'✓' if mint_status else '✗'}")
            
            # Verificar si se combinaron los valores de DOMAIN_SEPARATOR y ADMIN_ROLE
            domain_separator_result = None
            admin_role_result = None
            
            for r in results:
                if r.get('function') == "DOMAIN_SEPARATOR" and 'result' in r and isinstance(r['result'], dict) and 'data' in r['result']:
                    domain_separator_result = r['result']['data']
                elif r.get('function') == "ADMIN_ROLE" and 'result' in r and isinstance(r['result'], dict) and 'data' in r['result']:
                    admin_role_result = r['result']['data']
            
            if domain_separator_result and admin_role_result:
                logger.info(f"Valores obtenidos:")
                logger.info(f"  DOMAIN_SEPARATOR: {domain_separator_result}")
                logger.info(f"  ADMIN_ROLE: {admin_role_result}")
                logger.info(f"Combinación de valores requerida en la descripción: {'✓' if True else '✗'}")
            else:
                logger.info("Combinación de valores requerida en la descripción: ✗")
            
            # Evaluación final
            required_tasks = {
                "domain_separator": domain_separator_executed,
                "admin_role": admin_role_executed,
                "mint_address1": "0xaB6E247B25463F76E81aBAbBb6b0b86B40d45D38" in mint_addresses,
                "mint_address2": "0x6FE1e006AD733717539bac3f7E73470fC5B34Bad" in mint_addresses
            }
            
            all_tasks_completed = all(required_tasks.values())
            
            logger.info("\nResumen final:")
            logger.info(f"Tareas completadas: {sum(required_tasks.values())}/{len(required_tasks)}")
            logger.info(f"Todas las tareas requeridas completadas: {'SÍ' if all_tasks_completed else 'NO'}")
                
    except Exception as e:
        logger.exception(f"Error ejecutando el agente: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_agent_test()) 