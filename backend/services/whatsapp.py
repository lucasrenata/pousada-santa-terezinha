import os
import aiohttp
import json
import base64
from typing import Optional, Dict, Any

class WhatsAppService:
    def __init__(self):
        self.api_key = os.getenv("EVOLUTION_API_KEY")
        self.base_url = os.getenv("EVOLUTION_BASE_URL", "").rstrip("/")
        self.instance = os.getenv("EVOLUTION_INSTANCE_NAME")

    @property
    def headers(self):
        return {
            "apikey": self.api_key,
            "Content-Type": "application/json"
        }

    async def _request(self, method: str, endpoint: str, json_data: dict = None) -> dict:
        if not self.base_url or not self.api_key or not self.instance:
            print("WhatsAppService ERRO: Variáveis de ambiente da Evolution API não configuradas.")
            return {}

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=self.headers, json=json_data) as response:
                    response.raise_for_status()
                    return await response.json()
        except Exception as e:
            print(f"WhatsAppService ERRO na requisição para {endpoint}: {e}")
            return {}

    async def send_text(self, number: str, text: str, delay: int = 1200):
        """Envia mensagem de texto via Evolution API."""
        endpoint = f"message/sendText/{self.instance}"
        payload = {
            "number": number,
            "text": text,
            "delay": delay
        }
        return await self._request("POST", endpoint, payload)

    async def send_image(self, number: str, base64_image: str, caption: str = "", delay: int = 1200):
        """Envia imagem via Evolution API."""
        endpoint = f"message/sendMedia/{self.instance}"
        payload = {
            "number": number,
            "mediatype": "image",
            "media": base64_image,
            "caption": caption,
            "delay": delay
        }
        return await self._request("POST", endpoint, payload)

    async def send_audio(self, number: str, base64_audio: str, default_to_ptt: bool = True, delay: int = 1200):
        """Envia áudio via Evolution API. default_to_ptt envia como gravado na hora."""
        endpoint = f"message/sendWhatsAppAudio/{self.instance}"
        # Evolution tem sendWhatsAppAudio
        payload = {
            "number": number,
            "audio": base64_audio,
            "delay": delay
        }
        # Se usar o sendMedia genérico:
        # payload = {"number": number, "mediatype": "audio", "media": base64_audio, "delay": delay}
        return await self._request("POST", endpoint, payload)

    async def download_media(self, message: Dict[str, Any]) -> Optional[bytes]:
        """Baixa mídia de uma mensagem através da Evolution API e retorna os bytes."""
        endpoint = f"chat/getBase64FromMediaMessage/{self.instance}"
        payload = {"message": message}
        
        response = await self._request("POST", endpoint, payload)
        
        if response and isinstance(response, dict) and "base64" in response:
            try:
                base64_data = response["base64"]
                # Evolution costuma retornar "data:image/jpeg;base64,..." ou direto o base64
                if "," in base64_data:
                    base64_data = base64_data.split(",")[1]
                return base64.b64decode(base64_data)
            except Exception as e:
                print(f"Erro ao decodificar base64 da mídia: {e}")
                return None
        return None
