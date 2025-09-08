from collections import defaultdict
from typing import Callable, Any

import httpx
import jwt
import structlog
from starlette import status

from .schema import Conversation, TextMessage, SupportedMessages

MAX_MESSAGE_RETRY = 10
MessageHandler = Callable[[Conversation, TextMessage], None]


class ConversationClientCouldNotCreateConversation(Exception):
    ...


class ConversationClient:
    """
    Accessed via ctxt.chat_client.
    Uses a singleton because we don't need multiple instances.
    """
    _instance = None

    app_logger: Any
    chat_timeout: int
    _status_history: dict[str, list[str]]
    chat_url: str | None = None

    @classmethod
    def get_instance(cls):
        if cls._instance is not None:
            return cls._instance
        inst = cls.__new__(cls)
        inst.app_logger = structlog.get_logger('hap_adk.conversation_client')
        inst.chat_timeout = 60

        # Maintains a history of statuses sent so we can manage nested statuses
        inst._status_history = defaultdict(list)
        cls._instance = inst

        return inst

    def __init__(self):
        raise NotImplementedError()

    def _ping_conversation_server(self, base_url: str) -> bool:
        try:
            # self._get_client(base_url, "").get('/')
            httpx.get(base_url, timeout=self.chat_timeout)
            return True
        except:
            return False

    def _get_chat_url(self, token: str) -> str:
        if self.chat_url is not None:
            return self.chat_url

        chat_url = jwt.decode(token, options={'verify_signature': False}).get('url', '').rstrip('/').replace('happi', 'chat').replace('8080', '8008')
        if self._ping_conversation_server(chat_url):
            self.chat_url = chat_url
            return chat_url

        if chat_url.startswith("http://host.docker.internal"):
            chat_url = "http://localhost:8008"
            if self._ping_conversation_server(chat_url):
                self.chat_url = chat_url
                return chat_url

        raise ValueError(f"Could not connect to URL: {chat_url}")

    def _get_client(self, token: str) -> httpx.Client:
        # Access current_context info for retrieving url/auth information
        return httpx.Client(
            base_url=self._get_chat_url(token),
            headers={'Authorization': f'Bearer {token}'},
            timeout=self.chat_timeout,
        )

    def send_message(self, token: str, conversation: Conversation, message: SupportedMessages):
        """
        Send a message to the Chat server.
        :param token: Access token.
        :param conversation: The Conversation data to send the Message to.
        :param message: The Message object to send. Can be any of the supported types of Message.
        :return: The response of the send request
        """
        payload = message.model_dump()
        response = self._get_client(token).post(
            f'/v1/conversations/{conversation.mdl_ref}/{conversation.conversation_id}/messages/',
            json=payload,
        )

        if response.status_code != status.HTTP_201_CREATED:
            self.app_logger.error(
                'failed_to_send_message',
                response=f'{response.status_code}: {response.text}',
                conversation=conversation,
                message=payload,
            )
        else:
            self.app_logger.info(
                'conversation_client_sent_message',
                extra=dict(
                    conversation=conversation,
                    message=response.json(),
                )
            )
        return response

    def create_conversation(self, token: str, model_ref: str, name: str = '') -> Conversation:
        """
        Create a Conversation in the system. Will add the agent and any users for the model to it for conversations.
        Uses current_context to retrieve the model_ref.
        :param token: Access token.
        :param model_ref: Model reference
        :param name: The (optional) name of the room.
        :raise httpx.HTTPStatusError: If an error occurs when trying to create the room.
        """
        payload = {'name': name}
        response = self._get_client(token).post(
            f'/v1/conversations/{model_ref}',
            json=payload,
        )

        if response.status_code != status.HTTP_201_CREATED:
            self.app_logger.error(
                f'failed_to_create_conversation_in_server',
                response=f'{response.status_code}: {response.text}',
                model_ref=model_ref,
            )
            raise ConversationClientCouldNotCreateConversation()
        else:
            conv = Conversation(**response.json())
            self.app_logger.info(
                f'created_conversation_in_server',
                model_ref=model_ref,
                conversation=conv.model_dump(),
            )
        return conv

    def get_conversations_for_model(self, token: str, model_ref: str, with_messages: int = 0) -> list[Conversation]:
        response = self._get_client(token).get(
            f"/v1/conversations/{model_ref}",
            params={'with_messages': with_messages},
        )

        if response.status_code != status.HTTP_200_OK:
            self.app_logger.error(
                'failed_to_fetch_conversations_list',
                response=f'{response.status_code}: {response.text}',
                model_ref=model_ref,
            )
            return []
        return [Conversation(**conv) for conv in response.json()]

    def delete_conversation(self, token: str, model_ref: str, conv_id: str):
        response = self._get_client(token).delete(f"/v1/conversations/{model_ref}/{conv_id}")
        if response.status_code != status.HTTP_204_NO_CONTENT:
            self.app_logger.error(
                'failed_to_delete_conversation',
                response=f'{response.status_code}: {response.text}',
                model_ref=model_ref,
                conversation_id=conv_id,
            )

    def set_chat_status(self, token: str, conversation: Conversation, chat_status: str | None = None):
        response = self._get_client(token).patch(
            f'/v1/conversations/{conversation.mdl_ref}/{conversation.conversation_id}',
            json={'status': chat_status}
        )
        if not response.is_success:
            self.app_logger.error(
                'failed_to_set_chat_status',
                conversation=conversation,
                chat_status=chat_status,
                response=f'{response.status_code}: {response.text}'
            )
