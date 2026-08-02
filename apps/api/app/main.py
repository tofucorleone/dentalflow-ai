from contextlib import asynccontextmanager
from app.documents import router as documents_router
from app.ai.router import router as ai_router
from app.voice.router import router as voice_router
from app.voice.twilio_router import router as twilio_router
from fastapi import FastAPI
from app.document_ai import router as document_ai_router
from app.core import router as core_router
from app.patient360 import router as patient360_router
from app.db import close_pool, connection, open_pool
from app.auth import router as auth_router
from app.branding import router as branding_router

@asynccontextmanager
async def lifespan(_: FastAPI):
    await open_pool()
    yield
    await close_pool()


app = FastAPI(
    title="DentalFlow AI API",
    version="0.1.0",
    description=(
        "API multi-clinique cohérente pour soins, praticiens, patients, "
        "rendez-vous et disponibilités."
    ),
    lifespan=lifespan,
)


@app.get("/health", tags=["Système"])
async def health() -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1 AS ok")
            row = await cur.fetchone()
    return {"status": "ok", "database": row["ok"] == 1}


app.include_router(core_router)
app.include_router(patient360_router)
app.include_router(auth_router)
app.include_router(branding_router)
app.include_router(documents_router)
app.include_router(ai_router)
app.include_router(voice_router)
app.include_router(twilio_router)
app.include_router(document_ai_router)
