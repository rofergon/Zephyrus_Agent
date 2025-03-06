import aiohttp
from typing import Dict, List, Optional
from src.utils.config import DB_API_URL
from src.utils.logger import setup_logger
from src.models.agent import Agent

logger = setup_logger(__name__)

class DatabaseClient:
    def __init__(self, base_url: str = DB_API_URL):
        self.base_url = base_url
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_agent(self, agent_id: str) -> Optional[Agent]:
        """
        Obtiene un agente por su ID
        """
        try:
            async with self.session.get(f"{self.base_url}/agents/{agent_id}") as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                data = await response.json()
                return Agent.from_dict(data)
        except Exception as e:
            logger.error(f"Error getting agent {agent_id}: {str(e)}")
            raise

    async def update_agent(self, agent_id: str, data: Dict) -> Optional[Agent]:
        """
        Actualiza un agente
        """
        try:
            async with self.session.patch(f"{self.base_url}/agents/{agent_id}", json=data) as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                data = await response.json()
                return Agent.from_dict(data)
        except Exception as e:
            logger.error(f"Error updating agent {agent_id}: {str(e)}")
            raise

    async def get_agent_functions(self, agent_id: str) -> List[Dict]:
        """
        Obtiene las funciones de un agente
        """
        try:
            async with self.session.get(f"{self.base_url}/agents/{agent_id}/functions") as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"Error getting functions for agent {agent_id}: {str(e)}")
            raise

    async def create_execution_log(self, agent_id: str, log_data: Dict) -> Dict:
        """
        Crea un registro de ejecución
        """
        try:
            async with self.session.post(f"{self.base_url}/agents/{agent_id}/logs", json=log_data) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"Error creating execution log for agent {agent_id}: {str(e)}")
            raise 