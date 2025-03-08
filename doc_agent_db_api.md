# Agent Database API Documentation

## Table of Contents
- [Overview](#overview)
- [Agents](#agents)
- [Agent Functions](#agent-functions)
- [Agent Schedules](#agent-schedules)
- [Agent Notifications](#agent-notifications)
- [Agent Execution Logs](#agent-execution-logs)
- [Error Handling](#error-handling)

## Overview

This documentation describes the database API for managing smart contract agents. The API provides functionality for:
- Creating and managing agents
- Configuring agent functions
- Setting up execution schedules
- Managing notifications
- Tracking execution logs

## Agents

### Create Agent
Creates a new agent for a smart contract.

**Method**: `createAgent(agentData)`

**Parameters**:
```typescript
{
  contractId: string;      // Required: ID of the contract
  name: string;           // Required: Name of the agent
  owner: string;          // Required: Owner's address
  description?: string;   // Optional: Agent description
  status?: string;       // Optional: 'active' | 'paused' | 'stopped'
  gasLimit?: string;     // Optional: Gas limit for transactions
  maxPriorityFee?: string; // Optional: Max priority fee for transactions
  contractState?: object; // Optional: Current contract state
}
```

**Returns**:
```typescript
{
  agentId: string;  // UUID of the created agent
}
```

### Get Agents by Contract
Retrieves all agents associated with a contract.

**Method**: `getAgentsByContract(contractId)`

**Parameters**:
- `contractId`: string - ID of the contract

**Returns**:
```typescript
Array<{
  agent_id: string;
  contract_id: string;
  name: string;
  description: string | null;
  status: 'active' | 'paused' | 'stopped';
  gas_limit: string | null;
  max_priority_fee: string | null;
  owner: string;
  contract_state: object | null;
  created_at: string;
  updated_at: string;
}>
```

### Update Agent
Updates an existing agent's properties.

**Method**: `updateAgent(agentId, updateData)`

**Parameters**:
```typescript
agentId: string;
updateData: {
  name?: string;
  description?: string;
  status?: 'active' | 'paused' | 'stopped';
  gasLimit?: string;
  maxPriorityFee?: string;
  contractState?: object;
}
```

**Returns**: Updated agent object

## Agent Functions

### Create Function
Creates a new function configuration for an agent.

**Method**: `createAgentFunction(agentId, functionData)`

**Parameters**:
```typescript
agentId: string;
functionData: {
  functionName: string;      // Required: Name of the function
  functionSignature: string; // Required: Function signature
  functionType: string;      // Required: 'read' | 'write' | 'payable'
  isEnabled?: boolean;       // Optional: Enable/disable function
  validationRules?: object;  // Optional: Input validation rules
  abi: object;              // Required: Function ABI
  parameters?: Array<{       // Optional: Function parameters
    paramName: string;
    paramType: string;
    defaultValue?: any;
    validationRules?: object;
  }>;
}
```

**Returns**:
```typescript
{
  functionId: string;  // UUID of the created function
}
```

### Get Functions
Retrieves all functions configured for an agent.

**Method**: `getAgentFunctions(agentId)`

**Parameters**:
- `agentId`: string - ID of the agent

**Returns**:
```typescript
Array<{
  function_id: string;
  agent_id: string;
  function_name: string;
  function_signature: string;
  function_type: string;
  is_enabled: boolean;
  validation_rules: object | null;
  abi: object;
  parameters: Array<{
    param_id: string;
    param_name: string;
    param_type: string;
    default_value: any;
    validation_rules: object | null;
  }>;
}>
```

### Update Function
Updates an existing function configuration.

**Method**: `updateAgentFunction(functionId, updateData)`

**Parameters**:
```typescript
functionId: string;
updateData: {
  functionName?: string;
  functionSignature?: string;
  isEnabled?: boolean;
  validationRules?: object;
  abi?: object;
  parameters?: Array<{
    paramName: string;
    paramType: string;
    defaultValue?: any;
    validationRules?: object;
  }>;
}
```

## Agent Schedules

### Create Schedule
Creates a new execution schedule for an agent.

**Method**: `createAgentSchedule(agentId, scheduleData)`

**Parameters**:
```typescript
agentId: string;
scheduleData: {
  scheduleType: 'interval' | 'cron';  // Required: Schedule type
  intervalSeconds?: number;           // Required for interval type
  cronExpression?: string;           // Required for cron type
  nextExecution?: Date;              // Optional: Next execution time
  isActive?: boolean;                // Optional: Schedule status
}
```

**Returns**:
```typescript
{
  scheduleId: string;  // UUID of the created schedule
}
```

### Get Schedules
Retrieves all schedules for an agent.

**Method**: `getAgentSchedules(agentId)`

**Parameters**:
- `agentId`: string - ID of the agent

**Returns**:
```typescript
Array<{
  schedule_id: string;
  agent_id: string;
  schedule_type: string;
  interval_seconds: number | null;
  cron_expression: string | null;
  next_execution: string | null;
  last_execution: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}>
```

### Update Schedule
Updates an existing schedule configuration.

**Method**: `updateAgentSchedule(scheduleId, updateData)`

**Parameters**:
```typescript
scheduleId: string;
updateData: {
  scheduleType?: 'interval' | 'cron';
  intervalSeconds?: number;
  cronExpression?: string;
  nextExecution?: Date;
  isActive?: boolean;
}
```

## Agent Notifications

### Create Notification
Creates a new notification configuration for an agent.

**Method**: `createAgentNotification(agentId, notificationData)`

**Parameters**:
```typescript
agentId: string;
notificationData: {
  notificationType: 'email' | 'discord' | 'telegram';  // Required
  configuration: object;                               // Required
  isEnabled?: boolean;                                // Optional
}
```

**Returns**:
```typescript
{
  notificationId: string;  // UUID of the created notification
}
```

### Get Notifications
Retrieves all notifications for an agent.

**Method**: `getAgentNotifications(agentId)`

**Parameters**:
- `agentId`: string - ID of the agent

**Returns**:
```typescript
Array<{
  notification_id: string;
  agent_id: string;
  notification_type: string;
  configuration: object;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}>
```

### Update Notification
Updates an existing notification configuration.

**Method**: `updateAgentNotification(notificationId, updateData)`

**Parameters**:
```typescript
notificationId: string;
updateData: {
  notificationType?: 'email' | 'discord' | 'telegram';
  configuration?: object;
  isEnabled?: boolean;
}
```

## Agent Execution Logs

### Create Execution Log
Creates a new execution log entry.

**Method**: `createAgentExecutionLog(agentId, logData)`

**Parameters**:
```typescript
agentId: string;
logData: {
  functionId: string;                           // Required
  transactionHash?: string;                     // Optional
  status: 'pending' | 'success' | 'failed';     // Required
  errorMessage?: string;                        // Optional
  gasUsed?: string;                            // Optional
  gasPrice?: string;                           // Optional
  executionTime?: Date;                        // Optional
}
```

**Returns**:
```typescript
{
  logId: string;  // UUID of the created log
}
```

### Get Execution Logs
Retrieves all execution logs for an agent.

**Method**: `getAgentExecutionLogs(agentId)`

**Parameters**:
- `agentId`: string - ID of the agent

**Returns**:
```typescript
Array<{
  log_id: string;
  agent_id: string;
  function_id: string;
  transaction_hash: string | null;
  status: string;
  error_message: string | null;
  gas_used: string | null;
  gas_price: string | null;
  execution_time: string;
  created_at: string;
}>
```

## Error Handling

All methods follow a consistent error handling pattern:

1. Input validation errors:
   - Invalid or missing required fields
   - Invalid enum values (status, types, etc.)
   - Invalid data formats

2. Database errors:
   - Connection errors
   - Query execution errors
   - Constraint violations

3. Error Response Format:
```typescript
{
  error: string;  // Error message describing what went wrong
}
```

Common HTTP Status Codes:
- 400: Bad Request (Invalid input)
- 404: Not Found (Resource doesn't exist)
- 500: Internal Server Error

## Best Practices

1. Always validate input data before making API calls
2. Handle errors appropriately in your application
3. Use appropriate status codes in your responses
4. Implement proper authentication and authorization
5. Follow rate limiting guidelines
6. Keep logs for debugging purposes

## Data Types

- All IDs are UUID v4 strings
- Timestamps are in ISO 8601 format
- JSON objects should be properly serialized
- Boolean values should be true/false
- Numeric values should be passed as strings when dealing with blockchain values 