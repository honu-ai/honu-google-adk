import os

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client import StreamableHttpTransport
from google.adk.tools import ToolContext

load_dotenv()

MCP_HOST = os.getenv("MCP_HOST", "http://localhost:8282/mcp/")
print(f"MCP_HONU: {MCP_HOST}")

def _get_unauth_client():
    # In-memory server (ideal for testing)
    client = Client(
        transport=StreamableHttpTransport(MCP_HOST),
    )
    return client

def _get_client(tool_context: ToolContext):
    token = tool_context.state.get('token')
    model_ref = tool_context.state.get('model_ref')

    # In-memory server (ideal for testing)
    client = Client(
        transport=StreamableHttpTransport(
            MCP_HOST,
            headers={"X-HONU-MODEL": model_ref},
        ),
        auth=token,
    )
    return client
