import json
from typing import Optional

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import BaseTool, ToolContext, FunctionTool
from google.adk.tools.base_toolset import BaseToolset

from honu_google_adk.utils import _get_client, _get_unauth_client


def register_token(token: str, tool_context: ToolContext) -> dict:
    tool_context.state['token'] = token
    return dict(message='token saved')

def retrieve_token(tool_context: ToolContext) -> dict:
    token = tool_context.state.get('token')
    return dict(message="token retrieved", token=token)

def register_model(model_ref: str, tool_context: ToolContext) -> dict:
    tool_context.state['model_ref'] = model_ref
    return dict(message='registered models')

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

    async def get_tools(
            self,
            readonly_context: Optional[ReadonlyContext] = None,
    ) -> list[BaseTool]:
        client = _get_unauth_client()
        tools=[]
        async with client:
            for tool in await client.list_tools():
                tools.append(
                    FunctionTool(
                        create_tool(
                            tool.name,
                            tool.description
                        )
                    )
                )

        return tools

    async def close(self):
        return None
