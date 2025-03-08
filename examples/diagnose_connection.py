import asyncio
import sys
import os
import json
import aiohttp
from typing import Dict, Optional

# Añadir el directorio principal al path para poder importar los módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.db_client import DB_API_URL, CONTRACT_API_URL
from src.utils.logger import setup_logger

logger = setup_logger("diagnose_connection")

async def check_api_endpoint(session: aiohttp.ClientSession, url: str, description: str) -> Dict:
    """
    Verifica la disponibilidad de un endpoint de API
    """
    try:
        logger.info(f"Verificando {description} en {url}...")
        async with session.get(url) as response:
            status = response.status
            if status == 200:
                result = await response.text()
                logger.info(f"✅ Conexión exitosa a {description} - Status: {status}")
                return {
                    "endpoint": url,
                    "description": description,
                    "status": status,
                    "success": True,
                    "data": result[:200] + "..." if len(result) > 200 else result
                }
            else:
                logger.error(f"❌ Error conectando a {description} - Status: {status}")
                return {
                    "endpoint": url,
                    "description": description,
                    "status": status,
                    "success": False,
                    "error": await response.text()
                }
    except Exception as e:
        logger.error(f"❌ Error conectando a {description}: {str(e)}")
        return {
            "endpoint": url,
            "description": description,
            "status": None,
            "success": False,
            "error": str(e)
        }

async def diagnose_connections():
    """
    Diagnóstico completo de conexiones a las APIs necesarias
    """
    logger.info("Iniciando diagnóstico de conexiones...")
    
    # Endpoints a verificar
    endpoints = [
        # API de base de datos
        {"url": f"{DB_API_URL}/status", "description": "API de base de datos (status)"},
        {"url": f"{DB_API_URL}/agents", "description": "API de base de datos (agents)"},
        
        # API de contratos
        {"url": f"{CONTRACT_API_URL}/contracts/status", "description": "API de contratos (status)"},
    ]
    
    results = []
    
    # Verificar variables de entorno
    logger.info("Variables de entorno:")
    logger.info(f"DB_API_URL: {DB_API_URL}")
    logger.info(f"CONTRACT_API_URL: {CONTRACT_API_URL}")
    
    # Verificar conexiones HTTP a los endpoints
    async with aiohttp.ClientSession() as session:
        for endpoint in endpoints:
            result = await check_api_endpoint(session, endpoint["url"], endpoint["description"])
            results.append(result)
        
        # Intentar obtener un contrato específico a modo de prueba
        contract_id = "0xf079491ce07c2fa473ed7c9bdfd01861fa498b57"
        contract_url = f"{DB_API_URL}/contracts/{contract_id}"
        contract_result = await check_api_endpoint(session, contract_url, f"API de contratos (obtener contrato {contract_id})")
        results.append(contract_result)
        
        # Intentar obtener información del agente
        agent_id = "ec60632c-eae1-44fa-8dbf-e5542cb8edbd"
        agent_url = f"{DB_API_URL}/agents/getById/{agent_id}"
        agent_result = await check_api_endpoint(session, agent_url, f"API de agentes (obtener agente {agent_id})")
        results.append(agent_result)
    
    # Resumen del diagnóstico
    success_count = sum(1 for r in results if r["success"])
    logger.info(f"\nResumen del diagnóstico:")
    logger.info(f"✅ Conexiones exitosas: {success_count}/{len(results)}")
    logger.info(f"❌ Conexiones fallidas: {len(results) - success_count}/{len(results)}")
    
    # Mostrar resultados detallados
    logger.info("\nResultados detallados:")
    for i, result in enumerate(results, 1):
        status = "✅ OK" if result["success"] else "❌ ERROR"
        logger.info(f"{i}. {status} - {result['description']} ({result['endpoint']})")
        if not result["success"]:
            logger.info(f"   Error: {result.get('error', 'Desconocido')}")
    
    return results

if __name__ == "__main__":
    logger.info("Iniciando diagnóstico de conexiones a APIs")
    try:
        results = asyncio.run(diagnose_connections())
        logger.info("Diagnóstico completado")
        
        # Si hay errores, salir con código de error
        if any(not r["success"] for r in results):
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error durante el diagnóstico: {str(e)}", exc_info=True)
        sys.exit(1) 