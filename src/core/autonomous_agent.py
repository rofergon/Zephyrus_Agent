from typing import Dict, List, Optional
import json
import asyncio
from datetime import datetime
import logging
from openai import AsyncOpenAI
from pydantic import BaseModel
from src.utils.logger import setup_logger
from src.api.db_client import DatabaseClient
from src.models.agent import Agent

logger = setup_logger(__name__)

class SmartContractFunction(BaseModel):
    """Represents a smart contract function with its parameters and validation rules"""
    name: str
    type: str  # 'read' or 'write'
    parameters: List[Dict]
    validation_rules: Optional[Dict] = None

class AutonomousAgent:
    """
    An autonomous agent that monitors and interacts with smart contracts.
    Uses OpenAI GPT to analyze state and determine actions.
    """
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.agent: Optional[Agent] = None
        self.functions = []
        self.is_running = False
        self.openai_client = None

    async def initialize(self):
        """
        Inicializa el agente cargando su configuración y funciones
        """
        async with DatabaseClient() as db_client:
            # Cargar configuración del agente
            self.agent = await db_client.get_agent(self.agent_id)
            if not self.agent:
                raise ValueError(f"Agent {self.agent_id} not found")

            # Cargar funciones del agente
            self.functions = await db_client.get_agent_functions(self.agent_id)
            logger.info(f"Agent {self.agent_id} initialized with {len(self.functions)} functions")

            # Inicializar cliente de OpenAI
            self.openai_client = AsyncOpenAI()

    async def execute_function(self, function: Dict):
        """
        Ejecuta una función del contrato a través de la API REST
        """
        try:
            # TODO: Implementar cuando tengamos la documentación de la API REST
            logger.info(f"Would execute function {function['functionName']}")
            
            # Registrar la ejecución
            async with DatabaseClient() as db_client:
                await db_client.create_execution_log(
                    self.agent_id,
                    {
                        "functionName": function["functionName"],
                        "status": "pending",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
        except Exception as e:
            logger.error(f"Error executing function {function['functionName']}: {str(e)}")
            raise

    async def run(self):
        """
        Ejecuta el ciclo principal del agente
        """
        try:
            await self.initialize()
            self.is_running = True
            
            while self.is_running and self.agent.status == "active":
                for function in self.functions:
                    if not function.get("isEnabled", False):
                        continue

                    try:
                        await self.execute_function(function)
                    except Exception as e:
                        logger.error(f"Error executing function {function['functionName']}: {str(e)}")

                # Esperar antes de la siguiente iteración
                await asyncio.sleep(60)  # TODO: Hacer configurable

        except Exception as e:
            logger.error(f"Error in agent main loop: {str(e)}")
            self.is_running = False
            raise

    def stop(self):
        """
        Detiene el agente
        """
        self.is_running = False
        logger.info(f"Agent {self.agent_id} stopped")

    async def start(self):
        """Start the agent's execution loop"""
        self.is_running = True
        self.logger.info(f"Starting agent: {self.agent_id}")
        
        while self.is_running:
            try:
                await self.run()
                await asyncio.sleep(60)  # Wait a minute before retrying
            except Exception as e:
                self.logger.error(f"Error in execution cycle: {str(e)}")
                await asyncio.sleep(60)  # Wait a minute before retrying

    async def stop(self):
        """Stop the agent's execution loop"""
        self.is_running = False
        self.logger.info(f"Stopping agent: {self.agent_id}")

    async def execute_cycle(self):
        """Execute one cycle of the agent's logic"""
        # 1. Get current contract state through read functions
        contract_state = await self.get_contract_state()
        
        # 2. Analyze state and determine actions using OpenAI
        actions = await self.analyze_state(contract_state)
        
        # 3. Execute determined actions
        for action in actions:
            await self.execute_action(action)

    async def get_contract_state(self) -> Dict:
        """Get the current state of the contract through read functions"""
        state = {}
        for function in self.functions:
            if function.type == 'read':
                try:
                    contract_fn = getattr(self.contract.functions, function.name)
                    # For now, we're assuming read functions don't need parameters
                    result = await asyncio.to_thread(contract_fn().call)
                    state[function.name] = result
                except Exception as e:
                    self.logger.error(f"Error reading {function.name}: {str(e)}")
        return state

    async def analyze_state(self, state: Dict) -> List[Dict]:
        """Analyze contract state and determine actions using OpenAI"""
        prompt = self._create_analysis_prompt(state)
        
        response = await self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an autonomous agent managing a smart contract."},
                {"role": "user", "content": prompt}
            ],
            functions=[{
                "name": "execute_contract_function",
                "description": "Execute a function on the smart contract",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "function_name": {"type": "string"},
                        "parameters": {"type": "object"}
                    },
                    "required": ["function_name", "parameters"]
                }
            }]
        )
        
        # Parse the response and return list of actions
        return self._parse_openai_response(response)

    async def execute_action(self, action: Dict):
        """Execute a single action on the contract"""
        function = next(
            (f for f in self.functions if f.name == action['function_name']),
            None
        )
        
        if not function or function.type != 'write':
            self.logger.error(f"Invalid function: {action['function_name']}")
            return
        
        try:
            contract_fn = getattr(self.contract.functions, action['function_name'])
            # Here you would implement the actual transaction sending logic
            # This is a placeholder - you'll need to implement the actual
            # transaction signing and sending mechanism
            self.logger.info(f"Would execute {action['function_name']} with params: {action['parameters']}")
        except Exception as e:
            self.logger.error(f"Error executing {action['function_name']}: {str(e)}")

    def _create_analysis_prompt(self, state: Dict) -> str:
        """Create the prompt for OpenAI based on current state"""
        return f"""
        Current contract state:
        {json.dumps(state, indent=2)}
        
        Agent description:
        {self.agent.description}
        
        Available functions:
        {json.dumps([f.dict() for f in self.functions], indent=2)}
        
        Based on the current state and the agent's description, what actions should be taken?
        Return the actions as function calls using the execute_contract_function format.
        """

    def _parse_openai_response(self, response) -> List[Dict]:
        """Parse OpenAI's response into a list of actions"""
        actions = []
        for choice in response.choices:
            if choice.message.function_call:
                actions.append(json.loads(choice.message.function_call.arguments))
        return actions 