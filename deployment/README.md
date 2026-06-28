# DeepSeek-V3 Deployment

Complete deployment solution for DeepSeek-V3 with voice integration, agentic capabilities, and code editing features.

## Features

- **Model Serving**: vLLM-based serving for DeepSeek-V3 with tensor parallelism
- **Voice Integration**: Speech-to-text (Whisper) and text-to-speech (ElevenLabs)
- **Agentic Capabilities**: Tool-calling agent with built-in tools
- **Code Editor**: AI-powered code editing, review, and generation
- **REST API**: FastAPI-based API for all functionalities
- **Web Interface**: React-based frontend for interaction

## Prerequisites

- NVIDIA GPU with at least 4 GPUs for tensor parallelism (or 1 GPU with reduced parallelism)
- Docker and Docker Compose
- Python 3.10+
- API Keys:
  - ElevenLabs API key (for TTS)
  - OpenAI API key (optional, for additional features)

## Quick Start

### 1. Clone and Setup

```bash
cd e:\deepseek\DeepSeek-V3\deployment
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

### 3. Deploy with Docker Compose

```bash
docker-compose up -d
```

### 4. Access the Application

- API: http://localhost:8000
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs

## Manual Deployment (Local)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start vLLM Server

```bash
# In one terminal
python start_vllm.py
```

### 3. Start API Server

```bash
# In another terminal
python main.py
```

## API Endpoints

### Health
- `GET /health` - Health check

### Chat
- `POST /api/chat/completions` - Chat completion
- `POST /api/chat/stream` - Streaming chat

### Voice
- `POST /api/voice/stt` - Speech to text
- `POST /api/voice/tts` - Text to speech
- `GET /api/voice/voices` - List available voices

### Agent
- `POST /api/agent/execute` - Execute agent task
- `GET /api/agent/tools` - List available tools

### Code
- `POST /api/code/edit` - Edit code
- `POST /api/code/review` - Review code
- `POST /api/code/generate` - Generate code

## Cloud Deployment

### AWS

1. Launch EC2 instances with GPU (e.g., p3.8xlarge)
2. Install Docker and NVIDIA drivers
3. Deploy using Docker Compose
4. Configure security groups for ports 8000, 8001, 3000

### Google Cloud Platform

1. Create GPU VM instance (e.g., n1-standard-4 with V100)
2. Install Docker and NVIDIA drivers
3. Deploy using Docker Compose
4. Configure firewall rules

### Azure

1. Create GPU VM (e.g., Standard_NC6s_v3)
2. Install Docker and NVIDIA drivers
3. Deploy using Docker Compose
4. Configure network security groups

## Configuration

### Model Configuration
- `MODEL_NAME`: Hugging Face model path
- `TENSOR_PARALLEL_SIZE`: Number of GPUs for tensor parallelism
- `MAX_MODEL_LEN`: Maximum context length
- `GPU_MEMORY_UTILIZATION`: GPU memory utilization (0-1)

### Voice Configuration
- `WHISPER_MODEL`: Whisper model size (tiny, base, small, medium, large)
- `TTS_VOICE_ID`: ElevenLabs voice ID
- `ELEVENLABS_API_KEY`: ElevenLabs API key

### Agent Configuration
- `MAX_ITERATIONS`: Maximum agent iterations
- `TIMEOUT`: Agent timeout in seconds

## Hardware Requirements

### Minimum (Single GPU)
- 1x NVIDIA GPU with 24GB VRAM
- 32GB RAM
- 100GB SSD storage

### Recommended (Multi-GPU)
- 4x NVIDIA GPUs (A100/H100) with 40GB+ VRAM each
- 128GB RAM
- 500GB NVMe storage

## Troubleshooting

### vLLM Server Not Starting
- Check GPU availability: `nvidia-smi`
- Verify tensor parallel size matches GPU count
- Check logs: `docker logs deepseek-vllm`

### Out of Memory
- Reduce `MAX_MODEL_LEN`
- Reduce `GPU_MEMORY_UTILIZATION`
- Increase tensor parallel size

### Voice Features Not Working
- Verify API keys are set
- Check ElevenLabs API quota
- Test with smaller audio files

## License

This deployment code is MIT licensed. The DeepSeek-V3 model is subject to the Model License.
