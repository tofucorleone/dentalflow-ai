from fastapi import APIRouter, Depends

from app.ai.processor import process_conversation
from app.ai.schemas import (
    ConversationInput,
    ConversationRequest,
    ConversationResult,
)
from app.deps import clinic_id


router = APIRouter(
    prefix="/ai",
    tags=["IA conversationnelle"],
)


@router.post(
    "/conversation/test",
    response_model=ConversationResult,
)
async def test_conversation(
    payload: ConversationRequest,
    current_clinic=Depends(clinic_id),
) -> ConversationResult:
    conversation = ConversationInput(
        clinic_id=current_clinic,
        **payload.model_dump(),
    )

    return await process_conversation(conversation)
