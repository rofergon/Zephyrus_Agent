#!/usr/bin/env python
"""
Script de inicio específico para Railway que garantiza el uso del puerto correcto.
Este script reemplaza directamente las variables de entorno y luego inicia la aplicación.
"""

import os
import sys
import logging
import subprocess

# Configurar logging básico para este script
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('railway_starter')

def main():
    try:
        # Obtener el puerto que Railway proporciona
        railway_port = os.environ.get('PORT')
        
        if not railway_port:
            logger.warning("¡No se encontró la variable PORT de Railway! Usando 8080 como predeterminado.")
            railway_port = "8080"
            os.environ['PORT'] = railway_port
        
        # Forzar el puerto y host en las variables de entorno
        os.environ['WS_PORT'] = railway_port
        os.environ['WS_HOST'] = "0.0.0.0"
        
        # IMPORTANTE: Forzar también modificando la configuración en memoria
        # Esto es crítico para asegurar que se use 0.0.0.0 en lugar de localhost
        
        # Primera impresión para diagnóstico
        logger.info(f"Iniciando aplicación en Railway con PORT={railway_port}")
        logger.info(f"Variables de entorno establecidas: WS_PORT={os.environ.get('WS_PORT')}, WS_HOST={os.environ.get('WS_HOST')}")
        
        # Imprimir todas las variables de entorno relevantes para diagnóstico
        logger.info("Variables de entorno completas:")
        for key, value in os.environ.items():
            if key.startswith('WS_') or key == 'PORT' or key.startswith('RAILWAY_'):
                logger.info(f"  {key}={value}")
        
        # RAILWAY FIX: En lugar de crear un archivo temporal, vamos a usar directamente
        # el archivo railway_patch.py que ahora incluye un servidor HTTP para healthcheck
        
        patch_file = "src/railway_patch.py"
        logger.info(f"Iniciando aplicación con servidor HTTP para healthcheck usando {patch_file}")
        return subprocess.call([sys.executable, patch_file])
        
    except Exception as e:
        logger.error(f"Error al iniciar la aplicación: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 