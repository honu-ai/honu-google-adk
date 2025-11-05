import traceback
from collections import defaultdict
from typing import Optional, Any

import structlog
from google.adk.agents import InvocationContext, BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event
from google.adk.models import LlmRequest, LlmResponse
from google.adk.plugins import BasePlugin
from google.adk.tools import BaseTool, ToolContext
from google.genai import types

from honu_google_adk.agent_router.conversation_utils import ConversationClient
from honu_google_adk.agent_router.schema import Conversation, TextMessage


class HonuConversationPlugin(BasePlugin):
    """Plugin that loops messages back into the HAP Conversation server"""

    def __init__(self, name: str):
        super().__init__(name)
        self.conversation_client = ConversationClient.get_instance()
        self.logger = structlog.get_logger('honu_google_adk.honu_conversation_plugin')

    def _get_conv_for_session_id(self, token: str, model_ref: str, session_id: str) -> Conversation | None:
        convs = [
            c
            for c in
            self.conversation_client.get_conversations_for_model(token, model_ref)
            if c.conversation_id == session_id
        ]
        if not convs:
            return None
        return convs[0]

    async def before_agent_callback(self, *, agent: BaseAgent, callback_context: CallbackContext) -> Optional[types.Content]:
        token = callback_context.state.get('token')
        model_ref = callback_context.state.get('model_ref')
        if token is None or model_ref is None:
            # Possible if we're calling a sub-agent
            return

        # Try to get the conversation for the current session
        conversation = self._get_conv_for_session_id(token, model_ref, callback_context.session.id)
        if conversation is None:
            return

        # Set the status for the conversation
        self.conversation_client.set_chat_status(token, conversation, 'thinking')

    async def after_agent_callback(self, *, agent: BaseAgent, callback_context: CallbackContext) -> Optional[types.Content]:
        # Check for token and model ref in state
        token = callback_context.state.get('token')
        model_ref = callback_context.state.get('model_ref')
        if token is None or model_ref is None:
            # Possible if we're calling a sub-agent
            return

        # Try to get the conversation for the current session
        conversation = self._get_conv_for_session_id(token, model_ref, callback_context.session.id)
        if conversation is None:
            return

        # Set the status for the conversation
        self.conversation_client.set_chat_status(token, conversation, None)

    async def on_event_callback(self, *, invocation_context: InvocationContext, event: Event) -> Optional[Event]:
        session_id = invocation_context.session.id
        state = invocation_context.session.state
        token = state.get('token')
        model_ref = state.get('model_ref')
        if token is None or model_ref is None:
            # Possible if we're calling a sub-agent
            return

        # Try to get the conversation for the current session
        conversation = self._get_conv_for_session_id(token, model_ref, session_id)
        if conversation is None:
            return

        # Loop through the parts of the event and update the conversation accordingly
        for part in event.content.parts:
            if part.function_call:
                self.conversation_client.set_chat_status(token, conversation, f'running tool: {part.function_call.name}')
                self.logger.info('function_call_event', **part.function_call.model_dump())
            elif part.text:
                self.conversation_client.send_message(
                    token,
                    conversation,
                    TextMessage(body=part.text)
                )
            elif part.function_response:
                self.conversation_client.set_chat_status(token, conversation, 'thinking')
                self.logger.info('function_response_event', **part.function_response.model_dump())
            else:
                self.logger.warning('unhandled_message_type', **part)

    async def on_model_error_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_request: LlmRequest,
        error: Exception,
    ) -> Optional[LlmResponse]:
        token = callback_context.state.get('token')
        model_ref = callback_context.state.get('model_ref')
        if token is None or model_ref is None:
            # Log as much info as we can
            self.logger.error('llm_model_error', llm_request=llm_request, exc_info=traceback.print_exception(error))
            return

        # Try to get the conversation for the current session
        conversation = self._get_conv_for_session_id(token, model_ref, callback_context.session.id)
        if conversation is None:
            self.logger.error('llm_model_error', llm_request=llm_request, exc_info=traceback.print_exception(error), model_ref=model_ref)
            return

        # Set the status for the conversation
        self.conversation_client.send_message(
            token,
            conversation,
            TextMessage(body='An error occurred handling your last message. Please try again or contact support if this persists.'),
        )

    async def on_tool_error_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        error: Exception,
    ) -> Optional[dict]:
        token = tool_context.state.get('token')
        model_ref = tool_context.state.get('model_ref')
        if token is None or model_ref is None:
            # Log as much info as we can
            self.logger.error(
                'tool_error',
                exc_info=traceback.print_exception(error),
                tool=tool.name,
                args=tool_args,
            )
            return

        # Try to get the conversation for the current session
        conversation = self._get_conv_for_session_id(token, model_ref, tool_context.session.id)
        if conversation is None:
            # Log as much info as we can
            self.logger.error(
                'tool_error',
                exc_info=traceback.print_exception(error),
                tool=tool.name,
                args=tool_args,
                model_ref=model_ref,
            )
            return

        # Set the status for the conversation
        self.conversation_client.send_message(
            token,
            conversation,
            TextMessage(body='An error occurred handling your last message. Please try again or contact support if this persists.'),
        )
