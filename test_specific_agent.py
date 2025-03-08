#!/usr/bin/env python
"""
Script para probar directamente la ejecución del agente específico
que está causando problemas, sin usar WebSockets.
"""
import asyncio
import logging
import sys
import os

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_specific_agent")

# ID del agente a probar
AGENT_ID = "8191feef-546d-46a8-a26f-b92073882f5c"

# Asegurar que podemos importar desde el directorio raíz
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api.db_client import DatabaseClient
from src.core.autonomous_agent import AutonomousAgent
from datetime import datetime

async def run_agent_test():
    """Ejecuta el agente que está causando problemas"""
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
            
            # Datos del trigger
            trigger_data = {
                "trigger_type": "test",
                "timestamp": datetime.now().isoformat(),
                "execution_id": f"test_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            }
            
            # Ejecutar agente
            logger.info("Ejecutando agente...")
            results = await agent.analyze_and_execute(trigger_data)
            
            # Mostrar resultados
            if results:
                logger.info(f"Ejecución completada: {len(results)} acciones")
                for i, result in enumerate(results, 1):
                    function_name = result.get('function_name', 'unknown')
                    status = result.get('status', 'unknown')
                    logger.info(f"Acción {i}: {function_name} - {status}")
            else:
                logger.info("No se ejecutaron acciones")
                
    except Exception as e:
        logger.exception(f"Error ejecutando el agente: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_agent_test()) 