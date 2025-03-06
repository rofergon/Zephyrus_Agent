import logging
from pythonjsonlogger import jsonlogger
from .config import LOG_LEVEL, LOG_FORMAT

def setup_logger(name):
    """
    Configura y retorna un logger con el formato especificado
    """
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    # Crear un manejador que escriba logs en formato JSON
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(LOG_FORMAT)
    handler.setFormatter(formatter)
    
    # Agregar el manejador al logger
    logger.addHandler(handler)
    
    return logger 