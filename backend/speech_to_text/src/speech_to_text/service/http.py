import logging
from fastapi import APIRouter, UploadFile, File, HTTPException

from ..config import settings
from ..utils.whisper_engine import WhisperEngine

logger = logging.getLogger(settings.SERVICE_NAME + ".http")
router = APIRouter()


@router.post("/v1/transcribe")
async def transcribe(file: UploadFile = File(...), language: str | None = None):
    """Transcribe a full audio file and return the result."""
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty file")
    engine = WhisperEngine(config=settings)
    result = await engine.transcribe_file_bytes(audio_bytes, language)
    if not result:
        raise HTTPException(status_code=500, detail="Transcription failed")
    return result
