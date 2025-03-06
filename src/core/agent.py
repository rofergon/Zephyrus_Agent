"""
Main agent class for coordinating all components.
"""
import json
import uuid
from loguru import logger
from typing import Dict, Any, List, Optional, Union

from ..actions.contract_actions import ReadContractAction, WriteContractAction
from ..utils.openai_utils import OpenAIClient
from .scheduler import Scheduler
from .websocket_server import WebSocketServer


class Agent:
    """
    Main agent class for coordinating all components.
    """
    def __init__(self):
        self.scheduler = Scheduler()
        self.websocket_server = WebSocketServer()
        self.openai_client = OpenAIClient()
        self.config = None
        self.execution_plan = None
        self.read_action = None
        self.write_action = None
        
    async def start(self):
        """
        Start the agent.
        """
        # Register callback for agent configuration
        self.websocket_server.register_agent_config_callback(self.configure)
        
        # Start the WebSocket server
        await self.websocket_server.start()
        
        # Start the scheduler
        await self.scheduler.start()
        
        logger.info("Agent started")
        
    async def stop(self):
        """
        Stop the agent.
        """
        # Stop the scheduler
        await self.scheduler.stop()
        
        # Stop the WebSocket server
        await self.websocket_server.stop()
        
        logger.info("Agent stopped")
        
    async def configure(self, config: Dict[str, Any]):
        """
        Configure the agent with the provided configuration.
        
        Args:
            config: Agent configuration
        """
        logger.info(f"Configuring agent with: {config}")
        
        # Store the configuration
        self.config = config
        
        # Extract configuration values
        agent_name = config.get("name", "Unnamed Agent")
        agent_description = config.get("description", "")
        contract_address = config.get("contractAddress", "")
        contract_abi = config.get("abi", [])
        execution_schedule_minutes = int(config.get("executionScheduleMinutes", 5))
        functions = config.get("functions", [])
        network_id = int(config.get("networkId", 57054))
        
        # Create contract actions
        self.read_action = ReadContractAction(contract_address, contract_abi, network_id)
        self.write_action = WriteContractAction(contract_address, contract_abi, network_id)
        
        # Analyze agent description to extract execution plan
        self.execution_plan = await self.openai_client.analyze_agent_description(agent_description)
        
        # Create a task for the agent execution
        agent_id = str(uuid.uuid4())
        await self.scheduler.add_task(
            task_id=agent_id,
            callback=self.execute_agent_actions,
            interval_minutes=execution_schedule_minutes,
            kwargs={
                "agent_id": agent_id,
                "agent_name": agent_name
            }
        )
        
        # Send agent status update
        await self.websocket_server.send_agent_status(
            status="configured",
            details={
                "agent_id": agent_id,
                "agent_name": agent_name,
                "execution_schedule_minutes": execution_schedule_minutes
            }
        )
        
        logger.info(f"Agent {agent_name} configured with ID {agent_id}")
        
    async def execute_agent_actions(self, agent_id: str, agent_name: str):
        """
        Execute the agent actions according to the execution plan.
        
        Args:
            agent_id: ID of the agent
            agent_name: Name of the agent
        """
        if not self.execution_plan:
            logger.error("No execution plan available")
            await self.websocket_server.send_execution_log({
                "agent_id": agent_id,
                "agent_name": agent_name,
                "status": "error",
                "message": "No execution plan available"
            })
            return
            
        logger.info(f"Executing actions for agent {agent_name} ({agent_id})")
        
        # Send execution start log
        await self.websocket_server.send_execution_log({
            "agent_id": agent_id,
            "agent_name": agent_name,
            "status": "started",
            "timestamp": "now"
        })
        
        # Execute functions in sequence
        execution_results = []
        execution_context = {}
        
        for function_info in self.execution_plan.get("functions_sequence", []):
            function_name = function_info.get("function_name")
            conditions = function_info.get("conditions", [])
            parameters_info = function_info.get("parameters", [])
            
            # Check if all conditions are met
            all_conditions_met = True
            for condition in conditions:
                # TODO: Implement condition checking
                pass
                
            if not all_conditions_met:
                logger.info(f"Skipping function {function_name} because conditions are not met")
                continue
                
            # Get function type
            function_type = await self.read_action.get_function_type(function_name)
            
            if not function_type:
                logger.error(f"Function {function_name} does not exist in contract ABI")
                execution_results.append({
                    "function_name": function_name,
                    "status": "error",
                    "error": f"Function {function_name} does not exist in contract ABI"
                })
                continue
                
            # Generate parameters
            parameters = []
            for param_info in parameters_info:
                param_name = param_info.get("name")
                param_source = param_info.get("source")
                param_value = param_info.get("value")
                
                if param_source == "static":
                    parameters.append(param_value)
                elif param_source == "calculated":
                    # TODO: Implement parameter calculation
                    pass
                elif param_source == "retrieved":
                    # Use value from execution context
                    if param_value in execution_context:
                        parameters.append(execution_context[param_value])
                    else:
                        logger.error(f"Parameter {param_name} value {param_value} not found in execution context")
                        execution_results.append({
                            "function_name": function_name,
                            "status": "error",
                            "error": f"Parameter {param_name} value {param_value} not found in execution context"
                        })
                        continue
                        
            # Execute function
            if function_type == "read":
                result = await self.read_action.execute(function_name, parameters)
            else:  # function_type == "write"
                result = await self.write_action.execute(function_name, parameters)
                
            # Store result in execution context
            if result.get("success"):
                if function_type == "read":
                    execution_context[function_name] = result.get("result")
                else:
                    execution_context[function_name] = result.get("transaction_hash")
                    
            # Add result to execution results
            execution_results.append({
                "function_name": function_name,
                "status": "success" if result.get("success") else "error",
                "result": result
            })
            
        # Send execution complete log
        await self.websocket_server.send_execution_log({
            "agent_id": agent_id,
            "agent_name": agent_name,
            "status": "completed",
            "timestamp": "now",
            "results": execution_results
        })
        
        logger.info(f"Execution completed for agent {agent_name} ({agent_id})")
        
    async def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the agent.
        
        Returns:
            Dictionary with agent status
        """
        tasks = self.scheduler.get_all_tasks()
        
        return {
            "is_configured": self.config is not None,
            "agent_name": self.config.get("name", "Unnamed Agent") if self.config else None,
            "tasks": tasks
        }
