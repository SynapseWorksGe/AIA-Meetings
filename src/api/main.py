"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.database import engine
from src.api.models.meeting import Base
from src.api.routes.auth import router as auth_router
from src.api.routes.meetings import router as meetings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (use Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="AIA-Meetings",
    description="Meeting transcription and summarization service",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(meetings_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    from src.api.config import settings

    uvicorn.run("src.api.main:app", host=settings.api_host, port=settings.api_port, reload=True)
