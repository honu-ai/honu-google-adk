# honu-google-adk

A Python package that integrates Google AI Development Kit (ADK) agents with the Honu platform, providing seamless toolset connectivity and MCP (Model Context Protocol) support.

## Installation

### Using uv (Recommended for Google tutorials)

```bash
uv add git+https://github.com/honu-ai/honu-google-adk.git --branch main
```

### Using Poetry

```bash
poetry add git+https://github.com/honu-ai/honu-google-adk.git@main
```

## Quick Start

To connect your agent to the Honu platform, you need to:

1. Include the Honu router in your FastAPI application
2. Add the Honu toolset to your agent configuration
3. Configure environment variables

## Configuration

### Environment Setup

Create a `.env` file in your project root:

```bash
MCP_HOST="http://mcp.honu.ai/mcp"
PORT=7999  # Optional: defaults to 7999 locally, uses Cloud Run's PORT in production
SESSION_SERVICE_URI=sqlite:///./sessions.db
```

### 1. Include the Honu Router

Create your `main.py` file with the following structure:

```python
import os

import uvicorn
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from honu_google_adk.agent_router.honu_router import HonuAgentRouter


SESSION_SERVICE_URI = os.environ.get("SESSION_SERVICE_URI", None)
if SESSION_SERVICE_URI is None:
    raise ValueError("No SESSION_SERVICE_URI found")


# Get the directory where main.py is located
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Example session service URI (e.g., SQLite)
SESSION_SERVICE_URI = SESSION_SERVICE_URI
# Example allowed origins for CORS
ALLOWED_ORIGINS = ["http://localhost", "http://localhost:8080", "*"]
# Set web=True if you intend to serve a web interface, False otherwise
SERVE_WEB_INTERFACE = True
PORT = int(os.environ.get('PORT', 7999))

# Call the function to get the FastAPI app instance
# Ensure the agent directory name ('capital_agent') matches your agent folder
app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_service_uri=SESSION_SERVICE_URI,
    allow_origins=ALLOWED_ORIGINS,
    web=SERVE_WEB_INTERFACE,
    # reload_agents=True,
)

app.include_router(HonuAgentRouter(PORT).agent_router)

if __name__ == "__main__":
    # Use the PORT environment variable provided by Cloud Run, defaulting to 8080
    uvicorn.run(app, host="0.0.0.0", port=PORT)
```

### 2. Configure Your Agent with Honu Tools

```python
from google.adk import Agent
from honu_google_adk.main import HonuToolSet

# Initialize Honu toolset (specify the MCP service you want to use)
honu_tools = HonuToolSet("trello")  # Available: "trello", "slack", etc.

# Create your agent
root_agent = Agent(
    name="honu_trello_agent",
    model="gemini-2.0-flash",
    description="Agent with Honu platform integration for Trello management",
    tools=[
        honu_tools,
        # Add other tools as needed
    ]
)
```

### 3. Add Display Information for Honu Chat
Adding a dictionary of agent_name -> AgentDisplayInformation to your HonuAgentRouter can allow you to customise how your agent shows up in the Platform.

```python
display_info = {
    'honu_trello_agent': AgentDisplayInformation(
        name='Trello Helper',
        avatar_url='<url for a picture for the agent>' or None,
        description='This is an agent to help you organise and manage your Trello board.',
    ),
}
app.include_router(HonuAgentRouter(PORT, display_info).agent_router)
```

## Deployment

### Cloud Run Deployment

This package is designed to work with Google Cloud Run. VertexAI deployment is not currently supported.

**Important**: Ensure your `main.py` includes the Honu router configuration as shown above for proper Cloud Run integration.

### Key Requirements for Deployment

- Use Cloud Run (VertexAI not supported)
- Include the `HonuAgentRouter` in your FastAPI app
- Configure appropriate CORS origins for your domain
- Set environment variables in your Cloud Run service

## Available MCP Services

The `HonuToolSet` supports various MCP services:

- `"trello"` - Trello board and card management
- Additional services can be specified based on your Honu platform configuration

## Troubleshooting

### Common Issues

1. **Port Configuration**: Ensure your `PORT` environment variable is properly set for Cloud Run deployment
2. **MCP Connection**: Verify your `MCP_HOST` is accessible from your deployment environment
3. **CORS Issues**: Update `ALLOWED_ORIGINS` to include your frontend domain

### Development Tips

- Set `reload_agents=True` during development for automatic reloading
- Use `web=True` if you need to serve a web interface alongside your agent
- Test locally before deploying to Cloud Run

## Contributing

This package follows standard Python development practices. When contributing:

1. Install with development dependencies
2. Follow the existing code structure
3. Test both local and Cloud Run deployments

## License

[Add your license information here]
