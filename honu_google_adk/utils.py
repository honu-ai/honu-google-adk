import os

from fastmcp import Client
from fastmcp.client import StreamableHttpTransport
from google.adk.tools import ToolContext

MCP_HOST = os.getenv("MCP_HOST", None)

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
