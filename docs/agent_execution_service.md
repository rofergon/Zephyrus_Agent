# Servicio de Ejecución de Agentes vía WebSocket

Este servicio permite ejecutar agentes de forma remota a través de WebSocket. Un cliente (como por ejemplo una aplicación frontend) puede enviar mensajes al servidor para solicitar la ejecución de un agente específico, y recibir actualizaciones en tiempo real sobre el progreso y resultados de la ejecución.

## Índice

- [Requisitos](#requisitos)
- [Iniciar el Servidor](#iniciar-el-servidor)
- [Protocolo de Comunicación](#protocolo-de-comunicación)
- [Ejemplos de Uso](#ejemplos-de-uso)
- [Integración con Frontend](#integración-con-frontend)
- [Manejo de Errores](#manejo-de-errores)

## Requisitos

- Python 3.7 o superior
- WebSockets (`pip install websockets`)
- Demás dependencias del proyecto Zephyrus Agent

## Iniciar el Servidor

### Windows

```bash
# Desde la raíz del proyecto
start_execution_server.bat
```

### Linux/Mac

```bash
# Desde la raíz del proyecto
python src/main_execution_server.py
```

Por defecto, el servidor escucha en `localhost:8765`. Estos valores se pueden configurar mediante variables de entorno:

- `WS_HOST`: Host donde escucha el servidor (por defecto: `localhost`)
- `WS_PORT`: Puerto donde escucha el servidor (por defecto: `8765`)

## Protocolo de Comunicación

### Solicitud de Ejecución de Agente

Para solicitar la ejecución de un agente, envía un mensaje JSON con uno de los siguientes formatos:

**Formato 1 (recomendado):**
```json
{
  "type": "websocket_execution",
  "agent_id": "ID_DEL_AGENTE"
}
```

**Formato 2 (compatible con el servidor existente):**
```json
{
  "type": "execute",
  "agent_id": "ID_DEL_AGENTE"
}
```

**Formato 3 (también compatible):**
```json
{
  "type": "execute",
  "data": {
    "agent_id": "ID_DEL_AGENTE"
  }
}
```

### Respuestas del Servidor

El servidor puede enviar diferentes tipos de respuestas:

1. **Inicio de Ejecución**:

```json
{
  "type": "execution_response",
  "data": {
    "success": true,
    "message": "Iniciando ejecución del agente ID_DEL_AGENTE",
    "status": "started"
  }
}
```

2. **Ejecución Completada (con éxito)**:

```json
{
  "type": "execution_response",
  "data": {
    "success": true,
    "results": [...],  // Detalles de las acciones ejecutadas
    "agent_id": "ID_DEL_AGENTE",
    "execution_count": 2,  // Número de acciones ejecutadas
    "status": "completed"
  }
}
```

3. **Ejecución Completada (sin acciones)**:

```json
{
  "type": "execution_response",
  "data": {
    "success": true,
    "results": [],
    "agent_id": "ID_DEL_AGENTE",
    "execution_count": 0,
    "message": "No se ejecutó ninguna acción durante el ciclo",
    "status": "completed"
  }
}
```

4. **Error de Ejecución**:

```json
{
  "type": "execution_response",
  "data": {
    "success": false,
    "error": "Mensaje de error",
    "agent_id": "ID_DEL_AGENTE",
    "status": "completed"
  }
}
```

5. **Error de Formato o Procesamiento**:

```json
{
  "type": "error",
  "data": {
    "message": "Descripción del error"
  }
}
```

## Ejemplos de Uso

### Cliente Python

Este repositorio incluye un cliente de ejemplo en `examples/websocket_execution_client.py` que puedes usar como referencia:

```bash
# Ejecutar con un agent_id específico
python examples/websocket_execution_client.py 8191feef-546d-46a8-a26f-b92073882f5c

# Si no se proporciona agent_id, usa un valor por defecto
python examples/websocket_execution_client.py
```

### Cliente JavaScript (para frontend)

```javascript
// Conectar al servidor WebSocket
const ws = new WebSocket('ws://localhost:8765');

// Manejar eventos de conexión
ws.onopen = () => {
  console.log('Conectado al servidor');
  
  // Solicitar ejecución de un agente
  const message = {
    type: 'execute',
    agent_id: '8191feef-546d-46a8-a26f-b92073882f5c'
  };
  
  ws.send(JSON.stringify(message));
};

// Recibir mensajes del servidor
ws.onmessage = (event) => {
  const response = JSON.parse(event.data);
  console.log('Respuesta recibida:', response);
  
  // Manejar diferentes estados de la respuesta
  if (response.type === 'execution_response') {
    const data = response.data || {};
    
    if (data.status === 'started') {
      // La ejecución ha comenzado
      console.log('Ejecución iniciada, esperando resultados...');
    } 
    else if (data.status === 'completed') {
      // La ejecución ha finalizado
      if (data.success) {
        console.log(`Ejecución completada: ${data.execution_count} acciones ejecutadas`);
        // Procesar resultados
        if (data.results && data.results.length > 0) {
          data.results.forEach((result, i) => {
            console.log(`Resultado ${i+1}:`, result);
          });
        }
      } else {
        console.error('Error en la ejecución:', data.error);
      }
    }
  } else if (response.type === 'error') {
    console.error('Error:', response.data?.message || 'Error desconocido');
  }
};

// Manejar errores y cierre de conexión
ws.onerror = (error) => {
  console.error('Error de WebSocket:', error);
};

ws.onclose = (event) => {
  console.log('Conexión cerrada:', event.code, event.reason);
};
```

## Integración con Frontend

Para integrar este servicio con una aplicación frontend:

1. **Establece la conexión WebSocket** cuando el usuario navegue a la página de agentes.
2. **Ofrece un botón "Ejecutar"** para cada agente que dispare la solicitud WebSocket.
3. **Muestra un indicador de progreso** mientras el estado es `started`.
4. **Actualiza la interfaz** cuando se reciba una respuesta con estado `completed`.
5. **Maneja apropiadamente los errores** mostrando mensajes claros al usuario.

Ejemplo de componente React:

```jsx
import React, { useState, useEffect, useRef } from 'react';

function AgentExecutor({ agentId }) {
  const [status, setStatus] = useState('idle'); // idle, connecting, running, completed, error
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);
  
  const executeAgent = () => {
    setStatus('connecting');
    setError(null);
    
    // Crear nueva conexión WebSocket
    const ws = new WebSocket('ws://localhost:8765');
    wsRef.current = ws;
    
    ws.onopen = () => {
      setStatus('running');
      
      // Enviar solicitud de ejecución
      ws.send(JSON.stringify({
        type: 'execute',
        agent_id: agentId
      }));
    };
    
    ws.onmessage = (event) => {
      const response = JSON.parse(event.data);
      
      if (response.type === 'execution_response') {
        const data = response.data || {};
        
        if (data.status === 'completed') {
          if (data.success) {
            setResults(data.results || []);
            setStatus('completed');
          } else {
            setError(data.error);
            setStatus('error');
          }
          
          // Cerrar la conexión 
          ws.close();
        }
      } else if (response.type === 'error') {
        setError(response.data?.message || 'Error desconocido');
        setStatus('error');
      }
    };
    
    ws.onerror = () => {
      setError('Error de conexión con el servidor');
      setStatus('error');
    };
    
    ws.onclose = () => {
      if (status === 'running') {
        setError('La conexión se cerró inesperadamente');
        setStatus('error');
      }
    };
  };
  
  // Limpiar la conexión al desmontar el componente
  useEffect(() => {
    return () => {
      if (wsRef.current && wsRef.current.readyState < 2) {
        wsRef.current.close();
      }
    };
  }, []);
  
  return (
    <div>
      <h2>Ejecución del Agente</h2>
      
      <button 
        onClick={executeAgent} 
        disabled={status === 'connecting' || status === 'running'}
      >
        Ejecutar Agente
      </button>
      
      {status === 'connecting' && <p>Conectando al servidor...</p>}
      {status === 'running' && <p>Ejecutando agente...</p>}
      {status === 'error' && <p className="error">Error: {error}</p>}
      
      {status === 'completed' && (
        <div>
          <h3>Resultados ({results.length} acciones)</h3>
          {results.length === 0 ? (
            <p>No se ejecutó ninguna acción</p>
          ) : (
            <ul>
              {results.map((result, index) => (
                <li key={index}>
                  <strong>Función:</strong> {result.function_name}
                  <br />
                  <strong>Resultado:</strong> {JSON.stringify(result.result)}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
```

## Manejo de Errores

El servicio maneja diferentes tipos de errores:

- **Errores de conexión**: El cliente no puede conectarse al servidor
- **Errores de formato**: Mensajes JSON no válidos o campos faltantes
- **Errores de ejecución**: Problemas al ejecutar el agente (agente no encontrado, contrato no encontrado, etc.)

Para una buena experiencia de usuario, asegúrate de manejar estos errores adecuadamente en tu cliente, mostrando mensajes claros y significativos. 