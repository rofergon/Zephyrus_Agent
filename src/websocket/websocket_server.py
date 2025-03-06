import json
import asyncio
import websockets
from typing import Dict, Set
from src.utils.config import WS_HOST, WS_PORT
from src.utils.logger import setup_logger
from src.core.agent_manager import AgentManager

logger = setup_logger(__name__)

class WebSocketServer:
    def __init__(self, agent_manager: AgentManager):
        self.host = WS_HOST
        self.port = WS_PORT
        self.agent_manager = agent_manager
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.server = None

    async def register(self, websocket: websockets.WebSocketServerProtocol):
        """
        Registra un nuevo cliente WebSocket
        """
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")

    async def unregister(self, websocket: websockets.WebSocketServerProtocol):
        """
        Elimina un cliente WebSocket
        """
        self.clients.remove(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")

    async def broadcast(self, message: Dict):
        """
        Envía un mensaje a todos los clientes conectados
        """
        if not self.clients:
            return

        message_str = json.dumps(message)
        await asyncio.gather(
            *[client.send(message_str) for client in self.clients],
            return_exceptions=True
        )

    async def handle_message(self, websocket: websockets.WebSocketServerProtocol, message: str):
        """
        Maneja los mensajes entrantes de los clientes
        """
        try:
            data = json.loads(message)
            message_type = data.get("type")
            message_data = data.get("data", {})

            if message_type == "add_agent":
                agent_id = message_data.get("agent_id")
                if agent_id:
                    await self.agent_manager.add_agent(agent_id)
                    await self.broadcast({
                        "type": "agent_added",
                        "data": {"agent_id": agent_id}
                    })

            elif message_type == "start_agent":
                agent_id = message_data.get("agent_id")
                if agent_id:
                    await self.agent_manager.start_agent(agent_id)
                    await self.broadcast({
                        "type": "agent_started",
                        "data": {"agent_id": agent_id}
                    })

            elif message_type == "stop_agent":
                agent_id = message_data.get("agent_id")
                if agent_id:
                    self.agent_manager.stop_agent(agent_id)
                    await self.broadcast({
                        "type": "agent_stopped",
                        "data": {"agent_id": agent_id}
                    })

            elif message_type == "remove_agent":
                agent_id = message_data.get("agent_id")
                if agent_id:
                    self.agent_manager.remove_agent(agent_id)
                    await self.broadcast({
                        "type": "agent_removed",
                        "data": {"agent_id": agent_id}
                    })

        except json.JSONDecodeError:
            logger.error("Invalid JSON message received")
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            await websocket.send(json.dumps({
                "type": "error",
                "data": {"message": str(e)}
            }))

    async def handler(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """
        Maneja una conexión WebSocket
        """
        await self.register(websocket)
        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister(websocket)

    async def start(self):
        """
        Inicia el servidor WebSocket
        """
        self.server = await websockets.serve(
            self.handler,
            self.host,
            self.port
        )
        logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")

    async def stop(self):
        """
        Detiene el servidor WebSocket
        """
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("WebSocket server stopped") 