from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth_schemas import (
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.auth_service import (
    authenticate_user,
    create_user,
    get_user_by_id,
)
from app.security import create_access_token, decode_access_token


router = APIRouter(prefix="/auth", tags=["Auth"])
bearer_scheme = HTTPBearer(auto_error=False)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(payload: UserCreate) -> dict:
    return await create_user(payload)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> dict:
    user = await authenticate_user(payload.email, payload.password)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Adresse e-mail ou mot de passe incorrect.",
        )

    access_token = create_access_token(str(user["id"]))

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise.",
        )

    try:
        payload = decode_access_token(credentials.credentials)
        subject = payload.get("sub")

        if not subject:
            raise ValueError("JWT sans sujet.")

        user_id = UUID(subject)

    except (jwt.PyJWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton invalide ou expiré.",
        )

    user = await get_user_by_id(user_id)

    if user is None or not user["active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable ou désactivé.",
        )

    return user


@router.get("/me", response_model=UserResponse)
async def me(user: dict = Depends(current_user)) -> dict:
    return user
