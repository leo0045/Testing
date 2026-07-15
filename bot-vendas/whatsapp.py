"""Cliente para envio de mensagens de WhatsApp via Evolution API.

Referência do endpoint (Evolution API v2):
    POST {base_url}/message/sendText/{instance}
    headers: {"apikey": "<API_KEY>"}
    body:    {"number": "<destino>", "text": "<mensagem>"}

Quando ``dry_run`` está ativo, nenhuma requisição de rede é feita: a mensagem é
apenas registrada em log. Isso permite testar o fluxo completo sem uma
instância real da Evolution API.
"""
from __future__ import annotations

import logging

import requests


class WhatsAppClient:
    def __init__(
        self,
        base_url: str,
        instance: str,
        api_key: str,
        recipient: str,
        dry_run: bool = False,
        timeout: int = 10,
        logger: logging.Logger | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.instance = instance
        self.api_key = api_key
        self.recipient = recipient
        self.dry_run = dry_run
        self.timeout = timeout
        self.logger = logger or logging.getLogger("bot_vendas")

    def send(self, text: str, recipient: str | None = None) -> bool:
        """Envia uma mensagem de texto. Retorna True em caso de sucesso."""
        number = recipient or self.recipient

        if self.dry_run:
            self.logger.info("[DRY-RUN] WhatsApp -> %s: %s", number, text)
            return True

        url = f"{self.base_url}/message/sendText/{self.instance}"
        headers = {"apikey": self.api_key, "Content-Type": "application/json"}
        payload = {"number": number, "text": text}

        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=self.timeout
            )
        except requests.RequestException as exc:
            self.logger.error("Falha de rede ao enviar mensagem: %s", exc)
            return False

        if response.status_code >= 400:
            self.logger.error(
                "Evolution API retornou %s: %s",
                response.status_code,
                response.text[:500],
            )
            return False

        self.logger.info(
            "Mensagem enviada para %s (HTTP %s)", number, response.status_code
        )
        return True
