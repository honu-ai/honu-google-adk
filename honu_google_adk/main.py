import json
from typing import Optional

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import BaseTool, ToolContext, FunctionTool
from google.adk.tools.base_toolset import BaseToolset

from honu_google_adk.utils import _get_client, _get_unauth_client

def create_tool(function_name: str, function_description: str):

    async def _inner(args: dict, tool_context: ToolContext):
        client = _get_client(tool_context)

        async with client:
            # Execute operations
            result = await client.call_tool(function_name, args)

        return dict(
            message='success',
            artefacts=json.loads(result.content[0].text)
        )

    _inner.__doc__ = function_description
    _inner.__name__= function_name

    return _inner

class HonuToolSet(BaseToolset):
    tags: set[str] | None = None

    def __init__(self, *tags_to_filter_by: str):
        if len(tags_to_filter_by):
            self.tags = set(tags_to_filter_by)
        super().__init__(tool_filter=None)

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
        client = _get_unauth_client()
        tools=[]
        async with client:
            for tool in await client.list_tools():
                if self._is_valid_tool(self.tags, tool):
                    tools.append(FunctionTool(create_tool(tool.name,tool.description)))

        return tools

    async def close(self):
        return None
