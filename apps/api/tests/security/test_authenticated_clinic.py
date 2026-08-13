import asyncio
from uuid import uuid4

from fastapi import HTTPException


def test_authenticated_clinic_accepts_user_clinic():
    from app.deps import authenticated_clinic_id

    user_clinic_id = uuid4()
    user = {
        "id": uuid4(),
        "clinic_id": user_clinic_id,
        "role": "staff",
        "active": True,
    }

    result = asyncio.run(
        authenticated_clinic_id(
            x_clinic_id=str(user_clinic_id),
            user=user,
        )
    )

    assert result == user_clinic_id


def test_authenticated_clinic_rejects_other_clinic():
    from app.deps import authenticated_clinic_id

    user = {
        "id": uuid4(),
        "clinic_id": uuid4(),
        "role": "staff",
        "active": True,
    }

    try:
        asyncio.run(
            authenticated_clinic_id(
                x_clinic_id=str(uuid4()),
                user=user,
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == "Accès interdit à cette clinique."
    else:
        raise AssertionError("Une HTTPException 403 était attendue.")
