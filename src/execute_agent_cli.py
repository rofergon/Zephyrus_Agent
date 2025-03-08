#!/usr/bin/env python
import asyncio
import sys
import os
import argparse
import json
from datetime import datetime

# Asegurar que podemos importar desde el directorio raíz
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.autonomous_agent import AutonomousAgent
from src.api.db_client import DatabaseClient
from src.utils.logger import setup_logger

logger = setup_logger("agent_executor_cli")

async def execute_agent(agent_id: str, verbose: bool = False):
    """
    Ejecuta un agente específico desde la línea de comandos.
    
    Args:
        agent_id: ID del agente a ejecutar
        verbose: Si es True, muestra detalles adicionales
    """
    logger.info(f"Iniciando ejecución para el agente {agent_id}")
    
    try:
        # Obtener los datos completos del agente
        logger.info("Obteniendo datos del agente desde la base de datos...")
        async with DatabaseClient() as db_client:
            # Obtener el agente
            agent_data = await db_client.get_agent(agent_id)
            if not agent_data:
                error_msg = f"No se encontró el agente con ID {agent_id}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            
            # Obtener el contrato asociado
            contract_data = await db_client.get_contract(agent_data.contract_id)
            if not contract_data:
                error_msg = f"No se encontró el contrato asociado {agent_data.contract_id}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
                
            # Obtener las funciones del agente
            functions_data = await db_client.get_agent_functions(agent_id)
            
            # Obtener la programación del agente (opcional)
            schedule_data = await db_client.get_agent_schedule(agent_id)
            
            # Mostrar información si es verbose
            if verbose:
                logger.info(f"Agente: {agent_data.name} ({agent_data.agent_id})")
                logger.info(f"Contrato: {agent_data.contract_id}")
                logger.info(f"Funciones disponibles: {len(functions_data)}")
                for i, func in enumerate(functions_data, 1):
                    logger.info(f"  {i}. {func.function_name} ({func.function_type})")
            
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
        
        # Trigger data para simular una ejecución manual
        trigger_data = {
            "trigger_type": "cli",
            "timestamp": datetime.now().isoformat(),
            "execution_id": f"cli_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        }
        
        # Ejecutar el ciclo de análisis y ejecución
        logger.info("Ejecutando ciclo de análisis y ejecución...")
        results = await agent.analyze_and_execute(trigger_data)
        
        # Mostrar resultados
        if results:
            logger.info(f"Resultados de la ejecución ({len(results)} acciones):")
            for i, result in enumerate(results, 1):
                logger.info(f"Resultado {i}:")
                if verbose:
                    logger.info(json.dumps(result, indent=2))
                else:
                    # Versión resumida de los resultados
                    function_name = result.get('function_name', 'unknown_function')
                    status = result.get('status', 'unknown_status')
                    
                    # Extraer resultado o error
                    if 'result' in result:
                        if isinstance(result['result'], dict):
                            result_summary = result['result'].get('message', 'Ver detalles con --verbose')
                        else:
                            result_summary = str(result['result'])
                    elif 'error' in result:
                        result_summary = f"ERROR: {result['error']}"
                    else:
                        result_summary = "No result information"
                    
                    logger.info(f"  Función: {function_name}")
                    logger.info(f"  Estado: {status}")
                    logger.info(f"  Resultado: {result_summary}")
                    logger.info("  --")
            
            return {
                "success": True,
                "results": results,
                "execution_count": len(results)
            }
        else:
            logger.info("No se ejecutó ninguna acción durante el ciclo")
            return {
                "success": True,
                "results": [],
                "execution_count": 0,
                "message": "No se ejecutó ninguna acción durante el ciclo"
            }
            
    except Exception as e:
        error_msg = f"Error durante la ejecución del agente {agent_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": error_msg
        }

def main():
    """Función principal para la ejecución desde línea de comandos"""
    parser = argparse.ArgumentParser(description='Ejecutar un agente autónomo')
    parser.add_argument('agent_id', help='ID del agente a ejecutar')
    parser.add_argument('--verbose', '-v', action='store_true', help='Mostrar detalles adicionales')
    
    args = parser.parse_args()
    
    try:
        result = asyncio.run(execute_agent(args.agent_id, args.verbose))
        
        if result['success']:
            execution_count = result.get('execution_count', 0)
            logger.info(f"Ejecución completada: {execution_count} acciones realizadas")
            sys.exit(0)
        else:
            logger.error(f"Error en la ejecución: {result.get('error', 'Error desconocido')}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Ejecución cancelada por el usuario")
        sys.exit(130)  # 128 + SIGINT(2)
    except Exception as e:
        logger.error(f"Error no controlado: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 