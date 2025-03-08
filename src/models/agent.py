from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime

@dataclass
class Agent:
    agent_id: str
    contract_id: str
    name: str
    description: str
    status: str
    gas_limit: str
    max_priority_fee: str
    created_at: Any  # Cambiado de datetime a Any para soportar string o datetime
    updated_at: Any  # Cambiado de datetime a Any para soportar string o datetime
    owner: str
    contract_state: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict) -> 'Agent':
        """
        Crea una instancia de Agent desde un diccionario
        """
        # Verificar el tipo de data
        if isinstance(data, list):
            if not data:
                raise ValueError("Empty data list provided for Agent.from_dict")
            data = data[0]
        
        # Verificar que tenemos un diccionario
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict or list for Agent.from_dict, got {type(data)}")
        
        # Manejar created_at y updated_at que pueden venir como string
        created_at = data.get('created_at', data.get('createdAt', ''))
        updated_at = data.get('updated_at', data.get('updatedAt', ''))
        
        # Si son strings y queremos convertirlos a datetime, podemos hacerlo así:
        # if isinstance(created_at, str) and created_at:
        #     created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        # if isinstance(updated_at, str) and updated_at:
        #     updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
        
        # Pero para mayor compatibilidad, los mantenemos como strings
        
        return cls(
            agent_id=data.get('agentId', data.get('agent_id', '')),
            contract_id=data.get('contractId', data.get('contract_id', '')),
            name=data.get('name', ''),
            description=data.get('description', ''),
            status=data.get('status', ''),
            gas_limit=data.get('gasLimit', data.get('gas_limit', '')),
            max_priority_fee=data.get('maxPriorityFee', data.get('max_priority_fee', '')),
            created_at=created_at,
            updated_at=updated_at,
            owner=data.get('owner', ''),
            contract_state=data.get('contractState', data.get('contract_state', {}))
        )

    def to_dict(self) -> Dict:
        """
        Convierte la instancia a un diccionario
        """
        # Manejar created_at y updated_at que pueden ser string o datetime
        if isinstance(self.created_at, datetime):
            created_at_str = self.created_at.isoformat().replace('+00:00', 'Z')
        else:
            created_at_str = self.created_at
            
        if isinstance(self.updated_at, datetime):
            updated_at_str = self.updated_at.isoformat().replace('+00:00', 'Z')
        else:
            updated_at_str = self.updated_at
            
        return {
            'agentId': self.agent_id,
            'contractId': self.contract_id,
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'gasLimit': self.gas_limit,
            'maxPriorityFee': self.max_priority_fee,
            'created_at': created_at_str,
            'updated_at': updated_at_str,
            'owner': self.owner,
            'contractState': self.contract_state
        }

@dataclass
class AgentFunction:
    function_id: str
    agent_id: str
    function_name: str
    function_signature: str
    function_type: str  # 'read', 'write', or 'payable'
    is_enabled: bool
    validation_rules: Dict[str, Any]
    abi: Dict[str, Any]
    created_at: Any  # Cambiado de datetime a Any para soportar string o datetime
    updated_at: Any  # Cambiado de datetime a Any para soportar string o datetime

    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentFunction':
        """
        Crea una instancia de AgentFunction desde un diccionario
        """
        # Manejar created_at y updated_at que pueden venir como string
        created_at = data.get('created_at', data.get('createdAt', ''))
        updated_at = data.get('updated_at', data.get('updatedAt', ''))
        
        return cls(
            function_id=data.get('functionId', data.get('function_id', '')),
            agent_id=data.get('agentId', data.get('agent_id', '')),
            function_name=data.get('functionName', data.get('function_name', '')),
            function_signature=data.get('functionSignature', data.get('function_signature', '')),
            function_type=data.get('functionType', data.get('function_type', '')),
            is_enabled=data.get('isEnabled', data.get('is_enabled', True)),
            validation_rules=data.get('validationRules', data.get('validation_rules', {})),
            abi=data.get('abi', {}),
            created_at=created_at,
            updated_at=updated_at
        )

    def to_dict(self) -> Dict:
        """
        Convierte la instancia a un diccionario
        """
        # Manejar created_at y updated_at que pueden ser string o datetime
        if isinstance(self.created_at, datetime):
            created_at_str = self.created_at.isoformat().replace('+00:00', 'Z')
        else:
            created_at_str = self.created_at
            
        if isinstance(self.updated_at, datetime):
            updated_at_str = self.updated_at.isoformat().replace('+00:00', 'Z')
        else:
            updated_at_str = self.updated_at
            
        return {
            'functionId': self.function_id,
            'agentId': self.agent_id,
            'functionName': self.function_name,
            'functionSignature': self.function_signature,
            'functionType': self.function_type,
            'isEnabled': self.is_enabled,
            'validationRules': self.validation_rules,
            'abi': self.abi,
            'created_at': created_at_str,
            'updated_at': updated_at_str
        }

@dataclass
class AgentFunctionParam:
    param_id: str
    function_id: str
    param_name: str
    param_type: str
    default_value: Optional[str]
    validation_rules: Optional[Dict[str, Any]]
    created_at: Any  # Cambiado de datetime a Any para soportar string o datetime
    updated_at: Any  # Cambiado de datetime a Any para soportar string o datetime

    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentFunctionParam':
        """
        Crea una instancia de AgentFunctionParam desde un diccionario
        """
        # Manejar created_at y updated_at que pueden venir como string
        created_at = data.get('created_at', data.get('createdAt', ''))
        updated_at = data.get('updated_at', data.get('updatedAt', ''))
        
        return cls(
            param_id=data.get('paramId', data.get('param_id', '')),
            function_id=data.get('functionId', data.get('function_id', '')),
            param_name=data.get('paramName', data.get('param_name', '')),
            param_type=data.get('paramType', data.get('param_type', '')),
            default_value=data.get('defaultValue', data.get('default_value')),
            validation_rules=data.get('validationRules', data.get('validation_rules')),
            created_at=created_at,
            updated_at=updated_at
        )

    def to_dict(self) -> Dict:
        """
        Convierte la instancia a un diccionario
        """
        # Manejar created_at y updated_at que pueden ser string o datetime
        if isinstance(self.created_at, datetime):
            created_at_str = self.created_at.isoformat().replace('+00:00', 'Z')
        else:
            created_at_str = self.created_at
            
        if isinstance(self.updated_at, datetime):
            updated_at_str = self.updated_at.isoformat().replace('+00:00', 'Z')
        else:
            updated_at_str = self.updated_at
            
        return {
            'paramId': self.param_id,
            'functionId': self.function_id,
            'paramName': self.param_name,
            'paramType': self.param_type,
            'defaultValue': self.default_value,
            'validationRules': self.validation_rules,
            'created_at': created_at_str,
            'updated_at': updated_at_str
        }

@dataclass
class AgentSchedule:
    schedule_id: str
    agent_id: str
    schedule_type: str
    cron_expression: str
    is_active: bool
    next_execution: Optional[Any]  # Cambiado de datetime a Any para soportar string o datetime
    created_at: Any  # Cambiado de datetime a Any para soportar string o datetime
    updated_at: Any  # Cambiado de datetime a Any para soportar string o datetime

    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentSchedule':
        """
        Crea una instancia de AgentSchedule desde un diccionario
        """
        # Manejar created_at, updated_at y next_execution que pueden venir como string
        created_at = data.get('created_at', data.get('createdAt', ''))
        updated_at = data.get('updated_at', data.get('updatedAt', ''))
        next_execution = data.get('nextExecution', data.get('next_execution'))
        
        return cls(
            schedule_id=data.get('scheduleId', data.get('schedule_id', '')),
            agent_id=data.get('agentId', data.get('agent_id', '')),
            schedule_type=data.get('scheduleType', data.get('schedule_type', '')),
            cron_expression=data.get('cronExpression', data.get('cron_expression', '')),
            is_active=data.get('isActive', data.get('is_active', True)),
            next_execution=next_execution,
            created_at=created_at,
            updated_at=updated_at
        )

    def to_dict(self) -> Dict:
        """
        Convierte la instancia a un diccionario
        """
        # Manejar created_at, updated_at y next_execution que pueden ser string o datetime
        if isinstance(self.created_at, datetime):
            created_at_str = self.created_at.isoformat().replace('+00:00', 'Z')
        else:
            created_at_str = self.created_at
            
        if isinstance(self.updated_at, datetime):
            updated_at_str = self.updated_at.isoformat().replace('+00:00', 'Z')
        else:
            updated_at_str = self.updated_at
            
        next_execution_str = None
        if self.next_execution:
            if isinstance(self.next_execution, datetime):
                next_execution_str = self.next_execution.isoformat().replace('+00:00', 'Z')
            else:
                next_execution_str = self.next_execution
            
        return {
            'scheduleId': self.schedule_id,
            'agentId': self.agent_id,
            'scheduleType': self.schedule_type,
            'cronExpression': self.cron_expression,
            'isActive': self.is_active,
            'nextExecution': next_execution_str,
            'created_at': created_at_str,
            'updated_at': updated_at_str
        } 