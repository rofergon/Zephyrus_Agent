"""
Contract actions for interacting with smart contracts.
"""
import json
from loguru import logger
from typing import Dict, Any, List, Optional, Union

from ..utils.blockchain import BlockchainClient
from ..utils.openai_utils import OpenAIClient


class ContractAction:
    """
    Base class for contract actions.
    """
    def __init__(self, 
                contract_address: str, 
                abi: List[Dict[str, Any]],
                network_id: int = 57054):
        self.contract_address = contract_address
        self.abi = abi
        self.network_id = network_id
        self.blockchain_client = BlockchainClient()
        self.openai_client = OpenAIClient()
        
    async def validate_function(self, function_name: str) -> Optional[Dict[str, Any]]:
        """
        Validate that a function exists in the contract ABI.
        
        Args:
            function_name: Name of the function
            
        Returns:
            Function details or None if function does not exist
        """
        return await self.blockchain_client.validate_contract_function(self.abi, function_name)
        
    async def get_function_type(self, function_name: str) -> Optional[str]:
        """
        Get the type of a function (read or write).
        
        Args:
            function_name: Name of the function
            
        Returns:
            "read" for view/pure functions, "write" for state-changing functions, or None if function does not exist
        """
        return await self.blockchain_client.get_function_type(self.abi, function_name)
        
    async def validate_parameters(self, 
                                function_name: str, 
                                parameters: List[Any], 
                                validation_rules: Dict[str, Any]) -> Dict[str, bool]:
        """
        Validate parameters for a function call.
        
        Args:
            function_name: Name of the function
            parameters: List of parameter values
            validation_rules: Dictionary of validation rules
            
        Returns:
            Dictionary with validation results
        """
        return await self.openai_client.validate_function_parameters(
            function_name, 
            parameters, 
            validation_rules
        )
        
    async def generate_parameters(self, 
                               function_name: str, 
                               parameter_specs: List[Dict[str, Any]], 
                               context: Dict[str, Any]) -> List[Any]:
        """
        Generate parameters for a function call.
        
        Args:
            function_name: Name of the function
            parameter_specs: List of parameter specifications
            context: Context information for parameter generation
            
        Returns:
            List of generated parameter values
        """
        return await self.openai_client.generate_parameter_values(
            function_name, 
            parameter_specs, 
            context
        )


class ReadContractAction(ContractAction):
    """
    Action for reading data from a contract.
    """
    async def execute(self, 
                    function_name: str, 
                    parameters: List[Any], 
                    validation_rules: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a read action on a contract.
        
        Args:
            function_name: Name of the function to call
            parameters: List of parameter values
            validation_rules: Optional validation rules for parameters
            
        Returns:
            Dictionary with execution result
        """
        # Validate function
        function = await self.validate_function(function_name)
        if not function:
            logger.error(f"Function {function_name} does not exist in contract ABI")
            return {
                "success": False,
                "error": f"Function {function_name} does not exist in contract ABI"
            }
            
        # Validate function type
        function_type = await self.get_function_type(function_name)
        if function_type != "read":
            logger.error(f"Function {function_name} is not a read function")
            return {
                "success": False,
                "error": f"Function {function_name} is not a read function"
            }
            
        # Validate parameters if validation rules are provided
        if validation_rules:
            validation_result = await self.validate_parameters(
                function_name, 
                parameters, 
                validation_rules
            )
            
            if not validation_result.get("is_valid", False):
                logger.error(f"Invalid parameters for function {function_name}: {validation_result}")
                return {
                    "success": False,
                    "error": "Invalid parameters",
                    "validation_result": validation_result
                }
                
        # Call the function
        try:
            async with self.blockchain_client:
                result = await self.blockchain_client.call_read_function(
                    self.contract_address,
                    function_name,
                    parameters,
                    self.abi,
                    self.network_id
                )
                
            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            logger.exception(f"Error calling read function {function_name}: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class WriteContractAction(ContractAction):
    """
    Action for writing data to a contract.
    """
    async def execute(self, 
                    function_name: str, 
                    parameters: List[Any], 
                    validation_rules: Optional[Dict[str, Any]] = None,
                    gas_limit: Optional[str] = None,
                    max_priority_fee: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a write action on a contract.
        
        Args:
            function_name: Name of the function to call
            parameters: List of parameter values
            validation_rules: Optional validation rules for parameters
            gas_limit: Optional gas limit for the transaction
            max_priority_fee: Optional max priority fee for the transaction
            
        Returns:
            Dictionary with execution result
        """
        # Validate function
        function = await self.validate_function(function_name)
        if not function:
            logger.error(f"Function {function_name} does not exist in contract ABI")
            return {
                "success": False,
                "error": f"Function {function_name} does not exist in contract ABI"
            }
            
        # Validate function type
        function_type = await self.get_function_type(function_name)
        if function_type != "write":
            logger.error(f"Function {function_name} is not a write function")
            return {
                "success": False,
                "error": f"Function {function_name} is not a write function"
            }
            
        # Validate parameters if validation rules are provided
        if validation_rules:
            validation_result = await self.validate_parameters(
                function_name, 
                parameters, 
                validation_rules
            )
            
            if not validation_result.get("is_valid", False):
                logger.error(f"Invalid parameters for function {function_name}: {validation_result}")
                return {
                    "success": False,
                    "error": "Invalid parameters",
                    "validation_result": validation_result
                }
                
        # Call the function
        try:
            async with self.blockchain_client:
                tx_hash = await self.blockchain_client.call_write_function(
                    self.contract_address,
                    function_name,
                    parameters,
                    self.abi,
                    gas_limit,
                    max_priority_fee,
                    self.network_id
                )
                
                # Get transaction receipt
                receipt = await self.blockchain_client.get_transaction_receipt(
                    tx_hash,
                    self.network_id
                )
                
            return {
                "success": True,
                "transaction_hash": tx_hash,
                "receipt": receipt
            }
        except Exception as e:
            logger.exception(f"Error calling write function {function_name}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
