import traceback
from fastapi import HTTPException
from typing import Iterator

import httpx
from google.adk.cli.adk_web_server import RunAgentRequest
from httpx_sse import connect_sse, ServerSentEvent
from starlette import status


class LocalSessionClient:

    def __init__(self, port):
        AGENT_URL = f"http://localhost:{port}"
        self.AGENT_NAME = "multi_tool_agent"
        self.USER_ID = "user"  # could be the model ref for now

        headers = {
            "accept": "application/json",
            "Content-type": "application/json"
        }
        self.client = httpx.Client(base_url=AGENT_URL, headers=headers, timeout=None)

    def get_sessions_for_model_ref(self, app_name: str, model_ref: str) -> list[(str, str)]:
        url = f"/apps/{app_name}/users/{self.USER_ID}/sessions"
        response = self.client.get(url)
        if response.status_code != status.HTTP_200_OK:
            raise Exception(f"Get session ({url}) came back with status: {response.status_code}: {response.text}")

        return [
            (session['state']['token'], session['id'])
            for session in response.json()
            if session['state'].get('model_ref', None) == model_ref
        ]

    def delete_session(self, app_name: str, session_id: str):
        response = self.client.delete(f"/apps/{app_name}/users/{self.USER_ID}/sessions/{session_id}")
        if not response.is_success:
            raise Exception(f"Delete session came back with status: {response.status_code}: {response.text}")

    def run_sse(self, request: RunAgentRequest) -> Iterator[ServerSentEvent]:
        try:
            with connect_sse(self.client, 'POST', '/run_sse', json=request.model_dump()) as event_source:
                for sse in event_source.iter_sse():
                    yield sse
        except:
            traceback.print_exc()
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_session_state(self, app_name: str, session_id: str) -> dict:
        url = f'/apps/{app_name}/users/{self.USER_ID}/sessions/{session_id}'
        response = self.client.get(url)
        if response.status_code != status.HTTP_200_OK:
            raise Exception(f"Get session (url) came back with status: {response.status_code}: {response.text}")
        return response.json()['state']

    def get_token(self, app_name: str, session_id: str) -> str | None:
        token = self.get_session_state(app_name, session_id).get('token', None)
        return token

    def get_model_ref(self, app_name, session_id: str) -> str | None:
        token = self.get_session_state(app_name, session_id).get('model_ref', None)
        return token

