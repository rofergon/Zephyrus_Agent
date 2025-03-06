"""
WebSocket server for communication with the frontend.
"""
import json
import asyncio
import websockets
from loguru import logger
from typing import Dict, Any, Callable, Optional, List

from ..config.settings import WEBSOCKET_HOST, WEBSOCKET_PORT


class WebSocketServer:
    """
    WebSocket server for communication with the frontend.
    """
    def __init__(self):
        self.host = WEBSOCKET_HOST
        self.port = WEBSOCKET_PORT
        self.clients = set()
        self.agent_config_callback = None
        self.server = None
        
    async def start(self):
        """
        Start the WebSocket server.
        """
        self.server = await websockets.serve(
            self.handle_connection, 
            self.host, 
            self.port
        )
        logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")
        
    def register_agent_config_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Register a callback function to be called when agent configuration is received.
        
        Args:
            callback: Function to call with the agent configuration
        """
        self.agent_config_callback = callback
        
    async def handle_connection(self, websocket, path):
        """
        Handle a WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            path: The connection path
        """
        client_id = id(websocket)
        self.clients.add(websocket)
        logger.info(f"Client connected: {client_id}")
        
        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_id}")
        finally:
            self.clients.remove(websocket)
    
    async def handle_message(self, websocket, message):
        """
        Handle a message from a client.
        
        Args:
            websocket: The WebSocket connection
            message: The message received
        """
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "agent_config":
                await self.handle_agent_config(data.get("data", {}))
                await websocket.send(json.dumps({
                    "type": "agent_config_received",
                    "status": "success"
                }))
            else:
                logger.warning(f"Unknown message type: {message_type}")
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                }))
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {message}")
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Invalid JSON format"
            }))
        except Exception as e:
            logger.exception(f"Error handling message: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "message": str(e)
            }))
    
    async def handle_agent_config(self, config: Dict[str, Any]):
        """
        Handle agent configuration received from the frontend.
        
        Args:
            config: The agent configuration
        """
        logger.info(f"Received agent configuration: {config}")
        
        if self.agent_config_callback:
            self.agent_config_callback(config)
        
    async def broadcast(self, message: Dict[str, Any]):
        """
        Broadcast a message to all connected clients.
        
        Args:
            message: The message to broadcast
        """
        if not self.clients:
            logger.warning("No clients connected, cannot broadcast message")
            return
            
        message_json = json.dumps(message)
        await asyncio.gather(
            *[client.send(message_json) for client in self.clients]
        )
        
    async def send_agent_status(self, status: str, details: Optional[Dict[str, Any]] = None):
        """
        Send agent status update to all connected clients.
        
        Args:
            status: The status of the agent (e.g., "running", "stopped")
            details: Additional details about the status
        """
        await self.broadcast({
            "type": "agent_status",
            "status": status,
            "details": details or {}
        })
        
    async def send_execution_log(self, log: Dict[str, Any]):
        """
        Send execution log to all connected clients.
        
        Args:
            log: The execution log
        """
        await self.broadcast({
            "type": "execution_log",
            "log": log
        })
        
    async def stop(self):
        """
        Stop the WebSocket server.
        """
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("WebSocket server stopped")
