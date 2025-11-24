import base64

import json
import jwt
from datetime import datetime, timezone
from fastapi import APIRouter
from google.adk.cli.adk_web_server import RunAgentRequest
from google.adk.events import Event
from google.genai.types import Part, Content
from pydantic import BaseModel
from starlette import status
from starlette.exceptions import HTTPException
import structlog

from honu_google_adk.agent_router.tasks_utils import ModelTasksAPIClient

from .conversation_utils import ConversationClient
from .schema import GADKAgentSchedulerPayload, HAPMessage, InitEngagement, DisengageAgent, MessageNotification, TextMessage, AgentDisplayInformation
from .utils import LocalSessionClient


class SignaturePayload(BaseModel):
    agent_url: str
    app_name: str
    model_ref: str

    @classmethod
    def from_signature(cls, signature: str) -> 'SignaturePayload':
        payload = json.loads(base64.b64decode(signature.removeprefix('external_agent/').encode()).decode())
        return cls(**payload)


class HonuAgentRouter:

    def __init__(self, hostname: str, port: int, agent_display_cards: dict[str, AgentDisplayInformation] | None = None):
        self.agent_router = self._agent_engagement_api()
        self.display_info = agent_display_cards or {}
        self.logger = structlog.get_logger('honu_agent_router')

        # store token
        self.hostname = hostname
        self.local_session_client = LocalSessionClient(port)
        self.USER_ID = "user"  # could be the model ref for now

    def _agent_engagement_api(self) -> APIRouter:
        api = APIRouter(prefix="/hapra/v1", tags=['adk'])

        @api.post("/messages/", status_code=status.HTTP_200_OK, include_in_schema=False)
        @api.post("/messages", status_code=status.HTTP_200_OK)
        def message_notification(payload: MessageNotification):
            """ With a message notification now we need to invoke the llm"""
            sig_payload = SignaturePayload.from_signature(payload.agent_signature)
            run_request = RunAgentRequest(
                app_name=sig_payload.app_name,
                user_id=self.USER_ID,
                session_id=payload.conversation.conversation_id,
                new_message=Content(
                    parts=[Part(text=payload.message.payload.body)],
                    role="user",
                ),
                streaming=False,
            )
            self.local_session_client.run(run_request)

        @api.get("/health_check/ping/{value}", status_code=status.HTTP_200_OK)
        def ping_pong(value: str) -> str:
            return value

        @api.get('/cards/{app_name}/', include_in_schema=False)
        @api.get('/cards/{app_name}')
        def get_agent_card(app_name: str) -> AgentDisplayInformation:
            card = self.display_info.get(app_name)
            if card is None:
                card = AgentDisplayInformation(
                    name=app_name,
                    avatar_url=None,
                    description='An Agent built to help you!',
                )
            return card

        @api.post("/agents/{agent_id}/init_engagement/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
        @api.post("/agents/{agent_id}/init_engagement", status_code=status.HTTP_201_CREATED)
        def init_engagement(agent_id: str, init: InitEngagement) -> None:
            conv_client = ConversationClient.get_instance()
            # Get the data from the agent signature for making the chat name
            sig_payload = SignaturePayload.from_signature(init.agent_signature)
            conv = conv_client.create_conversation(init.auth_token, init.mdl_ref, name=sig_payload.app_name)
            session_id = conv.conversation_id

            payload = dict(
                token=init.auth_token,
                model_ref=init.mdl_ref
            )

            response = self.local_session_client.client.post(f"/apps/{agent_id}/users/{self.USER_ID}/sessions/{session_id}", json=payload)
            if response.status_code != status.HTTP_200_OK:
                raise HTTPException(status_code=response.status_code, detail=response.text)

            # Send a fake message to the agent to prompt an introduction message to the user
            fake_message = MessageNotification(
                agent_signature=init.agent_signature,
                conversation=conv,
                message=HAPMessage(
                    message_id='',
                    author_id='',
                    timestamp=datetime.now(timezone.utc),
                    payload=TextMessage(body='honulabs_system_message: You have just been engaged by a User. Please introduce yourself to them.'),
                )
            )
            message_notification(fake_message)

            # Also create a task to run the brainbeat
            tasks_client = ModelTasksAPIClient(init.auth_token, init.mdl_ref)
            task_payload = GADKAgentSchedulerPayload(
                app_name=agent_id,
                session_id=session_id,
                message='honulabs_system_message: This is an automated system message. It is time to run your regular "brainbeat", where you check on the user\'s data, and perform any daily tasks you are instructed to do. Write your message as though you are coming directly to the User.',
            )
            tasks_client.create_task(
                task_payload.model_dump(),
                f'{agent_id} Brainbeat',
                f'Brainbeat for {agent_id}.',
                '0 9 * * *',
                f'{self.hostname}/hapra/v1/scheduler',
            )

        @api.post("/agents/{agent_id}/disengage/", status_code=status.HTTP_200_OK, include_in_schema=False)
        @api.post("/agents/{agent_id}/disengage", status_code=status.HTTP_200_OK)
        def disengage_agent(agent_id: str, disengage: DisengageAgent) -> None:
            conversation_client = ConversationClient.get_instance()
            sessions = self.local_session_client.get_sessions_for_model_ref(agent_id, disengage.mdl_ref)
            for token, conv_id in sessions:

                # Delete all the tasks
                client = ModelTasksAPIClient(token, disengage.mdl_ref)
                try:
                    client.delete_all_my_tasks()
                except:
                    print('Could not delete tasks for model ref', disengage.mdl_ref)

                # Then delete all the conversations
                try:
                    conversation_client.delete_conversation(token, disengage.mdl_ref, conv_id)
                except:
                    pass
                self.local_session_client.delete_session(agent_id, conv_id)

        @api.post("/scheduler/", status_code=status.HTTP_200_OK, include_in_schema=False)
        @api.post("/scheduler", status_code=status.HTTP_200_OK)
        def run_task(payload: GADKAgentSchedulerPayload) -> str:
            # Check that the session and app_name combo are correct
            run_request = RunAgentRequest(
                app_name=payload.app_name,
                user_id=self.USER_ID,
                session_id=payload.session_id,
                new_message=Content(
                    parts=[Part(text=payload.message)],
                    role="user",
                ),
                streaming=False,
            )
            try:
                self.local_session_client.run(run_request)
                return 'success'
            except Exception as e:
                return str(e.args)

        return api
