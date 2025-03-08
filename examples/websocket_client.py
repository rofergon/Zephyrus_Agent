import asyncio
import websockets
import json

# Configuración del agente de ejemplo
AGENT_CONFIG = {
    "agent": {
        "agentId": "db6aa8e0-501c-460a-a567-627f76a62dae",
        "contractId": "0xa199dadb19440efdd5d9f19de435d070b9c05c94",
        "name": "Smart Contract Agent",
        "description": "dfasdfasdfasefawef",
        "status": "paused",
        "gasLimit": "300000",
        "maxPriorityFee": "1.5",
        "created_at": "2025-03-06T19:02:41.790Z",
        "updated_at": "2025-03-06T19:02:41.790Z",
        "owner": "0xaB6E247B25463F76E81aBAbBb6b0b86B40d45D38",
        "contractState": {
            "paused": False,
            "symbol": "TEST"
        }
    },
    "functions": [
        {
            "functionId": "04ae3685-552a-4258-bf49-b1afdb7ea420",
            "agentId": "db6aa8e0-501c-460a-a567-627f76a62dae",
            "functionName": "balanceOf",
            "functionSignature": "balanceOf(address)",
            "functionType": "read",
            "isEnabled": True,
            "validationRules": {
                "account": {}
            },
            "abi": {
                "inputs": [
                    {
                        "internalType": "address",
                        "name": "account",
                        "type": "address"
                    }
                ],
                "name": "balanceOf",
                "outputs": [
                    {
                        "internalType": "uint256",
                        "name": "",
                        "type": "uint256"
                    }
                ],
                "stateMutability": "view",
                "type": "function"
            },
            "created_at": "2025-03-06T19:02:41.790Z",
            "updated_at": "2025-03-06T19:02:41.790Z"
        }
    ],
    "schedule": None,
    "notifications": []
}

async def send_agent_config():
    # Conectar al servidor WebSocket
    uri = "ws://localhost:8765"  # Ajusta según tu configuración
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Conectado al servidor WebSocket")
            
            # Crear mensaje para configurar el agente
            message = {
                "type": "configure_agent",
                "data": AGENT_CONFIG
            }
            
            # Enviar configuración
            await websocket.send(json.dumps(message))
            print("Configuración enviada")
            
            # Esperar respuesta
            response = await websocket.recv()
            print(f"Respuesta recibida: {response}")
            
            # Mantener la conexión abierta para recibir actualizaciones
            while True:
                try:
                    update = await websocket.recv()
                    print(f"Actualización recibida: {update}")
                except websockets.ConnectionClosed:
                    print("Conexión cerrada por el servidor")
                    break
                
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    # Ejecutar el cliente
    asyncio.run(send_agent_config()) 