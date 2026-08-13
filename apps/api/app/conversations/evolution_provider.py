import os
from typing import Any

import httpx


class EvolutionConfigurationError(RuntimeError):
    """Configuration Evolution absente ou invalide."""


class EvolutionSendError(RuntimeError):
    """Échec de l'envoi d'un message via Evolution API."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


def normalize_whatsapp_number(
    sender_phone: str,
) -> str:
    number = "".join(
        character
        for character in sender_phone
        if character.isdigit()
    )

    if not number:
        raise ValueError(
            "Le numéro WhatsApp est invalide."
        )

    return number


def required_environment(
    name: str,
) -> str:
    value = os.getenv(name, "").strip()

    if not value:
        raise EvolutionConfigurationError(
            f"La variable {name} est absente."
        )

    return value


def extract_evolution_message_id(
    payload: Any,
) -> str | None:
    if not isinstance(payload, dict):
        return None

    for key in (
        "messageId",
        "message_id",
        "id",
    ):
        value = payload.get(key)

        if value is not None:
            normalized = str(value).strip()

            if normalized:
                return normalized

    key_payload = payload.get("key")

    if isinstance(key_payload, dict):
        value = key_payload.get("id")

        if value is not None:
            normalized = str(value).strip()

            if normalized:
                return normalized

    for nested_key in (
        "data",
        "message",
        "response",
    ):
        result = extract_evolution_message_id(
            payload.get(nested_key)
        )

        if result:
            return result

    return None


async def send_evolution_text_message(
    *,
    instance: str,
    sender_phone: str,
    text: str,
    client: httpx.AsyncClient | None = None,
) -> dict:
    normalized_instance = instance.strip()
    normalized_text = text.strip()

    if not normalized_instance:
        raise ValueError(
            "L'instance Evolution est obligatoire."
        )

    if not normalized_text:
        raise ValueError(
            "Le message WhatsApp est obligatoire."
        )

    base_url = required_environment(
        "EVOLUTION_API_URL"
    ).rstrip("/")

    api_key = required_environment(
        "EVOLUTION_API_KEY"
    )

    url = (
        f"{base_url}/message/sendText/"
        f"{normalized_instance}"
    )

    payload = {
        "number": normalize_whatsapp_number(
            sender_phone
        ),
        "text": normalized_text,
    }

    headers = {
        "apikey": api_key,
        "Content-Type": "application/json",
    }

    owns_client = client is None

    if client is None:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(20.0)
        )

    try:
        response = await client.post(
            url,
            headers=headers,
            json=payload,
        )
    except httpx.HTTPError as exc:
        raise EvolutionSendError(
            "Evolution API est inaccessible."
        ) from exc
    finally:
        if owns_client:
            await client.aclose()

    if response.is_error:
        raise EvolutionSendError(
            "Evolution API a refusé le message.",
            status_code=response.status_code,
            response_body=response.text[:2000],
        )

    try:
        response_payload = response.json()
    except ValueError:
        response_payload = {
            "raw_response": response.text[:2000],
        }

    return {
        "external_id": extract_evolution_message_id(
            response_payload
        ),
        "status_code": response.status_code,
        "response": response_payload,
    }


__all__ = [
    "EvolutionConfigurationError",
    "EvolutionSendError",
    "extract_evolution_message_id",
    "normalize_whatsapp_number",
    "required_environment",
    "send_evolution_text_message",
]
