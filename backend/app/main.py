from fastapi import FastAPI
from sqlalchemy import text

from app.database import SessionLocal

app = FastAPI(title="CRAG AI Backend", version="0.1.0")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
def startup_check() -> None:
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))

