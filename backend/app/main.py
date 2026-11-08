from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.routers.auth import router as auth_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", debug=settings.debug)
app.include_router(auth_router)
DatabaseSession = Annotated[Session, Depends(get_db)]


@app.get("/")
def root():
    return {"name": settings.app_name, "docs": "/docs"}


@app.get("/health")
def health(db: DatabaseSession):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail={"status": "degraded", "database": "unavailable"},
        ) from None
    return {"status": "ok", "database": "ok"}
