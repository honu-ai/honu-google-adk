from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, model_validator


class InitEngagement(BaseModel):
    mdl_ref: str
    auth_token: str
    agent_signature: str


class DisengageAgent(BaseModel):
    mdl_ref: str
    agent_signature: str


class TextMessage(BaseModel):
    """
    A Simple Text Message
    """
    msgtype: Literal['honu.text'] = 'honu.text'
    body: str


class MessageResponse(BaseModel):
    """
    The details of a possible response an Agent can provide.
    The `text` field is the `text` to respond with.
    The `label` field is the controllable value for the `label` the response button should render with.
    """
    text: str
    label: str | None = None

    @model_validator(mode='after')
    def use_text_as_label_if_none_is_provided(self) -> Self:
        if self.label is None:
            self.label = self.text
        return self


class MessageWithResponses(BaseModel):
    """
    A Text Message with some suggested response that the User can use to quickly respond
    """
    msgtype: Literal['honu.quickresponses'] = 'honu.quickresponses'
    body: str
    responses: list[MessageResponse]


class MessageWithArtefacts(BaseModel):
    """
    A Text Message with some Artefact information to render
    """
    msgtype: Literal['honu.artefacts'] = 'honu.artefacts'
    body: str
    artefacts: list[dict]


class MessageWithActions(BaseModel):
    """
    A Text Message with some Actions to prompt the User to potentially run.
    """
    msgtype: Literal['honu.actions'] = 'honu.actions'
    body: str
    actions: list[dict]


SupportedMessages = TextMessage | MessageWithResponses | MessageWithArtefacts | MessageWithActions


class HAPMessage(BaseModel):
    message_id: str
    author_id: str
    timestamp: datetime
    payload: SupportedMessages
    # List of participants who have read the message
    read_by: list[str] = []


class ConversationParticipant(BaseModel):
    participant_id: str
    chat_status: str | None = None


class ConversationMetadata(BaseModel):
    name: str
    created_by: str
    created_at: datetime
    users: list[ConversationParticipant]
    agents: list[ConversationParticipant]


class Conversation(BaseModel):
    mdl_ref: str
    conversation_id: str
    metadata: ConversationMetadata
    messages: list[HAPMessage] = []


class MessageNotification(BaseModel):
    agent_signature: str
    conversation: Conversation
    message: HAPMessage

