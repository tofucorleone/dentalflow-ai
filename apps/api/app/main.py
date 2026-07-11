from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core import router as core_router
from app.patient360 import router as patient360_router
from app.db import close_pool, connection, open_pool


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
