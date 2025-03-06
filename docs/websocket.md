# Documentación WebSocket - Zephyrus Agent

## Conexión

El servidor WebSocket está disponible en:
```
ws://localhost:8765
```

## Mensajes

La comunicación se realiza mediante mensajes JSON con el siguiente formato:

```json
{
    "type": "tipo_de_mensaje",
    "data": {
        // datos específicos del mensaje
    }
}
```

## Comandos Disponibles

### 1. Agregar Agente

**Enviar:**
```json
{
    "type": "add_agent",
    "data": {
        "agent_id": "id_del_agente"
    }
}
```

**Respuesta exitosa:**
```json
{
    "type": "agent_added",
    "data": {
        "agent_id": "id_del_agente"
    }
}
```

### 2. Iniciar Agente

**Enviar:**
```json
{
    "type": "start_agent",
    "data": {
        "agent_id": "id_del_agente"
    }
}
```

**Respuesta exitosa:**
```json
{
    "type": "agent_started",
    "data": {
        "agent_id": "id_del_agente"
    }
}
```

### 3. Detener Agente

**Enviar:**
```json
{
    "type": "stop_agent",
    "data": {
        "agent_id": "id_del_agente"
    }
}
```

**Respuesta exitosa:**
```json
{
    "type": "agent_stopped",
    "data": {
        "agent_id": "id_del_agente"
    }
}
```

### 4. Eliminar Agente

**Enviar:**
```json
{
    "type": "remove_agent",
    "data": {
        "agent_id": "id_del_agente"
    }
}
```

**Respuesta exitosa:**
```json
{
    "type": "agent_removed",
    "data": {
        "agent_id": "id_del_agente"
    }
}
```

## Mensajes de Error

En caso de error, el servidor responderá con un mensaje de error:

```json
{
    "type": "error",
    "data": {
        "message": "Descripción del error"
    }
}
```

## Ejemplos de Errores Comunes

1. Agente no encontrado:
```json
{
    "type": "error",
    "data": {
        "message": "Agent <id_del_agente> not found"
    }
}
```

2. Agente ya existe:
```json
{
    "type": "error",
    "data": {
        "message": "Agent <id_del_agente> already exists"
    }
}
```

3. Agente ya está en ejecución:
```json
{
    "type": "error",
    "data": {
        "message": "Agent <id_del_agente> is already running"
    }
}
```

## Notas Adicionales

1. Todos los mensajes deben ser en formato JSON válido.
2. El campo `type` es obligatorio en todos los mensajes.
3. El campo `data` puede variar según el tipo de mensaje.
4. Los mensajes de respuesta siempre incluirán el ID del agente afectado.
5. El servidor mantendrá la conexión abierta hasta que el cliente la cierre o ocurra un error.

## Ejemplo de Uso con JavaScript

```javascript
// Conectar al WebSocket
const ws = new WebSocket('ws://localhost:8765');

// Manejar conexión establecida
ws.onopen = () => {
    console.log('Conectado al servidor WebSocket');
    
    // Ejemplo: Agregar un agente
    ws.send(JSON.stringify({
        type: 'add_agent',
        data: {
            agent_id: 'mi-agente-001'
        }
    }));
};

// Manejar mensajes recibidos
ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    console.log('Mensaje recibido:', message);
};

// Manejar errores
ws.onerror = (error) => {
    console.error('Error en WebSocket:', error);
};

// Manejar desconexión
ws.onclose = () => {
    console.log('Desconectado del servidor WebSocket');
};
```

## Ejemplo de Uso con Python

```python
import asyncio
import websockets
import json

async def connect_to_agent():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        # Ejemplo: Agregar un agente
        await websocket.send(json.dumps({
            "type": "add_agent",
            "data": {
                "agent_id": "mi-agente-001"
            }
        }))
        
        # Recibir respuesta
        response = await websocket.recv()
        print(f"Respuesta recibida: {response}")

# Ejecutar el cliente
asyncio.get_event_loop().run_until_complete(connect_to_agent())
``` 