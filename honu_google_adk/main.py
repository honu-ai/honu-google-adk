from google.genai import types
import json
from fastmcp import Client
from fastmcp.client import StreamableHttpTransport
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import BaseTool
from google.adk.tools import ToolContext
from google.adk.tools.base_toolset import BaseToolset
from google.genai import types
from mcp import Tool
from typing import Optional, Any
from typing_extensions import override


class HonuMCPFunctionTool(BaseTool):
    mcp_tool: Tool
    mcp_host: str

    def __init__(
            self,
            mcp_tool: Tool,
            mcp_host: str,
    ):
        super().__init__(
            name=mcp_tool.name,
            description=mcp_tool.description,
        )
        self.mcp_tool = mcp_tool
        self.mcp_host = mcp_host

    @override
    def _get_declaration(self) -> Optional[types.FunctionDeclaration]:
        return types.FunctionDeclaration(
            name=self.mcp_tool.name,
            description=self.mcp_tool.description,
            parameters_json_schema=self.mcp_tool.inputSchema,
            response_json_schema=self.mcp_tool.outputSchema,
        )

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

    @override
    async def run_async(
      self, *, args: dict[str, Any], tool_context: ToolContext
  ) -> Any:
        client = self._get_client(tool_context)
        print('calling', self.mcp_tool.name, 'with arguments', args)

        async with client:
            # Execute operations
            result = await client.call_tool(self.mcp_tool.name, args)
        response: dict[str, Any] = {'success': True}
        if result.content:
            try:
                response['artefacts'] = json.loads(result.content[0].text)
            except:
                response['text'] = result.content[0].text
                response['error_msg'] = 'Could not unwrap response into JSON. Plaintext response has been provided instead.'
        print('received response', response, 'for tool', self.mcp_tool.name, 'tool_result', result)
        return response

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
            timeout=600,
        )
        return client

    def _is_valid_tool(self, tool: Tool) -> bool:
        if self.tags is None:
            return True

        if not hasattr(tool, "meta"):
            return False

        if getattr(tool, 'meta') is None:
            return False

        tool_tags = set(getattr(tool, 'meta').get('_fastmcp', {}).get('tags', []))
        return len(self.tags & tool_tags) > 0

    async def get_tools(
            self,
            readonly_context: Optional[ReadonlyContext] = None,
    ) -> list[BaseTool]:
        client = self._get_unauth_client()
        async with client:
            return [
                HonuMCPFunctionTool(tool, self.mcp_host)
                for tool in (await client.list_tools())
                if self._is_valid_tool(tool)
            ]


    async def close(self):
        return None
