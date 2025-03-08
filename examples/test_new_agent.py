import asyncio
import sys
import os
import json
from datetime import datetime
from typing import Dict, List, Optional

# Añadir el directorio principal al path para poder importar los módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.autonomous_agent import AutonomousAgent
from src.api.db_client import DatabaseClient
from src.models.agent import Agent, AgentFunction
from src.utils.logger import setup_logger

logger = setup_logger("test_new_agent")

async def test_agent_execution():
    """
    Prueba la creación y ejecución de un agente autónomo con el nuevo ID de agente
    """
    agent_id = "d28e10e1-b0ef-4331-8cce-0c40fb4c6705"  # Nuevo ID de agente
    
    logger.info("Iniciando prueba de ejecución del agente")
    
    try:
        logger.info(f"Iniciando prueba para el agente {agent_id}")
        
        # Obtener los datos del agente desde la base de datos
        logger.info("Obteniendo datos del agente desde la base de datos...")
        
        async with DatabaseClient() as db_client:
            # Obtener el agente
            agent_data = await db_client.get_agent(agent_id)
            if not agent_data:
                logger.error(f"No se encontró el agente con ID {agent_id}")
                return
            
            # Obtener el contrato asociado
            contract_data = await db_client.get_contract(agent_data.contract_id)
            if not contract_data:
                logger.error(f"No se encontró el contrato asociado {agent_data.contract_id}")
                return
            
            # Obtener funciones del agente
            functions_data = await db_client.get_agent_functions(agent_id)
            if not functions_data:
                logger.error(f"No se encontraron funciones para el agente {agent_id}")
                return
            
            # Obtener programación del agente (opcional)
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
        
        # Mostrar información del agente
        logger.info(f"Agente cargado exitosamente:")
        logger.info(f"- Nombre: {agent.agent.name}")
        logger.info(f"- Descripción: {agent.agent.description}")
        logger.info(f"- Estado: {agent.agent.status}")
        logger.info(f"- Contrato: {agent.agent.contract_id}")
        
        # Mostrar funciones disponibles
        logger.info(f"Funciones disponibles ({len(agent.functions)}):")
        for i, function in enumerate(agent.functions, 1):
            logger.info(f"{i}. {function.function_name} ({function.function_type}) - Habilitada: {function.is_enabled}")
        
        # Trigger data para simular una ejecución manual
        trigger_data = {
            "trigger_type": "manual",
            "timestamp": datetime.now().isoformat(),
            "execution_id": f"test_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        }
        
        # Ejecutar el ciclo de análisis y ejecución
        logger.info("Ejecutando ciclo de análisis y ejecución...")
        results = await agent.analyze_and_execute(trigger_data)
        
        # Mostrar resultados
        if results:
            logger.info(f"Resultados de la ejecución ({len(results)} acciones):")
            for i, result in enumerate(results, 1):
                logger.info(f"Resultado {i}:")
                logger.info(json.dumps(result, indent=2))
        else:
            logger.info("No se ejecutó ninguna acción durante el ciclo")
        
        logger.info("Prueba completada exitosamente")
        return results
        
    except Exception as e:
        logger.error(f"Error durante la prueba: {str(e)}", exc_info=True)
        raise e

if __name__ == "__main__":
    try:
        result = asyncio.run(test_agent_execution())
    except Exception as e:
        logger.error(f"Error en la prueba: {str(e)}", exc_info=True)
        sys.exit(1) 