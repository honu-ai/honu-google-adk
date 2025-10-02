from dataclasses import dataclass

import jwt
import structlog
from httpx import Client, Response


class ModelTasksAPIClientException(Exception):

    def __init__(self, response: Response):
        self.content = response.text
        self.response_code = response.status_code
        self.url = response.url

    def __str__(self):
        return f'ModelTasksAPIClient received response {self.response_code} for URL {self.url}.\nResponse content:\n{self.content}'


class ModelTasksAPIClient:
    def __init__(self, auth_token: str, model_ref: str):
        self.auth_token = auth_token
        self.model_ref = model_ref
        self.logger = structlog.get_logger('honu_google_adk.model_tasks_api_client')

    @property
    def client(self):
        return Client(
            base_url=self.url,
            headers=self.auth_header,
            timeout=300,
            verify=False,
        )
    
    @property
    def url(self) -> str:
        return jwt.decode(
            self.auth_token, 
            options={'verify_signature': False},
        ).get('url', '').rstrip('/').replace('localhost', 'host.docker.internal')

    @property
    def auth_header(self):
        return {"Authorization": f"Bearer {self.auth_token}"}

    def delete_all_my_tasks(self):
        """
        List all tasks in a given model
        """
        _, domain_id, model_id = self.model_ref.split('|')
        response = self.client.get(
            f'/v1/domains/{domain_id}/models/{model_id}/scheduling',
        )
        if not response.is_success:
            raise ModelTasksAPIClientException(response)
        for task in response.json():
            task_id = task['id']
            response = self.client.delete(
                f'/v1/domains/{domain_id}/models/{model_id}/scheduling/{task_id}',
            )
            if not response.is_success:
                # We'll just be trying to delete all tasks, some will fail and some will succeed
                pass
