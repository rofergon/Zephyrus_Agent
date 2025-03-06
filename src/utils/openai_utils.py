"""
Utility functions for interacting with the OpenAI API.
"""
import json
from openai import AsyncOpenAI
from loguru import logger
from typing import Dict, Any, List, Optional, Union

from ..config.settings import OPENAI_API_KEY, OPENAI_MODEL


class OpenAIClient:
    """
    Client for interacting with the OpenAI API.
    """
    def __init__(self, api_key: str = OPENAI_API_KEY, model: str = OPENAI_MODEL):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        
    async def analyze_agent_description(self, description: str) -> Dict[str, Any]:
        """
        Analyze the agent description to extract the intended behavior.
        
        Args:
            description: Description of the agent behavior
            
        Returns:
            Dictionary with extracted behavior information
        """
        prompt = f"""
        You are an AI assistant helping to analyze a description of an autonomous agent's behavior.
        The agent will interact with a smart contract on a blockchain.
        
        Please analyze the following description and extract:
        1. The sequence of functions to call
        2. Any conditions for calling these functions
        3. Any parameters that need to be calculated or retrieved
        
        Description:
        {description}
        
        Respond with a JSON object in the following format:
        {{
            "functions_sequence": [
                {{
                    "function_name": "name of the function",
                    "conditions": ["condition 1", "condition 2"],
                    "parameters": [
                        {{
                            "name": "parameter name",
                            "source": "static/calculated/retrieved",
                            "value": "static value or calculation description"
                        }}
                    ]
                }}
            ],
            "execution_logic": "description of the overall execution logic"
        }}
        """
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an AI assistant that analyzes descriptions of autonomous agent behavior and extracts structured information."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"Analyzed agent description: {result}")
            return result
        except Exception as e:
            logger.error(f"Error analyzing agent description: {e}")
            raise
            
    async def validate_function_parameters(self, 
                                         function_name: str, 
                                         parameters: List[Dict[str, Any]], 
                                         validation_rules: Dict[str, Any]) -> Dict[str, bool]:
        """
        Validate function parameters against validation rules.
        
        Args:
            function_name: Name of the function
            parameters: List of parameter values
            validation_rules: Dictionary of validation rules
            
        Returns:
            Dictionary with validation results for each parameter
        """
        prompt = f"""
        You are an AI assistant helping to validate parameters for a smart contract function call.
        
        Function: {function_name}
        Parameters: {json.dumps(parameters)}
        Validation Rules: {json.dumps(validation_rules)}
        
        Please validate each parameter against the rules and respond with a JSON object in the following format:
        {{
            "is_valid": true/false,
            "validation_results": {{
                "parameter_name": {{
                    "is_valid": true/false,
                    "reason": "reason for validation result"
                }}
            }}
        }}
        """
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an AI assistant that validates parameters for smart contract function calls."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"Validated function parameters: {result}")
            return result
        except Exception as e:
            logger.error(f"Error validating function parameters: {e}")
            raise
            
    async def generate_parameter_values(self, 
                                      function_name: str, 
                                      parameter_specs: List[Dict[str, Any]], 
                                      context: Dict[str, Any]) -> List[Any]:
        """
        Generate parameter values for a function call based on specifications and context.
        
        Args:
            function_name: Name of the function
            parameter_specs: List of parameter specifications
            context: Context information for parameter generation
            
        Returns:
            List of generated parameter values
        """
        prompt = f"""
        You are an AI assistant helping to generate parameter values for a smart contract function call.
        
        Function: {function_name}
        Parameter Specifications: {json.dumps(parameter_specs)}
        Context: {json.dumps(context)}
        
        Please generate appropriate values for each parameter based on the specifications and context.
        Respond with a JSON array of parameter values in the correct order for the function call.
        """
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an AI assistant that generates parameter values for smart contract function calls."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"Generated parameter values: {result}")
            return result.get("parameter_values", [])
        except Exception as e:
            logger.error(f"Error generating parameter values: {e}")
            raise
