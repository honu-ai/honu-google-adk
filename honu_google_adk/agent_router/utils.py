import traceback
from fastapi import HTTPException
from typing import Iterator, Any

import httpx
from google.adk.cli.adk_web_server import RunAgentRequest
from httpx_sse import connect_sse, ServerSentEvent
from starlette import status


class LocalSessionClient:

    def __init__(self, port):
        self.agent_url = f"http://localhost:{port}"
        self.USER_ID = "user"  # could be the model ref for now

    @property
    def client(self):
        return httpx.AsyncClient(
            base_url=self.agent_url,
            headers={
                "accept": "application/json",
                "Content-type": "application/json"
            },
            timeout=None,
        )

    async def get_sessions_for_model_ref(self, app_name: str, model_ref: str) -> list[(str, str)]:
        async with self.client as client:
            response = await client.get(f"/apps/{app_name}/users/{self.USER_ID}/sessions")
            if response.status_code != status.HTTP_200_OK:
                response.raise_for_status()

            return [
                (session['state']['token'], session['id'])
                for session in response.json()
                if session['state'].get('model_ref', None) == model_ref
            ]

    async def create_session(self, app_name: str, session_id: str, state: dict[str, Any]):
        async with self.client as client:
            response = await client.post(f"/apps/{app_name}/users/{self.USER_ID}/sessions/{session_id}", json=state)
            if not response.is_success:
                response.raise_for_status()

    async def delete_session(self, app_name: str, session_id: str):
        async with self.client as client:
            response = await client.delete(f"/apps/{app_name}/users/{self.USER_ID}/sessions/{session_id}")
            if not response.is_success:
                response.raise_for_status()

    async def run(self, request: RunAgentRequest):
        async with self.client as client:
            response = await client.post('/run', json=request.model_dump())
            if not response.is_success:
                response.raise_for_status()

    async def get_session_state(self, app_name: str, session_id: str) -> dict:
        async with self.client as client:
            response = await client.get(f'/apps/{app_name}/users/{self.USER_ID}/sessions/{session_id}')
            if response.status_code != status.HTTP_200_OK:
                response.raise_for_status()
            return response.json()['state']

