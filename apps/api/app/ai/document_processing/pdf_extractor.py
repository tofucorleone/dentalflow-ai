from pathlib import Path

from pypdf import PdfReader

from app.ai.document_processing.schemas import PdfExtractionResult


class PdfExtractionError(Exception):
    """Erreur lors de l'extraction du texte d'un PDF."""


def extract_pdf_text(file_path: Path) -> PdfExtractionResult:
    if not file_path.exists():
        raise PdfExtractionError("Le fichier PDF est introuvable.")

    try:
        reader = PdfReader(str(file_path))
    except Exception as exc:
        raise PdfExtractionError(
            "Impossible de lire le fichier PDF.",
        ) from exc

    pages_text: list[str] = []

    for page in reader.pages:
        text = page.extract_text() or ""
        cleaned_text = text.strip()

        if cleaned_text:
            pages_text.append(cleaned_text)

    extracted_text = "\n\n".join(pages_text)

    return PdfExtractionResult(
        text=extracted_text,
        page_count=len(reader.pages),
        character_count=len(extracted_text),
        requires_ocr=len(extracted_text.strip()) == 0,
    )
