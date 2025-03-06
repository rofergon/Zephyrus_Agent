"""
Utility functions for interacting with the blockchain via the Hardhat API.
"""
import json
import aiohttp
from loguru import logger
from typing import Dict, Any, List, Optional, Union

from ..config.settings import HARDHAT_API_URL


class BlockchainClient:
    """
    Client for interacting with the blockchain via the Hardhat API.
    """
    def __init__(self, api_url: str = HARDHAT_API_URL):
        self.api_url = api_url
        self.session = None
        
    async def __aenter__(self):
        """
        Create a new aiohttp session when entering a context.
        """
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Close the aiohttp session when exiting a context.
        """
        if self.session:
            await self.session.close()
            self.session = None
            
    async def _ensure_session(self):
        """
        Ensure that a session exists.
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
            
    async def _make_request(self, endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a request to the Hardhat API.
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            data: Request data
            
        Returns:
            Response data
        """
        await self._ensure_session()
        
        url = f"{self.api_url}/{endpoint}"
        
        try:
            if method == "GET":
                async with self.session.get(url) as response:
                    response.raise_for_status()
                    return await response.json()
            elif method == "POST":
                async with self.session.post(url, json=data) as response:
                    response.raise_for_status()
                    return await response.json()
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except aiohttp.ClientError as e:
            logger.error(f"Error making request to {url}: {e}")
            raise
            
    async def call_read_function(self, 
                               contract_address: str, 
                               function_name: str, 
                               function_args: List[Any],
                               abi: List[Dict[str, Any]],
                               network_id: int = 57054) -> Any:
        """
        Call a read function on a contract.
        
        Args:
            contract_address: Address of the contract
            function_name: Name of the function to call
            function_args: Arguments to pass to the function
            abi: Contract ABI
            network_id: Network ID
            
        Returns:
            Function result
        """
        data = {
            "contractAddress": contract_address,
            "functionName": function_name,
            "functionArgs": function_args,
            "abi": abi,
            "networkId": network_id
        }
        
        logger.info(f"Calling read function {function_name} on contract {contract_address}")
        
        try:
            result = await self._make_request("call-read-function", "POST", data)
            logger.info(f"Read function {function_name} result: {result}")
            return result.get("result")
        except Exception as e:
            logger.error(f"Error calling read function {function_name}: {e}")
            raise
            
    async def call_write_function(self, 
                                contract_address: str, 
                                function_name: str, 
                                function_args: List[Any],
                                abi: List[Dict[str, Any]],
                                gas_limit: Optional[str] = None,
                                max_priority_fee: Optional[str] = None,
                                network_id: int = 57054) -> str:
        """
        Call a write function on a contract.
        
        Args:
            contract_address: Address of the contract
            function_name: Name of the function to call
            function_args: Arguments to pass to the function
            abi: Contract ABI
            gas_limit: Gas limit for the transaction
            max_priority_fee: Max priority fee for the transaction
            network_id: Network ID
            
        Returns:
            Transaction hash
        """
        data = {
            "contractAddress": contract_address,
            "functionName": function_name,
            "functionArgs": function_args,
            "abi": abi,
            "networkId": network_id
        }
        
        if gas_limit:
            data["gasLimit"] = gas_limit
            
        if max_priority_fee:
            data["maxPriorityFee"] = max_priority_fee
            
        logger.info(f"Calling write function {function_name} on contract {contract_address}")
        
        try:
            result = await self._make_request("call-write-function", "POST", data)
            tx_hash = result.get("transactionHash")
            logger.info(f"Write function {function_name} transaction hash: {tx_hash}")
            return tx_hash
        except Exception as e:
            logger.error(f"Error calling write function {function_name}: {e}")
            raise
            
    async def get_transaction_receipt(self, tx_hash: str, network_id: int = 57054) -> Dict[str, Any]:
        """
        Get a transaction receipt.
        
        Args:
            tx_hash: Transaction hash
            network_id: Network ID
            
        Returns:
            Transaction receipt
        """
        data = {
            "transactionHash": tx_hash,
            "networkId": network_id
        }
        
        try:
            result = await self._make_request("get-transaction-receipt", "POST", data)
            return result.get("receipt")
        except Exception as e:
            logger.error(f"Error getting transaction receipt for {tx_hash}: {e}")
            raise
            
    async def validate_contract_function(self, 
                                       abi: List[Dict[str, Any]], 
                                       function_name: str) -> Optional[Dict[str, Any]]:
        """
        Validate that a function exists in a contract ABI and return its details.
        
        Args:
            abi: Contract ABI
            function_name: Name of the function
            
        Returns:
            Function details or None if function does not exist
        """
        for item in abi:
            if item.get("type") == "function" and item.get("name") == function_name:
                return item
                
        return None
        
    async def get_function_type(self, abi: List[Dict[str, Any]], function_name: str) -> Optional[str]:
        """
        Get the type of a function (read or write).
        
        Args:
            abi: Contract ABI
            function_name: Name of the function
            
        Returns:
            "read" for view/pure functions, "write" for state-changing functions, or None if function does not exist
        """
        function = await self.validate_contract_function(abi, function_name)
        
        if not function:
            return None
            
        # View and pure functions are read-only
        if function.get("stateMutability") in ["view", "pure"]:
            return "read"
        else:
            return "write"
