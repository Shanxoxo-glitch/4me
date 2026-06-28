from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import httpx
import os

router = APIRouter()

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2000
    stream: Optional[bool] = False

class ChatResponse(BaseModel):
    content: str
    model: str
    usage: Dict[str, int]

# vLLM server URL
VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8001")

@router.post("/completions", response_model=ChatResponse)
async def chat_completion(request: ChatRequest):
    """Generate chat completion using DeepSeek-V3 via vLLM"""
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{VLLM_URL}/v1/chat/completions",
                json={
                    "model": os.getenv("MODEL_NAME", "deepseek-ai/DeepSeek-V3"),
                    "messages": [msg.dict() for msg in request.messages],
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "stream": False
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return ChatResponse(
                content=data["choices"][0]["message"]["content"],
                model=data["model"],
                usage=data.get("usage", {})
            )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"vLLM server error: {str(e)}")

@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat completion using DeepSeek-V3 via vLLM"""
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{VLLM_URL}/v1/chat/completions",
                json={
                    "model": os.getenv("MODEL_NAME", "deepseek-ai/DeepSeek-V3"),
                    "messages": [msg.dict() for msg in request.messages],
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "stream": True
                }
            ) as response:
                response.raise_for_status()
                
                async def generate():
                    async for chunk in response.aiter_bytes():
                        yield chunk
                
                return StreamingResponse(
                    generate(),
                    media_type="text/event-stream"
                )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"vLLM server error: {str(e)}")
