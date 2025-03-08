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
        
        # Imprimir todas las variables de entorno para diagnóstico
        logger.info("Variables de entorno completas:")
        for key, value in os.environ.items():
            if key.startswith('WS_') or key == 'PORT' or key.startswith('RAILWAY_'):
                logger.info(f"  {key}={value}")
        
        # Patchar directamente los módulos de Python para forzar el uso de 0.0.0.0
        # Para hacer esto, vamos a crear un pequeño archivo temporal que inicializará 
        # correctamente y luego llamará a main.py
        
        patch_file = "src/railway_patch.py"
        with open(patch_file, "w") as f:
            f.write("""
import os
import sys

# Forzar las variables críticas antes de importar el resto
os.environ['WS_HOST'] = '0.0.0.0'
os.environ['WS_PORT'] = os.environ.get('PORT', '8080')

# Imprimir confirmación
print(f"[RAILWAY PATCH] Forzando WS_HOST=0.0.0.0 y WS_PORT={os.environ.get('PORT', '8080')}")

# Ahora importar y ejecutar la aplicación principal
sys.path.insert(0, '.')
from src.main import main

if __name__ == "__main__":
    main()
""")
        
        # Iniciar el proceso con el archivo de patch
        logger.info(f"Iniciando aplicación con variables forzadas usando {patch_file}")
        return subprocess.call([sys.executable, patch_file])
        
    except Exception as e:
        logger.error(f"Error al iniciar la aplicación: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 