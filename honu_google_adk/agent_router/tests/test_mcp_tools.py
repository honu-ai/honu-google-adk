from google.adk.tools import BaseTool

from honu_google_adk.main import HonuToolSet


def test_mcp_tool_is_valid():
    test_tool = BaseTool(name='test_tool', description='test_description')

    valid_tags = {"trello"}

    test_tool.meta = None
    assert not HonuToolSet._is_valid_tool(valid_tags, test_tool)

    test_tool.meta = {'_fastmcp': {'tags': ['public', 'trello', 'utility']}}
    assert HonuToolSet._is_valid_tool(valid_tags, test_tool)

    test_tool.meta = {'_fastmcp': {'tags': ['public', 'utility']}}
    assert not HonuToolSet._is_valid_tool(valid_tags, test_tool)

