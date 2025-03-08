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

logger = setup_logger("test_balance_function")

async def test_balance_function():
    """
    Carga un agente específico y ejecuta su función balanceOf para leer el balance de una dirección.
    """
    agent_id = "ec60632c-eae1-44fa-8dbf-e5542cb8edbd"
    address_to_check = "0xaB6E247B25463F76E81aBAbBb6b0b86B40d45D38"  # Dirección del propietario del contrato
    
    logger.info(f"Iniciando prueba para el agente {agent_id}")
    logger.info(f"Verificando balance de la dirección: {address_to_check}")
    
    try:
        # Primero, obtener los datos completos del agente usando DatabaseClient
        logger.info("Obteniendo datos del agente desde la base de datos...")
        async with DatabaseClient() as db_client:
            # Obtener el agente
            agent_data = await db_client.get_agent(agent_id)
            if not agent_data:
                raise ValueError(f"No se encontró el agente con ID {agent_id}")
            
            # Obtener el contrato asociado
            contract_data = await db_client.get_contract(agent_data.contract_id)
            if not contract_data:
                raise ValueError(f"No se encontró el contrato asociado {agent_data.contract_id}")
                
            # Obtener las funciones del agente
            functions_data = await db_client.get_agent_functions(agent_id)
            
            # Obtener la programación del agente (opcional)
            schedule_data = await db_client.get_agent_schedule(agent_id)
            
            logger.info(f"Datos obtenidos correctamente para el agente {agent_id}")
            
            # Preparar la configuración completa para crear el agente
            config = {
                "agent_id": agent_id,
                "contract": contract_data,  # Ahora contract_data es un objeto, no una lista
                "agent": agent_data.to_dict(),
                "functions": [func.to_dict() for func in functions_data],
                "schedule": schedule_data.to_dict() if schedule_data else None
            }
            
            logger.info("Creando instancia del agente con los datos obtenidos...")
            agent = await AutonomousAgent.from_config(config)
        
        logger.info("Inicializando el agente...")
        await agent.initialize()
        
        # Mostrar información del agente
        logger.info(f"Agente cargado exitosamente: {agent.agent.name}")
        
        # Buscar la función balanceOf
        balance_function = None
        for function in agent.functions:
            if function.function_name == "balanceOf" and function.is_enabled:
                balance_function = function
                break
        
        if not balance_function:
            logger.error("No se encontró la función balanceOf habilitada en el agente")
            return
        
        logger.info(f"Función encontrada: {balance_function.function_name} ({balance_function.function_type})")
        
        # Parámetros para la función balanceOf
        params = {
            "account": address_to_check
        }
        
        # Ejecutar la función balanceOf
        logger.info(f"Ejecutando función balanceOf con parámetros: {params}")
        result = await agent.execute_function(balance_function, params)
        
        # Mostrar resultado
        logger.info(f"Balance obtenido: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error durante la prueba: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    logger.info("Iniciando prueba de función balanceOf")
    try:
        result = asyncio.run(test_balance_function())
        logger.info(f"Prueba completada exitosamente. Resultado: {result}")
    except Exception as e:
        logger.error(f"Error en la prueba: {str(e)}", exc_info=True)
        sys.exit(1) 