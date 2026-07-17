from openai import APIError

from app.ai.llm.client import (
    LlmConfigurationError,
    get_openai_client,
)
from app.ai.prompts.document_summary import (
    DOCUMENT_SUMMARY_INSTRUCTIONS,
)


class DocumentSummaryError(RuntimeError):
    """Erreur pendant la génération du résumé documentaire."""


async def summarize_document(text: str) -> str:
    cleaned_text = text.strip()

    if not cleaned_text:
        raise DocumentSummaryError(
            "Le document ne contient aucun texte à résumer.",
        )

    client = get_openai_client()

    try:
        response = await client.responses.create(
            model="gpt-4.1-mini",
            instructions=DOCUMENT_SUMMARY_INSTRUCTIONS,
            input=cleaned_text,
            max_output_tokens=700,
        )
    except LlmConfigurationError:
        raise
    except APIError as exc:
        raise DocumentSummaryError(
            "Le service de résumé IA est momentanément indisponible.",
        ) from exc

    summary = response.output_text.strip()

    if not summary:
        raise DocumentSummaryError(
            "Le modèle n'a retourné aucun résumé.",
        )

    return summary
