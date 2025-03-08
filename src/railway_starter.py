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
        
        # Forzar el puerto en las variables de entorno
        os.environ['WS_PORT'] = railway_port
        os.environ['WS_HOST'] = "0.0.0.0"
        
        logger.info(f"Iniciando aplicación en Railway con PORT={railway_port}")
        logger.info(f"Variables de entorno establecidas: WS_PORT={os.environ.get('WS_PORT')}, WS_HOST={os.environ.get('WS_HOST')}")
        
        # Iniciar el proceso principal de la aplicación
        # Usamos subprocess.call para que se ejecute en el mismo proceso
        return subprocess.call([sys.executable, "src/main.py"])
        
    except Exception as e:
        logger.error(f"Error al iniciar la aplicación: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 