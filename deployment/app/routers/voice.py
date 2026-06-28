from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import whisper
import elevenlabs
import io
import numpy as np
import os
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class STTRequest(BaseModel):
    audio_data: str  # base64 encoded audio

class STTResponse(BaseModel):
    text: str
    language: str

class TTSRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None

# Initialize Whisper model
whisper_model = None
elevenlabs_client = None

def get_whisper_model():
    global whisper_model
    if whisper_model is None:
        model_size = os.getenv("WHISPER_MODEL", "base")
        logger.info(f"Loading Whisper model: {model_size}")
        whisper_model = whisper.load_model(model_size)
    return whisper_model

def get_elevenlabs_client():
    global elevenlabs_client
    if elevenlabs_client is None:
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="ELEVENLABS_API_KEY not configured")
        elevenlabs.set_api_key(api_key)
        elevenlabs_client = elevenlabs
    return elevenlabs_client

@router.post("/stt", response_model=STTResponse)
async def speech_to_text(file: UploadFile = File(...)):
    """Convert speech to text using Whisper"""
    try:
        # Read audio file
        audio_data = await file.read()
        
        # Load audio with Whisper
        model = get_whisper_model()
        
        # Save to temp file for Whisper
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            temp_file.write(audio_data)
            temp_path = temp_file.name
        
        try:
            # Transcribe
            result = model.transcribe(temp_path)
            return STTResponse(
                text=result["text"],
                language=result.get("language", "en")
            )
        finally:
            os.unlink(temp_path)
            
    except Exception as e:
        logger.error(f"STT error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Speech-to-text error: {str(e)}")

@router.post("/tts")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech using ElevenLabs"""
    try:
        client = get_elevenlabs_client()
        voice_id = request.voice_id or os.getenv("TTS_VOICE_ID")
        
        if not voice_id:
            # Get default voice
            voices = client.voices()
            if voices:
                voice_id = voices[0].voice_id
            else:
                raise HTTPException(status_code=500, detail="No voice available")
        
        # Generate speech
        audio = client.generate(
            text=request.text,
            voice=voice_id,
            model="eleven_multilingual_v2"
        )
        
        # Convert to bytes
        audio_bytes = b''.join(audio)
        
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg"
        )
        
    except Exception as e:
        logger.error(f"TTS error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Text-to-speech error: {str(e)}")

@router.get("/voices")
async def list_voices():
    """List available ElevenLabs voices"""
    try:
        client = get_elevenlabs_client()
        voices = client.voices()
        
        return {
            "voices": [
                {
                    "voice_id": voice.voice_id,
                    "name": voice.name,
                    "category": voice.category,
                    "labels": voice.labels
                }
                for voice in voices
            ]
        }
    except Exception as e:
        logger.error(f"List voices error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing voices: {str(e)}")
