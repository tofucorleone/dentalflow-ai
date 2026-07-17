from decimal import Decimal
from uuid import UUID

from app.ai.schemas import ConversationResult
from app.treatment_service import list_active_treatments


def format_price(value: Decimal) -> str:
    amount = f"{value:,.2f}".replace(",", " ").replace(".", ",")

    if amount.endswith(",00"):
        amount = amount[:-3]

    return f"{amount} DA"


async def handle_treatment_pricing(
    clinic_id: UUID,
    patient_id: UUID | None,
) -> ConversationResult:
    treatments = await list_active_treatments(clinic_id)

    if not treatments:
        return ConversationResult(
            intent="treatment_pricing",
            patient_id=patient_id,
            reply=(
                "Les tarifs des soins ne sont pas encore disponibles. "
                "Je peux vous mettre en relation avec le cabinet."
            ),
            requires_human=True,
        )

    lines = [
        f"• {treatment['name']} : {format_price(treatment['price'])}"
        for treatment in treatments
    ]

    reply = (
        "Voici les tarifs actuellement enregistrés :\n\n"
        + "\n".join(lines)
        + "\n\nCertains soins peuvent nécessiter une consultation préalable."
    )

    return ConversationResult(
        intent="treatment_pricing",
        patient_id=patient_id,
        reply=reply,
    )
