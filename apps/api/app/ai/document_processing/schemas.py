from pydantic import BaseModel, Field


class PdfExtractionResult(BaseModel):
    text: str
    page_count: int = Field(ge=0)
    character_count: int = Field(ge=0)
    requires_ocr: bool


class ExtractedTextUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=500_000)
