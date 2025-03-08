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

logger = setup_logger("test_agent_execution")

async def test_agent_execution():
    """
    Carga un agente específico desde la base de datos y ejecuta sus funciones.
    """
    agent_id = "8191feef-546d-46a8-a26f-b92073882f5c"
    
    logger.info(f"Iniciando prueba para el agente {agent_id}")
    
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
                
                # Verificar si hay errores o mensajes en los logs
                if "error" in result:
                    print(f"ERROR en la ejecución {i}: {result['error']}")
        else:
            logger.info("No se ejecutó ninguna acción durante el ciclo")
            
        # Recuperar los logs de ejecución para verificar los mensajes
        print("\n=== Verificando logs de ejecución para mensajes ===")
        async with DatabaseClient() as db_client:
            # Aquí necesitamos implementar un método para obtener los logs de ejecución
            # Vamos a simular esta llamada para la prueba
            print(f"Intentando recuperar logs de ejecución para el agente {agent_id}...")
            
            # Esta URL es la que se usa en la documentación
            logs_url = f"{db_client.base_url}/agents/{agent_id}/logs"
            print(f"URL de la API para logs: {logs_url}")
            
            try:
                async with db_client.session.get(logs_url) as response:
                    if response.status == 200:
                        logs_data = await response.json()
                        print(f"Se encontraron {len(logs_data)} registros de logs")
                        
                        for i, log in enumerate(logs_data, 1):
                            print(f"\nLog #{i}:")
                            print(f"  Función: {log.get('function_id')}")
                            print(f"  Estado: {log.get('status')}")
                            print(f"  Tiempo: {log.get('execution_time')}")
                            
                            # Verificar si hay mensaje en error_message
                            if log.get('error_message'):
                                print(f"  MENSAJE: {log.get('error_message')}")
                    else:
                        print(f"Error al recuperar logs. Código: {response.status}")
                        print(await response.text())
            except Exception as e:
                print(f"Error al consultar logs: {str(e)}")
        
        return results
        
    except Exception as e:
        logger.error(f"Error durante la prueba: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    logger.info("Iniciando prueba de ejecución del agente")
    try:
        result = asyncio.run(test_agent_execution())
        logger.info("Prueba completada exitosamente")
    except Exception as e:
        logger.error(f"Error en la prueba: {str(e)}", exc_info=True)
        sys.exit(1) 