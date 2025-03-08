#!/usr/bin/env python
"""
Script sencillo para probar la ejecución del agente con un ID específico
sin depender de WebSocket.

Uso: python test_execute_specific_agent.py AGENT_ID
"""

import asyncio
import sys
import logging
import os

# Configurar logging para este script
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_execute_specific_agent")

# Verificar ID del agente
if len(sys.argv) < 2:
    logger.error("Debe proporcionar el ID del agente como argumento")
    print(f"Uso: python {sys.argv[0]} AGENT_ID")
    sys.exit(1)

AGENT_ID = sys.argv[1]
logger.info(f"Probando ejecución directa del agente: {AGENT_ID}")

# Importar desde src/execute_agent_cli.py
try:
    # Añadir el directorio raíz al path
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    from src.execute_agent_cli import execute_agent
    
    async def test_execution():
        """Ejecuta el agente y muestra resultados detallados"""
        logger.info("Iniciando ejecución del agente...")
        
        try:
            result = await execute_agent(AGENT_ID, verbose=True)
            
            if result['success']:
                actions_count = result.get('execution_count', 0)
                logger.info(f"¡Ejecución exitosa! {actions_count} acciones ejecutadas")
                
                # Mostrar detalles de las acciones
                if actions_count > 0:
                    for i, action in enumerate(result.get('results', []), 1):
                        logger.info(f"Acción {i}: {action.get('function_name')} - {action.get('status')}")
                else:
                    logger.info("No se ejecutaron acciones")
                
                return 0
            else:
                logger.error(f"Error: {result.get('error', 'Error desconocido')}")
                return 1
                
        except Exception as e:
            logger.exception(f"Error durante la ejecución: {str(e)}")
            return 1
    
    # Ejecutar el test
    sys.exit(asyncio.run(test_execution()))
    
except ImportError as e:
    logger.error(f"Error importando módulos: {str(e)}")
    sys.exit(1)
except Exception as e:
    logger.exception(f"Error general: {str(e)}")
    sys.exit(1) 