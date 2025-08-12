import base64

import json
from fastapi import APIRouter
from google.adk.cli.adk_web_server import AgentRunRequest
from google.adk.events import Event
from google.genai.types import Part, Content
from starlette import status
from starlette.exceptions import HTTPException

from .conversation_utils import ConversationClient
from .schema import InitEngagement, DisengageAgent, MessageNotification, TextMessage
from .utils import LocalSessionClient


class HonuAgentRouter:

    def __init__(self, port: int):
        self.agent_router = self._agent_engagement_api()

        # store token
        self.local_session_client = LocalSessionClient(port)
        self.USER_ID = "user"  # could be the model ref for now

    def _agent_engagement_api(self) -> APIRouter:
        api = APIRouter(prefix="/hapra/v1", tags=['adk'])

        @api.get("/health_check/ping/{value}", status_code=status.HTTP_200_OK)
        def ping_pong(value: str) -> str:
            return value

        @api.post("/agents/{agent_id}/init_engagement/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
        @api.post("/agents/{agent_id}/init_engagement", status_code=status.HTTP_201_CREATED)
        def init_engagement(agent_id: str, init: InitEngagement) -> None:

            conv_client = ConversationClient.get_instance()
            conv = conv_client.create_conversation(init.auth_token, init.mdl_ref, name="multi_tool_agent_conversation")
            session_id = conv.conversation_id

            payload = dict(
                token=init.auth_token,
                model_ref=init.mdl_ref
            )

            response = self.local_session_client.client.post(f"/apps/{agent_id}/users/{self.USER_ID}/sessions/{session_id}", json=payload)
            if response.status_code != status.HTTP_200_OK:
                raise HTTPException(status_code=response.status_code, detail=response.text)

        @api.post("/agents/{agent_id}/disengage/", status_code=status.HTTP_200_OK, include_in_schema=False)
        @api.post("/agents/{agent_id}/disengage", status_code=status.HTTP_200_OK)
        def disengage_agent(agent_id: str, disengage: DisengageAgent) -> None:
            conversation_client = ConversationClient.get_instance()
            sessions = self.local_session_client.get_sessions_for_model_ref(agent_id, disengage.mdl_ref)
            for token, conv_id in sessions:
                conversation_client.delete_conversation(token, disengage.mdl_ref, conv_id)
                self.local_session_client.delete_session(agent_id, conv_id)

        @api.post("/messages/", status_code=status.HTTP_200_OK, include_in_schema=False)
        @api.post("/messages", status_code=status.HTTP_200_OK)
        def message_notification(payload: MessageNotification):
            """ With a message notification now we need to invoke the llm"""
            app_name = base64.b64decode(payload.agent_signature.removeprefix('external_agent/').encode()).decode().split('/')[3]
            conversation_client = ConversationClient.get_instance()
            conv = payload.conversation
            token = self.local_session_client.get_token(app_name, conv.conversation_id)
            conversation_client.set_chat_status(token, conv, 'thinking')
            run_request = AgentRunRequest(
                app_name=app_name,
                user_id=self.USER_ID,
                session_id=payload.conversation.conversation_id,
                new_message=Content(
                    parts=[Part(text=payload.message.payload.body)],
                    role="user",
                ),
                streaming=False,
            )

            for sse in self.local_session_client.run_sse(run_request):
                if sse.event != 'message':
                    continue

                # Capture response and send to chat
                message = Event(**json.loads(sse.data))
                for part in message.content.parts:
                    if part.function_call:
                        conversation_client.set_chat_status(token, conv, f'running tool: {part.function_call.name}')
                    elif part.text:
                        conversation_client.send_message(
                            token,
                            conv,
                            TextMessage(body=part.text)
                        )
                    elif part.function_response:
                        conversation_client.set_chat_status(token, conv, 'thinking')
                    else:
                        print('Unhandled message type')
                        print(message)
            conversation_client.set_chat_status(token, conv, None)

        return api


