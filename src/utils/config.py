import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# API URLs
DB_API_URL = os.getenv('DB_API_URL', 'https://069c626bcc34.ngrok.app/api/db')
BLOCKCHAIN_API_URL = os.getenv('BLOCKCHAIN_API_URL', '')

# Configuración del WebSocket
WS_HOST = os.getenv('WS_HOST', 'localhost')
WS_PORT = int(os.getenv('WS_PORT', '8765'))

# Configuración del agente
AGENT_CHECK_INTERVAL = int(os.getenv('AGENT_CHECK_INTERVAL', '60'))  # segundos
DEFAULT_GAS_LIMIT = os.getenv('DEFAULT_GAS_LIMIT', '1000000')
DEFAULT_MAX_PRIORITY_FEE = os.getenv('DEFAULT_MAX_PRIORITY_FEE', '2')

# Configuración de logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s' 