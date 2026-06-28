import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
from dotenv import load_dotenv
import logging

from app.routers import chat, voice, agent, code, health

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting DeepSeek-V3 deployment...")
    logger.info(f"Model: {os.getenv('MODEL_NAME', 'deepseek-ai/DeepSeek-V3')}")
    logger.info(f"Tensor Parallel Size: {os.getenv('TENSOR_PARALLEL_SIZE', '4')}")
    yield
    # Shutdown
    logger.info("Shutting down DeepSeek-V3 deployment...")

# Create FastAPI app
app = FastAPI(
    title="DeepSeek-V3 AI Assistant",
    description="AI assistant with voice, agentic, and code editing capabilities",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(voice.router, prefix="/api/voice", tags=["Voice"])
app.include_router(agent.router, prefix="/api/agent", tags=["Agent"])
app.include_router(code.router, prefix="/api/code", tags=["Code"])

@app.get("/")
async def root():
    return {
        "message": "DeepSeek-V3 AI Assistant",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "chat": "/api/chat",
            "voice": "/api/voice",
            "agent": "/api/agent",
            "code": "/api/code"
        }
    }

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
