#!/usr/bin/env python
"""
Script para depurar y probar directamente el agente problemático,
con mensajes de log detallados en cada paso.
"""
import asyncio
import logging
import sys
import json
import os
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("debug_agent")

# ID del agente a probar
AGENT_ID = "8191feef-546d-46a8-a26f-b92073882f5c"

# Asegurar que podemos importar desde el directorio raíz
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def debug_agent():
    try:
        logger.info("==== INICIANDO DEPURACIÓN DEL AGENTE ====")
        logger.info(f"Agente ID: {AGENT_ID}")
        
        # 1. IMPORTAR DEPENDENCIAS
        logger.info("Importando dependencias...")
        from src.api.db_client import DatabaseClient
        from src.core.autonomous_agent import AutonomousAgent
        logger.info("Dependencias importadas correctamente")
        
        # 2. CONECTAR A LA BASE DE DATOS
        logger.info("Conectando a la base de datos...")
        async with DatabaseClient() as db_client:
            # 3. OBTENER EL AGENTE
            logger.info(f"Obteniendo agente {AGENT_ID}...")
            agent_data = await db_client.get_agent(AGENT_ID)
            if not agent_data:
                logger.error(f"¡ERROR! El agente {AGENT_ID} no existe")
                return
            
            logger.info(f"Agente obtenido: {agent_data.name}")
            logger.info(f"Descripción: {agent_data.description}")
            
            # 4. OBTENER EL CONTRATO
            logger.info(f"Obteniendo contrato {agent_data.contract_id}...")
            contract_data = await db_client.get_contract(agent_data.contract_id)
            if not contract_data:
                logger.error(f"¡ERROR! El contrato {agent_data.contract_id} no existe")
                return
            
            logger.info(f"Contrato obtenido: {contract_data.get('name', 'Sin nombre')}")
            
            # 5. OBTENER FUNCIONES
            logger.info("Obteniendo funciones del agente...")
            functions = await db_client.get_agent_functions(AGENT_ID)
            logger.info(f"Funciones obtenidas: {len(functions)}")
            
            for i, func in enumerate(functions, 1):
                logger.info(f"  Función {i}: {func.function_name} ({func.function_type})")
                if hasattr(func, 'abi') and func.abi:
                    logger.info(f"    ABI disponible: {func.abi}")
            
            # 6. OBTENER PROGRAMACIÓN
            logger.info("Obteniendo programación del agente...")
            schedule = await db_client.get_agent_schedule(AGENT_ID)
            if schedule:
                logger.info(f"Programación obtenida: {schedule.schedule_type}")
            else:
                logger.info("El agente no tiene programación")
            
            # 7. CREAR CONFIGURACIÓN
            logger.info("Creando configuración del agente...")
            config = {
                "agent_id": AGENT_ID,
                "contract": contract_data,
                "agent": agent_data.to_dict(),
                "functions": [func.to_dict() for func in functions],
                "schedule": schedule.to_dict() if schedule else None
            }
            
            # Omitir imprimir la configuración completa ya que puede ser demasiado grande
            logger.info("Configuración creada")
            
            # 8. CREAR AGENTE
            logger.info("Creando instancia del agente...")
            agent = await AutonomousAgent.from_config(config)
            logger.info("Instancia del agente creada correctamente")
            
            # 9. INICIALIZAR AGENTE
            logger.info("Inicializando agente...")
            await agent.initialize()
            logger.info("Agente inicializado correctamente")
            
            # 10. CREAR TRIGGER DATA
            logger.info("Preparando datos para ejecución...")
            trigger_data = {
                "trigger_type": "debug",
                "timestamp": datetime.now().isoformat(),
                "execution_id": f"debug_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            }
            
            # 11. EJECUTAR AGENTE
            logger.info("==== EJECUTANDO AGENTE ====")
            try:
                results = await agent.analyze_and_execute(trigger_data)
                
                # 12. PROCESAR RESULTADOS
                if results:
                    logger.info(f"==== RESULTADOS ({len(results)} acciones) ====")
                    for i, result in enumerate(results, 1):
                        logger.info(f"Resultado {i}:")
                        logger.info(f"  Función: {result.get('function_name')}")
                        logger.info(f"  Estado: {result.get('status')}")
                        
                        if 'result' in result:
                            if isinstance(result['result'], dict):
                                logger.info(f"  Resultado: {json.dumps(result['result'], indent=2)}")
                            else:
                                logger.info(f"  Resultado: {result['result']}")
                        elif 'error' in result:
                            logger.error(f"  Error: {result['error']}")
                        
                        if 'parameters' in result:
                            logger.info(f"  Parámetros: {json.dumps(result['parameters'], indent=2)}")
                else:
                    logger.info("==== NO SE EJECUTARON ACCIONES ====")
                
                return results
            except Exception as e:
                logger.exception(f"¡ERROR durante la ejecución del agente!: {str(e)}")
                raise
                
    except Exception as e:
        logger.exception(f"¡ERROR en la depuración!: {str(e)}")
        return None

if __name__ == "__main__":
    try:
        logger.info("Iniciando script de depuración")
        results = asyncio.run(debug_agent())
        
        if results:
            logger.info(f"Depuración completada con {len(results)} resultados")
        else:
            logger.warning("Depuración completada sin resultados o con errores")
            
    except KeyboardInterrupt:
        logger.info("Depuración interrumpida por el usuario")
    except Exception as e:
        logger.exception(f"Error fatal: {str(e)}")
        sys.exit(1) 