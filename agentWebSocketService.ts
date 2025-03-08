import { AgentConfiguration } from '../components/AgentConfigForm';

export type WebSocketMessageType = 
  | 'create_contract'
  | 'create_contract_response'
  | 'create_agent'
  | 'create_agent_response'
  | 'create_function'
  | 'create_function_response'
  | 'create_schedule'
  | 'create_schedule_response'
  | 'create_notification'
  | 'create_notification_response'
  | 'configure_agent'
  | 'configure_agent_response'
  | 'agent_configured'
  | 'start_agent'
  | 'agent_started'
  | 'stop_agent'
  | 'agent_stopped'
  | 'execute'
  | 'execute_response'
  | 'error'
  | 'log'
  | 'status';

interface WebSocketMessage {
  type: WebSocketMessageType;
  data: any;
}

interface AgentConnection {
  socket: WebSocket;
  handlers: Map<string, ((message: any) => void)[]>;
}

export class AgentWebSocketService {
  private static instance: AgentWebSocketService;
  private connections: Map<string, AgentConnection> = new Map();

  private constructor() {}

  public static getInstance(): AgentWebSocketService {
    if (!AgentWebSocketService.instance) {
      AgentWebSocketService.instance = new AgentWebSocketService();
    }
    return AgentWebSocketService.instance;
  }

  public connect(agentId: string): Promise<void> {
    return new Promise((resolve, reject) => {
      // Si ya existe una conexión para este agente, la cerramos
      if (this.connections.has(agentId)) {
        this.disconnect(agentId);
      }

      // Obtener la URL base del WebSocket del entorno
      const wsUrl = import.meta.env.MODE === 'production'
        ? import.meta.env.VITE_WS_URL_PROD
        : import.meta.env.VITE_WS_AGENT_URL_DEV || 'ws://localhost:8765';

      // Construir la URL completa según la documentación
      const fullWsUrl = `${wsUrl}/ws/agent/${agentId}`;
      console.log('Connecting to WebSocket:', fullWsUrl);

      try {
        const socket = new WebSocket(fullWsUrl);
        const handlers = new Map<string, ((message: any) => void)[]>();

        socket.onopen = () => {
          console.log(`Connected to agent WebSocket service for agent ${agentId}`);
          this.emitForAgent(agentId, 'log', { message: 'Connected to agent service', type: 'info' });
          resolve();
        };

        socket.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data);
            this.handleMessage(agentId, message);
          } catch (error) {
            console.error(`Error parsing WebSocket message for agent ${agentId}:`, error);
            this.emitForAgent(agentId, 'error', { message: 'Error parsing message' });
          }
        };

        socket.onerror = (error) => {
          const errorMessage = `WebSocket connection error for agent ${agentId}: ${error instanceof Error ? error.message : 'Unknown error'}`;
          console.error(errorMessage);
          this.emitForAgent(agentId, 'error', { message: errorMessage });
          reject(new Error(errorMessage));
        };

        socket.onclose = (event) => {
          const closeMessage = `WebSocket closed for agent ${agentId}. Code: ${event.code}, Reason: ${event.reason || 'No reason provided'}`;
          console.log(closeMessage);
          this.emitForAgent(agentId, 'log', { 
            message: closeMessage,
            type: event.wasClean ? 'info' : 'warning'
          });
          // Limpiar la conexión cuando se cierra
          this.connections.delete(agentId);
        };

        // Guardar la nueva conexión
        this.connections.set(agentId, { socket, handlers });

      } catch (error) {
        const errorMessage = `Failed to create WebSocket connection: ${error instanceof Error ? error.message : 'Unknown error'}`;
        console.error(errorMessage);
        reject(new Error(errorMessage));
      }
    });
  }

  public disconnect(agentId: string): void {
    const connection = this.connections.get(agentId);
    if (connection) {
      connection.socket.close();
      this.connections.delete(agentId);
    }
  }

  public disconnectAll(): void {
    for (const agentId of this.connections.keys()) {
      this.disconnect(agentId);
    }
  }

  public async configureAgent(agentId: string, config: AgentConfiguration): Promise<void> {
    const connection = this.connections.get(agentId);
    if (!connection || connection.socket.readyState !== WebSocket.OPEN) {
      throw new Error(`WebSocket is not connected for agent ${agentId}`);
    }

    try {
      // 1. Create contract
      await this.sendMessageToAgent(agentId, {
        type: 'create_contract',
        data: config.contract
      });

      // 2. Create agent base
      await this.sendMessageToAgent(agentId, {
        type: 'create_agent',
        data: {
          contractId: config.agent.contractId,
          name: config.agent.name,
          description: config.agent.description,
          status: config.agent.status,
          gas_limit: config.agent.gas_limit,
          max_priority_fee: config.agent.max_priority_fee,
          owner: config.agent.owner,
          contract_state: config.agent.contract_state
        }
      });

      // 3. Add functions
      for (const func of config.functions) {
        await this.sendMessageToAgent(agentId, {
          type: 'create_function',
          data: {
            function_name: func.function_name,
            function_signature: func.function_signature,
            function_type: func.function_type,
            is_enabled: func.is_enabled,
            validation_rules: func.validation_rules,
            abi: func.abi
          }
        });
      }

      // 4. Add schedule if exists
      if (config.schedule) {
        await this.sendMessageToAgent(agentId, {
          type: 'create_schedule',
          data: {
            schedule_type: config.schedule.schedule_type,
            cron_expression: config.schedule.cron_expression,
            is_active: config.schedule.is_active
          }
        });
      }

      // 5. Add notifications if any
      for (const notification of config.notifications) {
        await this.sendMessageToAgent(agentId, {
          type: 'create_notification',
          data: {
            notification_type: notification.notification_type,
            configuration: notification.configuration,
            is_enabled: notification.is_enabled
          }
        });
      }

      // 6. Finally, send configure_agent to complete setup
      await this.sendMessageToAgent(agentId, {
        type: 'configure_agent',
        data: { agent_id: agentId }
      });

    } catch (error) {
      console.error('Error configuring agent:', error);
      throw error;
    }
  }

  public startAgent(agentId: string): void {
    this.sendMessageToAgent(agentId, {
      type: 'start_agent',
      data: { agent_id: agentId }
    });
  }

  public stopAgent(agentId: string): void {
    this.sendMessageToAgent(agentId, {
      type: 'stop_agent',
      data: { agent_id: agentId }
    });
  }

  public executeAgent(agentId: string): void {
    this.sendMessageToAgent(agentId, {
      type: 'execute',
      data: { agent_id: agentId }
    });
  }

  public on(agentId: string, type: WebSocketMessageType, handler: (message: any) => void): void {
    const connection = this.connections.get(agentId);
    if (connection) {
      const handlers = connection.handlers.get(type) || [];
      handlers.push(handler);
      connection.handlers.set(type, handlers);
    }
  }

  public off(agentId: string, type: WebSocketMessageType, handler: (message: any) => void): void {
    const connection = this.connections.get(agentId);
    if (connection) {
      const handlers = connection.handlers.get(type) || [];
      const index = handlers.indexOf(handler);
      if (index !== -1) {
        handlers.splice(index, 1);
        connection.handlers.set(type, handlers);
      }
    }
  }

  private emitForAgent(agentId: string, type: WebSocketMessageType, data: any): void {
    const connection = this.connections.get(agentId);
    if (connection) {
      const handlers = connection.handlers.get(type) || [];
      handlers.forEach(handler => handler(data));
    }
  }

  private async sendMessageToAgent(agentId: string, message: WebSocketMessage): Promise<void> {
    const connection = this.connections.get(agentId);
    if (connection && connection.socket.readyState === WebSocket.OPEN) {
      try {
        const messageString = JSON.stringify(message);
        console.log(`Sending message to agent ${agentId}:`, messageString);
        connection.socket.send(messageString);

        // Wait for acknowledgment
        return new Promise((resolve, reject) => {
          const responseType = message.type === 'create_contract' ? 'create_contract_response' :
                             message.type === 'create_agent' ? 'create_agent_response' :
                             message.type === 'create_function' ? 'create_function_response' :
                             message.type === 'create_schedule' ? 'create_schedule_response' :
                             message.type === 'create_notification' ? 'create_notification_response' :
                             message.type === 'configure_agent' ? 'configure_agent_response' :
                             `${message.type}_response` as WebSocketMessageType;

          const handler = (response: any) => {
            if (response.status === 'error') {
              reject(new Error(response.message));
            } else {
              resolve();
            }
            // Remove the handler after receiving response
            this.off(agentId, responseType, handler);
          };
          
          // Add handler for response
          this.on(agentId, responseType, handler);

          // Add timeout
          setTimeout(() => {
            this.off(agentId, responseType, handler);
            reject(new Error(`Timeout waiting for ${message.type} response`));
          }, 5000);
        });

      } catch (error) {
        const errorMessage = `Error sending message to agent ${agentId}: ${error instanceof Error ? error.message : 'Unknown error'}`;
        console.error(errorMessage);
        this.emitForAgent(agentId, 'error', { message: errorMessage });
        throw error;
      }
    } else {
      const errorMessage = `WebSocket is not connected for agent ${agentId}. State: ${connection?.socket.readyState}`;
      console.error(errorMessage);
      this.emitForAgent(agentId, 'error', { message: errorMessage });
      throw new Error(errorMessage);
    }
  }

  private handleMessage(agentId: string, message: WebSocketMessage): void {
    this.emitForAgent(agentId, message.type, message.data);

    // Manejar respuestas específicas
    switch (message.type) {
      case 'agent_configured':
        if (message.data.status === 'error') {
          this.emitForAgent(agentId, 'error', { message: message.data.message });
        }
        break;

      case 'status':
        // Actualizar estado del agente específico
        break;

      case 'error':
        console.error(`Agent error for ${agentId}:`, message.data.message);
        break;
    }
  }
} 