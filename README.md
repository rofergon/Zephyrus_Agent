# Zephyrus Autonomous Agent

An autonomous agent that interacts with smart contracts on the Sonic blockchain based on predefined behaviors and schedules.

## Features

- WebSocket-based communication with frontend
- Autonomous contract interaction using OpenAI GPT-4
- Configurable execution intervals
- Support for both read and write contract functions
- Automatic state analysis and action determination
- Robust error handling and logging

## Project Structure

```
.
├── src/
│   ├── actions/        # Action-specific implementations
│   ├── models/         # Data models and agent implementation
│   ├── utils/          # Utility functions and helpers
│   ├── websocket/      # WebSocket client implementation
│   └── main.py         # Main application entry point
├── .env.example        # Example environment variables
├── requirements.txt    # Python dependencies
└── README.md          # Project documentation
```

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd zephyrus-agent
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy `.env.example` to `.env` and fill in your configuration:
```bash
cp .env.example .env
```

5. Configure your environment variables in `.env`:
```
OPENAI_API_KEY=your_openai_api_key
WS_SERVER_URL=ws://localhost:8000/ws
DB_API_URL=https://069c626bcc34.ngrok.app/api/db
SONIC_RPC_URL=your_sonic_rpc_url
SONIC_CHAIN_ID=57054
DEFAULT_EXECUTION_INTERVAL=5
```

## Usage

1. Start the agent:
```bash
python src/main.py
```

2. The agent will connect to the WebSocket server and wait for configuration from the frontend.

3. Send configuration through WebSocket:
```json
{
    "type": "agent_config",
    "data": {
        "name": "MyAgent",
        "description": "This agent monitors and interacts with X contract...",
        "contract_address": "0x...",
        "contract_abi": [...],
        "functions": [
            {
                "name": "balanceOf",
                "type": "read",
                "parameters": [
                    {
                        "name": "account",
                        "type": "address"
                    }
                ]
            },
            {
                "name": "burn",
                "type": "write",
                "parameters": [
                    {
                        "name": "value",
                        "type": "uint256"
                    }
                ],
                "validation_rules": {
                    "value": {
                        "min": "0",
                        "max": "1000000"
                    }
                }
            }
        ],
        "execution_interval": 5
    }
}
```

4. Control the agent:
```json
{
    "type": "agent_control",
    "data": {
        "action": "start"  // or "stop"
    }
}
```

## WebSocket Message Types

### Incoming Messages

- `agent_config`: Configure the agent with contract details and functions
- `agent_control`: Control agent execution (start/stop)

### Outgoing Messages

- `agent_configured`: Confirmation of successful agent configuration
- `agent_started`: Confirmation that the agent has started
- `agent_stopped`: Confirmation that the agent has stopped
- `error`: Error message when something goes wrong

## Development

To add new functionality:

1. Add new action implementations in `src/actions/`
2. Update the agent's analysis logic in `src/models/agent.py`
3. Add new message handlers in `src/main.py` if needed

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT

## Deployment

### Railway Deployment

This project can be deployed to Railway using GitHub integration. For detailed instructions, see the [Railway Deployment Guide](RAILWAY_DEPLOYMENT.md).

Quick steps:
1. Push your code to GitHub
2. Set up a new project in Railway from your GitHub repository
3. Configure environment variables in the Railway dashboard
4. Railway will automatically build and deploy your application

For local development, use the `.env` file. For Railway, configure variables in the Railway dashboard. 