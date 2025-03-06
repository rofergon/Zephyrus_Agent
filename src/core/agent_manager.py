import asyncio
from typing import Dict
from src.core.autonomous_agent import AutonomousAgent
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class AgentManager:
    def __init__(self):
        self.agents: Dict[str, AutonomousAgent] = {}
        self.tasks: Dict[str, asyncio.Task] = {}

    async def add_agent(self, agent_id: str):
        """
        Agrega un nuevo agente al manager
        """
        if agent_id in self.agents:
            logger.warning(f"Agent {agent_id} already exists")
            return

        agent = AutonomousAgent(agent_id)
        try:
            await agent.initialize()
            self.agents[agent_id] = agent
            logger.info(f"Agent {agent_id} added successfully")
        except Exception as e:
            logger.error(f"Error adding agent {agent_id}: {str(e)}")
            raise

    async def start_agent(self, agent_id: str):
        """
        Inicia la ejecución de un agente
        """
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        if agent_id in self.tasks and not self.tasks[agent_id].done():
            logger.warning(f"Agent {agent_id} is already running")
            return

        agent = self.agents[agent_id]
        task = asyncio.create_task(agent.run())
        self.tasks[agent_id] = task
        logger.info(f"Agent {agent_id} started")

    def stop_agent(self, agent_id: str):
        """
        Detiene la ejecución de un agente
        """
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        agent = self.agents[agent_id]
        agent.stop()

        if agent_id in self.tasks and not self.tasks[agent_id].done():
            self.tasks[agent_id].cancel()
        
        logger.info(f"Agent {agent_id} stopped")

    def remove_agent(self, agent_id: str):
        """
        Elimina un agente del manager
        """
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        self.stop_agent(agent_id)
        del self.agents[agent_id]
        if agent_id in self.tasks:
            del self.tasks[agent_id]
        
        logger.info(f"Agent {agent_id} removed")

    async def start_all(self):
        """
        Inicia todos los agentes
        """
        for agent_id in self.agents:
            await self.start_agent(agent_id)

    def stop_all(self):
        """
        Detiene todos los agentes
        """
        for agent_id in list(self.agents.keys()):
            self.stop_agent(agent_id)

    async def cleanup(self):
        """
        Limpia todos los recursos
        """
        self.stop_all()
        # Esperar a que todas las tareas terminen
        if self.tasks:
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)

async def main():
    """Main application entry point"""
    try:
        agent_manager = AgentManager()
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 