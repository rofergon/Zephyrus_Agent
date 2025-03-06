from dataclasses import dataclass
from typing import Dict, Optional
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
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dict(cls, data: Dict) -> 'Agent':
        """
        Crea una instancia de Agent desde un diccionario
        """
        return cls(
            agent_id=data['agentId'],
            contract_id=data['contractId'],
            name=data['name'],
            description=data['description'],
            status=data['status'],
            gas_limit=data['gasLimit'],
            max_priority_fee=data['maxPriorityFee'],
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at'])
        )

    def to_dict(self) -> Dict:
        """
        Convierte la instancia a un diccionario
        """
        return {
            'agentId': self.agent_id,
            'contractId': self.contract_id,
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'gasLimit': self.gas_limit,
            'maxPriorityFee': self.max_priority_fee,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        } 