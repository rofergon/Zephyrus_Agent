/**
 * Test script para crear un agente usando la API
 * 
 * Este script demuestra cómo utilizar la API para crear un agente completo 
 * incluyendo funciones, programación y notificaciones
 * 
 * Ejecución: node tests/create-agent.js
 */

// Usando fetch nativo de Node.js 18+
// No necesitamos importar node-fetch

// Configuración
const API_BASE_URL = 'http://localhost:3000/api/db';
const WALLET_ADDRESS = '0xaB6E247B25463F76E81aBAbBb6b0b86B40d45D38';
const CONTRACT_ID = '0x3ded337a401e234d40cf2a54d9291bf61692ca07';

// Datos del agente desde el frontend (adaptados para la API)
const agentConfig = {
  "agent": {
    "contractId": CONTRACT_ID,
    "name": "Smart Contract Agent",
    "description": "asdfwefsdfwef",
    "status": "paused",
    "gas_limit": "300000",
    "max_priority_fee": "1.5",
    "owner": WALLET_ADDRESS,
    "contract_state": {
      "paused": false,
      "symbol": "TST"
    }
  },
  "functions": [
    {
      "function_name": "approve",
      "function_signature": "approve(address,uint256)",
      "function_type": "write",
      "is_enabled": true,
      "validation_rules": {
        "spender": {},
        "value": {}
      },
      "abi": {
        "inputs": [
          {
            "internalType": "address",
            "name": "spender",
            "type": "address"
          },
          {
            "internalType": "uint256",
            "name": "value",
            "type": "uint256"
          }
        ],
        "name": "approve",
        "outputs": [
          {
            "internalType": "bool",
            "name": "",
            "type": "bool"
          }
        ],
        "stateMutability": "nonpayable",
        "type": "function"
      }
    }
  ],
  "schedule": {
    "schedule_type": "cron",
    "cron_expression": "0 0 * * *",
    "is_active": true
  },
  "notifications": []
};

// Función principal
async function createAgent() {
  try {
    console.log('Iniciando prueba de creación de agente');
    
    // 0. Crear el contrato en la tabla contracts (no en deployed_contracts)
    console.log('\nPaso preliminar: Verificando/creando contrato...');
    
    // Datos del contrato
    const contractData = {
      contract_id: CONTRACT_ID,
      address: CONTRACT_ID,
      chain_id: 11155111, // Sepolia
      name: "TestToken",
      type: "ERC20",
      abi: JSON.stringify([{
        "inputs": [
          { "internalType": "address", "name": "spender", "type": "address" },
          { "internalType": "uint256", "name": "value", "type": "uint256" }
        ],
        "name": "approve",
        "outputs": [{ "internalType": "bool", "name": "", "type": "bool" }],
        "stateMutability": "nonpayable",
        "type": "function"
      }]),
      deployed_at: new Date().toISOString(),
      owner_address: WALLET_ADDRESS
    };
    
    try {
      // Intentar crear el contrato
      console.log('Creando contrato...');
      const createContractResponse = await fetch(`${API_BASE_URL}/contracts/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(contractData)
      });
      
      console.log('Status de la respuesta (contrato):', createContractResponse.status);
      const responseText = await createContractResponse.text();
      console.log('Respuesta (contrato):', responseText);
      
      if (!createContractResponse.ok) {
        console.log('Error al crear contrato, pero continuamos por si ya existe');
      } else {
        console.log('Contrato creado con éxito');
      }
    } catch (error) {
      console.error('Error verificando/creando contrato:', error);
      // Continuamos aún si hay error
    }
    
    // 1. Crear agente base
    console.log('\nPaso 1: Creando agente base...');
    console.log('URL de la API:', `${API_BASE_URL}/agents`);
    console.log('Datos del agente:', JSON.stringify(agentConfig.agent, null, 2));

    try {
      const agentResponse = await fetch(`${API_BASE_URL}/agents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(agentConfig.agent)
      });
      
      console.log('Status de la respuesta:', agentResponse.status);
      const responseText = await agentResponse.text();
      console.log('Respuesta:', responseText);
      
      if (!agentResponse.ok) {
        throw new Error(`Error al crear agente: ${responseText}`);
      }
      
      const agentResult = JSON.parse(responseText);
      const agentId = agentResult.agent_id;
      console.log(`Agente creado con ID: ${agentId}`);
      
      // 2. Crear funciones
      console.log('\nPaso 2: Creando funciones del agente...');
      for (const functionData of agentConfig.functions) {
        const functionResponse = await fetch(`${API_BASE_URL}/agents/${agentId}/functions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(functionData)
        });
        
        if (!functionResponse.ok) {
          const errorText = await functionResponse.text();
          throw new Error(`Error al crear función: ${errorText}`);
        }
        
        const functionResult = await functionResponse.json();
        console.log(`Función creada con ID: ${functionResult.function_id}`);
      }
      
      // 3. Crear programación
      if (agentConfig.schedule) {
        console.log('\nPaso 3: Configurando programación...');
        const scheduleResponse = await fetch(`${API_BASE_URL}/agents/${agentId}/schedules`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(agentConfig.schedule)
        });
        
        if (!scheduleResponse.ok) {
          const errorText = await scheduleResponse.text();
          throw new Error(`Error al crear programación: ${errorText}`);
        }
        
        const scheduleResult = await scheduleResponse.json();
        console.log(`Programación creada con ID: ${scheduleResult.schedule_id}`);
      }
      
      // 4. Crear notificaciones
      if (agentConfig.notifications && agentConfig.notifications.length > 0) {
        console.log('\nPaso 4: Configurando notificaciones...');
        for (const notificationData of agentConfig.notifications) {
          const notificationResponse = await fetch(`${API_BASE_URL}/agents/${agentId}/notifications`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(notificationData)
          });
          
          if (!notificationResponse.ok) {
            const errorText = await notificationResponse.text();
            throw new Error(`Error al crear notificación: ${errorText}`);
          }
          
          const notificationResult = await notificationResponse.json();
          console.log(`Notificación creada con ID: ${notificationResult.notification_id}`);
        }
      } else {
        console.log('\nPaso 4: No hay notificaciones para configurar');
      }
      
      // 5. Verificar la creación completa
      console.log('\nPaso 5: Verificando la creación del agente...');
      const verifyResponse = await fetch(`${API_BASE_URL}/agents/${CONTRACT_ID}`);
      
      if (!verifyResponse.ok) {
        const errorText = await verifyResponse.text();
        throw new Error(`Error al verificar agente: ${errorText}`);
      }
      
      const agents = await verifyResponse.json();
      console.log(`Verificación completada, ${agents.length} agente(s) encontrado(s) para el contrato`);
      
      // Verificar funciones
      const functionsResponse = await fetch(`${API_BASE_URL}/agents/${agentId}/functions`);
      if (functionsResponse.ok) {
        const functions = await functionsResponse.json();
        console.log(`Verificación de funciones completada, ${functions.length} función(es) encontrada(s)`);
      }
      
      // Verificar programación
      const schedulesResponse = await fetch(`${API_BASE_URL}/agents/${agentId}/schedules`);
      if (schedulesResponse.ok) {
        const schedules = await schedulesResponse.json();
        console.log(`Verificación de programación completada, ${schedules.length} programación(es) encontrada(s)`);
      }
      
      console.log('\nPrueba de creación de agente completada con éxito');
      console.log(`Resumen: Agente ID ${agentId} creado para el contrato ${CONTRACT_ID}`);
      
      return {
        success: true,
        agentId,
        message: 'Agente creado completamente'
      };
    } catch (err) {
      console.error('Error en paso 1:', err);
      throw err;
    }
  } catch (error) {
    console.error('\nError durante la prueba:', error.message);
    return {
      success: false,
      error: error.message
    };
  }
}

// Ejecutar el test si se llama directamente
if (require.main === module) {
  createAgent()
    .then(result => {
      if (!result.success) {
        process.exit(1);
      }
    })
    .catch(err => {
      console.error('Error fatal:', err);
      process.exit(1);
    });
}

module.exports = { createAgent }; 