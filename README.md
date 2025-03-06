# Zephyrus Autonomous Contract Agent

An autonomous agent system for interacting with smart contracts on the Sonic blockchain based on scheduled actions.

## Overview

This agent system allows for automated interaction with smart contracts based on predefined schedules and actions. The agent receives configuration from a frontend via WebSocket, including:

- Agent name and description
- Contract functions to interact with
- Execution schedule (in minutes)
- Contract ABI and address

## Features

- WebSocket server for real-time communication with frontend
- Scheduled execution of contract functions
- Support for both read and write contract functions
- Parameter validation for contract function calls
- Integration with OpenAI models for intelligent decision making

## Project Structure

```
Zephyrus_Agent/
├── src/
│   ├── actions/       # Contract interaction actions
│   ├── core/          # Core agent functionality
│   ├── config/        # Configuration settings
│   ├── utils/         # Utility functions
│   └── main.py        # Application entry point
├── requirements.txt   # Python dependencies
└── README.md          # This file
```

## Installation

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Create a `.env` file with required environment variables (see Configuration section)

## Configuration

Create a `.env` file in the root directory with the following variables:

```
OPENAI_API_KEY=your_openai_api_key
WEBSOCKET_HOST=localhost
WEBSOCKET_PORT=8765
HARDHAT_API_URL=http://localhost:3000
```

## Usage

1. Start the agent: `python src/main.py`
2. Connect to the WebSocket server from your frontend application
3. Send agent configuration via WebSocket
4. The agent will start executing the specified actions based on the schedule

## License

MIT
