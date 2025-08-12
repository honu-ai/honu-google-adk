import jwt

from agent_router.conversation_utils import ConversationClient


def test__get_char_url(monkeypatch):

    @staticmethod
    def _fake_ping_server(chat_url):
        return 'host.docker.internal' not in chat_url
    monkeypatch.setattr(ConversationClient, ConversationClient._ping_conversation_server.__name__, _fake_ping_server)

    token_payload = {
        'url': 'http://host.docker.internal:8080',
        'hap_token_type': 'agent',
        'agent_id': 'external_agent/aHR0cDovL2xvY2FsaG9zdDo3OTk5L211bHRpX3Rvb2xfYWdlbnQvb3JnX0NyUXRvQnZpb2g3bjF0QjZ8d0ZUU1RncDFSbU9MT1ZCeHFBbVRNUXxxWEJWdlNBdlIybVNLSFpiVVVha0FR',
        'org_id': 'org_CrQtoBvioh7n1tB6'
    }
    token = jwt.encode(token_payload, "some_secret", algorithm="HS256")
    cc = ConversationClient.get_instance()
    chat_url = cc._get_chat_url(token)
    assert chat_url == "http://localhost:8008"

