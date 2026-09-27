import logging
import httpx
import urllib3
from typing import List, Dict, Any

from app.config import settings


# Disable insecure HTTPS warnings if self-signed certificates are used
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class ArgoCDClient:
    def __init__(self):
        self.server_url = settings.argocd_server.rstrip("/")
        self.token = settings.argocd_token
        self.verify_ssl = settings.argocd_verify_ssl
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    async def get_application(self, app_name: str) -> Dict[str, Any]:
        """Fetch full details of an ArgoCD Application asynchronously."""
        url = f"{self.server_url}/api/v1/applications/{app_name}"
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def is_managed_by_argocd(self, app_name: str) -> bool:
        """Check if an application exists and is managed by ArgoCD asynchronously."""
        try:
            await self.get_application(app_name)
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False
            raise

    async def list_applications(self) -> List[Dict[str, Any]]:
        """Fetch a list of all ArgoCD Applications asynchronously."""
        url = f"{self.server_url}/api/v1/applications"
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return data.get("items", [])

argocd_client=ArgoCDClient()