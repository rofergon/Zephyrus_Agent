import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from src.core.autonomous_agent import AutonomousAgent
from src.models.agent import Agent, AgentFunction, AgentSchedule

# Configuración de prueba del agente
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

@pytest.fixture
def mock_db_client():
    """Fixture para crear un mock del DatabaseClient"""
    mock = AsyncMock()
    
    # Crear objetos Pydantic para el retorno
    agent_data = AGENT_CONFIG["agent"]
    agent = Agent(
        agent_id=agent_data["agentId"],
        contract_id=agent_data["contractId"],
        name=agent_data["name"],
        description=agent_data["description"],
        status=agent_data["status"],
        gas_limit=agent_data["gasLimit"],
        max_priority_fee=agent_data["maxPriorityFee"],
        owner=agent_data["owner"],
        contract_state=agent_data["contractState"],
        created_at=agent_data["created_at"],
        updated_at=agent_data["updated_at"]
    )
    
    functions = [
        AgentFunction(
            function_id=f["functionId"],
            agent_id=f["agentId"],
            function_name=f["functionName"],
            function_signature=f["functionSignature"],
            function_type=f["functionType"],
            is_enabled=f["isEnabled"],
            validation_rules=f["validationRules"],
            abi=f["abi"],
            created_at=f["created_at"],
            updated_at=f["updated_at"]
        ) for f in AGENT_CONFIG["functions"]
    ]
    
    schedule = None if AGENT_CONFIG["schedule"] is None else AgentSchedule(**AGENT_CONFIG["schedule"])
    
    # Configurar el mock para devolver los objetos Pydantic
    mock.configure_agent = AsyncMock(return_value=(agent, functions, schedule))
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    
    return mock

@pytest.mark.asyncio
async def test_agent_configuration_new(mock_db_client):
    """Test para verificar la creación de un nuevo agente"""
    
    # Patch del DatabaseClient
    with patch('src.core.autonomous_agent.DatabaseClient', return_value=mock_db_client):
        # Crear instancia del agente desde la configuración
        agent = await AutonomousAgent.from_config(AGENT_CONFIG)
        
        # Verificar que el agente se creó correctamente
        assert agent.agent_id == AGENT_CONFIG["agent"]["agentId"]
        assert agent.agent.name == AGENT_CONFIG["agent"]["name"]
        assert agent.agent.status == AGENT_CONFIG["agent"]["status"]
        assert agent.agent.gas_limit == AGENT_CONFIG["agent"]["gasLimit"]
        assert agent.agent.max_priority_fee == AGENT_CONFIG["agent"]["maxPriorityFee"]
        
        # Verificar que las funciones se configuraron correctamente
        assert len(agent.functions) == len(AGENT_CONFIG["functions"])
        for i, function in enumerate(agent.functions):
            assert function.function_id == AGENT_CONFIG["functions"][i]["functionId"]
            assert function.function_name == AGENT_CONFIG["functions"][i]["functionName"]
            assert function.function_type == AGENT_CONFIG["functions"][i]["functionType"]
            assert function.is_enabled == AGENT_CONFIG["functions"][i]["isEnabled"]
        
        # Verificar que se llamó al método configure_agent del DatabaseClient
        mock_db_client.configure_agent.assert_called_once_with(AGENT_CONFIG)

@pytest.mark.asyncio
async def test_agent_configuration_existing(mock_db_client):
    """Test para verificar la actualización de un agente existente"""
    
    # Simular que el agente ya existe con un estado diferente
    agent_data = AGENT_CONFIG["agent"]
    existing_agent = Agent(
        agent_id=agent_data["agentId"],
        contract_id=agent_data["contractId"],
        name=agent_data["name"],
        description=agent_data["description"],
        status="active",  # Cambio para simular una actualización
        gas_limit=agent_data["gasLimit"],
        max_priority_fee=agent_data["maxPriorityFee"],
        owner=agent_data["owner"],
        contract_state=agent_data["contractState"],
        created_at=agent_data["created_at"],
        updated_at=agent_data["updated_at"]
    )
    
    mock_db_client.configure_agent = AsyncMock(return_value=(
        existing_agent,
        [AgentFunction(
            function_id=f["functionId"],
            agent_id=f["agentId"],
            function_name=f["functionName"],
            function_signature=f["functionSignature"],
            function_type=f["functionType"],
            is_enabled=f["isEnabled"],
            validation_rules=f["validationRules"],
            abi=f["abi"],
            created_at=f["created_at"],
            updated_at=f["updated_at"]
        ) for f in AGENT_CONFIG["functions"]],
        None
    ))
    
    # Patch del DatabaseClient
    with patch('src.core.autonomous_agent.DatabaseClient', return_value=mock_db_client):
        # Crear instancia del agente desde la configuración
        agent = await AutonomousAgent.from_config(AGENT_CONFIG)
        
        # Verificar que el agente se actualizó correctamente
        assert agent.agent_id == AGENT_CONFIG["agent"]["agentId"]
        assert agent.agent.status == "active"  # Verificar que se mantiene el estado existente
        
        # Verificar que se llamó al método configure_agent del DatabaseClient
        mock_db_client.configure_agent.assert_called_once_with(AGENT_CONFIG)

@pytest.mark.asyncio
async def test_agent_configuration_validation(mock_db_client):
    """Test para verificar la validación de la configuración del agente"""
    
    # Configuración inválida (sin agentId)
    invalid_config = AGENT_CONFIG.copy()
    del invalid_config["agent"]["agentId"]
    
    mock_db_client.configure_agent = AsyncMock(side_effect=ValueError("Invalid configuration"))
    
    # Patch del DatabaseClient
    with patch('src.core.autonomous_agent.DatabaseClient', return_value=mock_db_client):
        # Verificar que se lanza una excepción con configuración inválida
        with pytest.raises(ValueError):
            await AutonomousAgent.from_config(invalid_config) 