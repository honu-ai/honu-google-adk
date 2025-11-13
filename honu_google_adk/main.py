import json
from typing import Optional

from fastmcp import Client
from fastmcp.client import StreamableHttpTransport
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import BaseTool, FunctionTool
from google.adk.tools import ToolContext
from google.adk.tools.base_toolset import BaseToolset


class HonuToolSet(BaseToolset):
    tags: set[str] | None = None

    def __init__(self, mcp_host: str, *tags_to_filter_by: str):
        self.mcp_host = mcp_host
        if len(tags_to_filter_by):
            self.tags = set(tags_to_filter_by)
        super().__init__(tool_filter=None)

    def _get_unauth_client(self):
        client = Client(
            transport=StreamableHttpTransport(self.mcp_host),
        )
        return client

    def _get_client(self, tool_context: ToolContext):
        token = tool_context.state.get('token')
        model_ref = tool_context.state.get('model_ref')

        # In-memory server (ideal for testing)
        client = Client(
            transport=StreamableHttpTransport(
                self.mcp_host,
                headers={"X-HONU-MODEL": model_ref},
            ),
            auth=token,
        )
        return client

    @staticmethod
    def _is_valid_tool(valid_tool_tags: set[str], tool: BaseTool) -> bool:
        if valid_tool_tags is None:
            return True

        if not hasattr(tool, "meta"):
            return False

        if getattr(tool, 'meta') is None:
            return False

        tool_tags = set(getattr(tool, 'meta').get('_fastmcp', {}).get('tags', []))
        return len(valid_tool_tags & tool_tags) > 0

    async def get_tools(
            self,
            readonly_context: Optional[ReadonlyContext] = None,
    ) -> list[BaseTool]:
        client = self._get_unauth_client()
        tools=[]
        async with client:
            for tool in await client.list_tools():
                if self._is_valid_tool(self.tags, tool):
                    tools.append(
                        FunctionTool(
                            self.create_tool(tool.name,tool.description)
                        )
                    )

        return tools

    def create_tool(self, function_name: str, function_description: str):
        async def _inner(args: dict, tool_context: ToolContext):
            client = self._get_client(tool_context)

            async with client:
                # Execute operations
                result = await client.call_tool(function_name, args)
            response = {'message': 'success'}
            if result.content:
                try:
                    response['artefacts'] = json.loads(result.content[0].text)
                except:
                    print(result.content[0].text)
            print('received response', response, 'for tool', function_name)
            return response

        _inner.__doc__ = function_description
        _inner.__name__ = function_name

        return _inner

    async def close(self):
        return None
