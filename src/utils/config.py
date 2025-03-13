import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# API URLs
DB_API_URL = os.getenv('DB_API_URL', 'https://5d91014c0172.ngrok.app/api/db')
# URL base para la API de contratos (sin /db)
CONTRACT_API_URL = os.getenv('CONTRACT_API_URL', 
                          DB_API_URL.replace('/api/db', '/api') if '/api/db' in DB_API_URL 
                          else 'https://5d91014c0172.ngrok.app/api')
BLOCKCHAIN_API_URL = os.getenv('BLOCKCHAIN_API_URL', '')

# Configuración del WebSocket
# En Railway, necesitamos usar 0.0.0.0 para el host y la variable PORT que Railway proporciona
WS_HOST = os.getenv('WS_HOST', 'localhost')
# Asegúrate de que el puerto es un entero y usa el PORT de Railway si está disponible
WS_PORT = int(os.getenv('PORT', os.getenv('WS_PORT', '8765')))

# Configuración del agente
AGENT_CHECK_INTERVAL = int(os.getenv('AGENT_CHECK_INTERVAL', '60'))  # segundos
DEFAULT_GAS_LIMIT = os.getenv('DEFAULT_GAS_LIMIT', '1000000')
DEFAULT_MAX_PRIORITY_FEE = os.getenv('DEFAULT_MAX_PRIORITY_FEE', '2')

# Configuración de logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s' 