/**
 * Ejemplo de cómo procesar y mostrar los logs del agente en el frontend
 * Este es solo un ejemplo, y debe adaptarse al framework y estructura específica de tu frontend
 */

// Función para conectar al WebSocket y ejecutar un agente
function executeAgent(agentId) {
  // Estado para almacenar los logs y resultados
  let logs = [];
  let executionResults = [];
  let executionStatus = 'connecting'; // connecting, running, completed, error
  
  // Elementos de la UI (reemplazar con la lógica específica de tu frontend)
  const statusEl = document.getElementById('status');
  const logsEl = document.getElementById('logs');
  const resultsEl = document.getElementById('results');
  
  // Actualizar la UI
  function updateUI() {
    // Actualizar el estado
    statusEl.textContent = executionStatus;
    statusEl.className = executionStatus;
    
    // Limpiar los logs anteriores
    logsEl.innerHTML = '';
    
    // Mostrar los logs del agente
    logs.forEach(log => {
      const logItem = document.createElement('div');
      logItem.className = 'log-item agent-comment';
      
      // Formatear la fecha
      const timestamp = new Date(log.timestamp);
      const timeStr = timestamp.toLocaleTimeString();
      
      logItem.innerHTML = `
        <span class="timestamp">${timeStr}</span>
        <span class="agent-icon">🤖</span>
        <span class="message">${log.message}</span>
      `;
      
      logsEl.appendChild(logItem);
    });
    
    // Actualizar resultados si disponibles
    if (executionResults && executionResults.length > 0) {
      resultsEl.innerHTML = `
        <div class="results-header">
          ${executionResults.length} Acciones Ejecutadas
        </div>
      `;
      
      executionResults.forEach((result, index) => {
        const resultItem = document.createElement('div');
        resultItem.className = 'result-item';
        
        const statusClass = result.success ? 'result-success' : 'result-error';
        const statusIcon = result.success ? '✓' : '✗';
        
        resultItem.innerHTML = `
          <div class="result-function">${index + 1}. ${result.function}</div>
          <div class="result-params">Parámetros: ${JSON.stringify(result.params)}</div>
          <div class="result-output ${statusClass}">
            ${statusIcon} ${result.result}
          </div>
        `;
        
        resultsEl.appendChild(resultItem);
      });
    } else {
      resultsEl.innerHTML = '<div class="results-header">No hay resultados disponibles</div>';
    }
    
    // Hacer scroll hacia abajo para ver los logs más recientes
    logsEl.scrollTop = logsEl.scrollHeight;
  }
  
  // Conectar al WebSocket
  const ws = new WebSocket('ws://localhost:8765');
  
  ws.onopen = () => {
    executionStatus = 'running';
    updateUI();
    
    // Enviar solicitud de ejecución
    const message = {
      type: 'execute',
      agent_id: agentId
    };
    
    ws.send(JSON.stringify(message));
    console.log('Solicitud de ejecución enviada para el agente:', agentId);
    
    // Agregar log de inicio
    logs.push({
      timestamp: new Date().toISOString(),
      level: 'info',
      message: 'Conectado al servidor. Enviando solicitud de ejecución...'
    });
    
    updateUI();
  };
  
  ws.onmessage = (event) => {
    const response = JSON.parse(event.data);
    console.log('Respuesta recibida:', response);
    
    // Procesar la respuesta según su tipo
    if (response.type === 'execute_response') {
      const data = response.data;
      
      // Actualizar el estado según la respuesta
      if (data.status === 'success') {
        executionStatus = 'completed';
        if (data.results) {
          executionResults = data.results;
        }
      } else if (data.status === 'error') {
        executionStatus = 'error';
      } else if (data.status === 'processing') {
        executionStatus = 'running';
      }
      
      // Procesar los logs si están disponibles
      if (data.logs && Array.isArray(data.logs)) {
        // Agregar los nuevos logs a la lista
        logs = [...logs, ...data.logs];
      }
      
      // Actualizar la UI
      updateUI();
      
      // Si la ejecución ha terminado, cerrar la conexión
      if (data.status === 'success' || data.status === 'error') {
        ws.close();
      }
    } else if (response.type === 'log') {
      // Procesar mensajes de log individuales
      const logData = response.data;
      
      logs.push({
        timestamp: new Date().toISOString(),
        level: logData.level || 'info',
        message: logData.message
      });
      
      updateUI();
    } else if (response.type === 'error') {
      // Procesar errores
      executionStatus = 'error';
      
      // Agregar el mensaje de error a los logs
      logs.push({
        timestamp: new Date().toISOString(),
        level: 'error',
        message: response.data.message
      });
      
      // Procesar logs adicionales si están disponibles
      if (response.data.logs && Array.isArray(response.data.logs)) {
        logs = [...logs, ...response.data.logs];
      }
      
      updateUI();
      
      // Cerrar la conexión
      ws.close();
    }
  };
  
  ws.onerror = (error) => {
    console.error('Error WebSocket:', error);
    
    executionStatus = 'error';
    
    logs.push({
      timestamp: new Date().toISOString(),
      level: 'error',
      message: 'Error de conexión WebSocket'
    });
    
    updateUI();
  };
  
  ws.onclose = () => {
    console.log('Conexión WebSocket cerrada');
    
    if (executionStatus === 'running') {
      executionStatus = 'error';
      
      logs.push({
        timestamp: new Date().toISOString(),
        level: 'error',
        message: 'La conexión se cerró inesperadamente'
      });
      
      updateUI();
    }
  };
  
  return {
    // Retornar una función para cancelar la ejecución si es necesario
    cancel: () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    }
  };
}

// Ejemplo de CSS para dar estilo a los logs
const styles = `
  .log-container {
    height: 400px;
    overflow-y: auto;
    border: 1px solid #ccc;
    padding: 10px;
    font-family: system-ui, -apple-system, sans-serif;
    margin-bottom: 20px;
    background-color: #f9f9f9;
  }
  
  .log-item {
    margin-bottom: 10px;
    padding: 10px;
    border-radius: 10px;
    line-height: 1.5;
  }
  
  .log-item.agent-comment {
    background-color: #e1f5fe;
    border-left: 4px solid #0288d1;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }
  
  .timestamp {
    color: #666;
    margin-right: 10px;
    font-size: 0.8em;
  }
  
  .agent-icon {
    font-size: 1.2em;
    margin-right: 10px;
  }
  
  .message {
    word-break: break-word;
  }
  
  #status {
    font-weight: bold;
    padding: 5px 10px;
    border-radius: 3px;
    display: inline-block;
  }
  
  #status.connecting {
    background-color: #f0f0f0;
    color: #333;
  }
  
  #status.running {
    background-color: #0077cc;
    color: white;
  }
  
  #status.completed {
    background-color: #00cc00;
    color: white;
  }
  
  #status.error {
    background-color: #cc0000;
    color: white;
  }
  
  /* Estilos para los resultados */
  .results-container {
    margin-top: 20px;
    border: 1px solid #ccc;
    border-radius: 5px;
    overflow: hidden;
    background-color: white;
  }
  
  .results-header {
    background-color: #f0f0f0;
    padding: 10px;
    font-weight: bold;
    border-bottom: 1px solid #ccc;
  }
  
  .result-item {
    padding: 10px;
    border-bottom: 1px solid #eee;
  }
  
  .result-item:last-child {
    border-bottom: none;
  }
  
  .result-function {
    font-weight: bold;
    margin-bottom: 5px;
  }
  
  .result-params {
    font-family: monospace;
    font-size: 0.9em;
    background-color: #f5f5f5;
    padding: 5px;
    border-radius: 3px;
    margin-bottom: 5px;
  }
  
  .result-success {
    color: #00cc00;
  }
  
  .result-error {
    color: #cc0000;
  }
`;

// Ejemplo de HTML para mostrar los logs
const html = `
  <div>
    <h2>Ejecución del Agente</h2>
    <div>
      <label for="agent-id">ID del Agente:</label>
      <input type="text" id="agent-id" value="8191feef-546d-46a8-a26f-b92073882f5c" />
      <button id="execute-btn">Ejecutar</button>
    </div>
    
    <div>
      <h3>Estado: <span id="status">-</span></h3>
    </div>
    
    <h3>Comentarios del Agente:</h3>
    <div id="logs" class="log-container"></div>
    
    <h3>Resultados:</h3>
    <div id="results" class="results-container"></div>
  </div>
`;

// Ejemplo de cómo se activaría la ejecución
document.addEventListener('DOMContentLoaded', () => {
  // Insertar los estilos
  const styleElement = document.createElement('style');
  styleElement.textContent = styles;
  document.head.appendChild(styleElement);
  
  // Insertar el HTML
  const container = document.createElement('div');
  container.innerHTML = html;
  document.body.appendChild(container);
  
  // Configurar el evento del botón de ejecución
  document.getElementById('execute-btn').addEventListener('click', () => {
    const agentId = document.getElementById('agent-id').value.trim();
    
    if (agentId) {
      executeAgent(agentId);
    } else {
      alert('Por favor, introduce un ID de agente válido');
    }
  });
}); 