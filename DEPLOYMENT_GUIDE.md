# DeepSeek-V3 Complete Deployment Guide

This guide covers deploying DeepSeek-V3 with voice integration, agentic capabilities, and code editing features both in the cloud and on your local laptop.

## Architecture Overview

```
┌─────────────────┐
│   Frontend      │  React + Vite + Tailwind
│   (Port 3000)   │  - Chat Interface
│                 │  - Voice Interface
│                 │  - Code Editor
│                 │  - Agent Panel
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   FastAPI       │  Python + Uvicorn
│   (Port 8000)   │  - Chat API
│                 │  - Voice API (STT/TTS)
│                 │  - Agent API
│                 │  - Code API
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   vLLM Server  │  Model Serving
│   (Port 8001)   │  - DeepSeek-V3
│                 │  - Tensor Parallelism
│                 │  - OpenAI Compatible
└─────────────────┘
```

## Prerequisites

### Hardware Requirements

**For Cloud Deployment (Recommended):**
- 4x NVIDIA GPUs (A100 40GB or H100 80GB recommended)
- 128GB RAM
- 500GB NVMe SSD storage
- Linux OS (Ubuntu 22.04 recommended)

**For Local Testing (Minimum):**
- 1x NVIDIA GPU with 24GB VRAM (RTX 3090/4090 or better)
- 32GB RAM
- 100GB SSD storage
- Windows 10/11 or Linux

### Software Requirements

- Docker & Docker Compose
- NVIDIA Docker Runtime
- Python 3.10+
- Node.js 20+
- Git

## Step 1: Cloud Deployment

### Option A: AWS Deployment

1. **Launch EC2 Instance**
   ```bash
   # Use p3.8xlarge (4x V100) or p4d.24xlarge (8x A100)
   # AMI: Deep Learning AMI (Ubuntu 22.04)
   # Security Group: Allow ports 22, 8000, 8001, 3000
   ```

2. **Connect to Instance**
   ```bash
   ssh -i your-key.pem ubuntu@your-instance-ip
   ```

3. **Install Docker and NVIDIA Runtime**
   ```bash
   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   
   # Install NVIDIA Container Toolkit
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
   curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
   sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   ```

4. **Clone Repository**
   ```bash
   git clone https://github.com/deepseek-ai/DeepSeek-V3.git
   cd DeepSeek-V3/deployment
   ```

5. **Configure Environment**
   ```bash
   cp .env.example .env
   nano .env
   # Add your API keys
   ```

6. **Deploy with Docker Compose**
   ```bash
   docker-compose up -d
   ```

7. **Access the Application**
   - Frontend: `http://your-instance-ip:3000`
   - API: `http://your-instance-ip:8000`
   - API Docs: `http://your-instance-ip:8000/docs`

### Option B: Google Cloud Platform

1. **Create GPU VM**
   ```bash
   gcloud compute instances create deepseek-v3 \
     --machine-type=a2-highgpu-4g \
     --accelerator=type=nvidia-tesla-a100,count=4 \
     --image-family=pytorch-latest-gpu \
     --image-project=deeplearning-platform-release \
     --maintenance-policy=TERMINATE \
     --boot-disk-size=500GB \
     --boot-disk-type=pd-ssd
   ```

2. **SSH and Install Docker**
   ```bash
   gcloud compute ssh deepseek-v3
   # Follow same Docker installation steps as AWS
   ```

3. **Deploy**
   ```bash
   git clone https://github.com/deepseek-ai/DeepSeek-V3.git
   cd DeepSeek-V3/deployment
   docker-compose up -d
   ```

### Option C: Azure

1. **Create GPU VM**
   - Use Standard_NC24ads_A100_v4 (4x A100)
   - Ubuntu 22.04 base image

2. **Install NVIDIA Drivers and Docker**
   ```bash
   wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
   sudo dpkg -i cuda-keyring_1.1-1_all.deb
   sudo apt-get update
   sudo apt-get install -y cuda-toolkit-12-1 nvidia-driver-535
   # Install Docker as above
   ```

3. **Deploy**
   ```bash
   git clone https://github.com/deepseek-ai/DeepSeek-V3.git
   cd DeepSeek-V3/deployment
   docker-compose up -d
   ```

## Step 2: Local Laptop Setup (Windows)

### 1. Install Prerequisites

```powershell
# Install Docker Desktop for Windows with WSL2
# Download from: https://www.docker.com/products/docker-desktop

# Install Python 3.10
# Download from: https://www.python.org/downloads/

# Install Node.js 20
# Download from: https://nodejs.org/

# Install Git
# Download from: https://git-scm.com/download/win
```

### 2. Clone Repository

```powershell
cd e:\deepseek
git clone https://github.com/deepseek-ai/DeepSeek-V3.git
```

### 3. Setup Backend

```powershell
cd DeepSeek-V3\deployment

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env with your settings
```

### 4. Setup Frontend

```powershell
cd e:\deepseek\frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### 5. Start Services

```powershell
# Terminal 1: Start vLLM server
cd e:\deepseek\DeepSeek-V3\deployment
.\venv\Scripts\activate
python start_vllm.py

# Terminal 2: Start FastAPI server
cd e:\deepseek\DeepSeek-V3\deployment
.\venv\Scripts\activate
python main.py

# Terminal 3: Start frontend (already running)
# Frontend at http://localhost:3000
```

## Step 3: API Keys Configuration

### ElevenLabs (for Text-to-Speech)

1. Sign up at https://elevenlabs.io
2. Get API key from https://elevenlabs.io/app/settings/api-keys
3. Add to `.env`:
   ```
   ELEVENLABS_API_KEY=your_key_here
   TTS_VOICE_ID=your_voice_id_here
   ```

### OpenAI (Optional)

1. Sign up at https://platform.openai.com
2. Get API key from https://platform.openai.com/api-keys
3. Add to `.env`:
   ```
   OPENAI_API_KEY=your_key_here
   ```

## Step 4: Model Configuration

### For Multi-GPU Setup (Cloud)

Edit `.env`:
```env
MODEL_NAME=deepseek-ai/DeepSeek-V3
TENSOR_PARALLEL_SIZE=4
MAX_MODEL_LEN=8192
GPU_MEMORY_UTILIZATION=0.9
```

### For Single GPU Setup (Local)

Edit `.env`:
```env
MODEL_NAME=deepseek-ai/DeepSeek-V3
TENSOR_PARALLEL_SIZE=1
MAX_MODEL_LEN=4096
GPU_MEMORY_UTILIZATION=0.8
```

## Step 5: Testing the Deployment

### 1. Health Check

```bash
curl http://localhost:8000/health
```

### 2. Test Chat API

```bash
curl -X POST http://localhost:8000/api/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "temperature": 0.7,
    "max_tokens": 100
  }'
```

### 3. Test Voice API

```bash
# Speech to Text
curl -X POST http://localhost:8000/api/voice/stt \
  -F "file=@audio.wav"

# Text to Speech
curl -X POST http://localhost:8000/api/voice/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, world!"}'
```

### 4. Test Agent API

```bash
curl -X POST http://localhost:8000/api/agent/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Search for information about AI",
    "max_iterations": 5
  }'
```

### 5. Test Code API

```bash
curl -X POST http://localhost:8000/api/code/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Create a function to calculate fibonacci",
    "language": "python"
  }'
```

## Step 6: Running on Laptop (Local Mode)

### Option A: Full Local Stack

Run all services locally on your laptop with GPU:

```powershell
# Requires NVIDIA GPU with CUDA support
# Follow Step 2 above
```

### Option B: Cloud Backend + Local Frontend

Run the model in the cloud, but use the frontend locally:

1. Deploy backend to cloud (Step 1)
2. Update frontend settings:
   - API URL: `http://your-cloud-ip:8000`
3. Run frontend locally:
   ```powershell
   cd e:\deepseek\frontend
   npm run dev
   ```

### Option C: Hybrid Mode

Run vLLM in cloud, API locally, frontend locally:

1. Deploy only vLLM to cloud
2. Run FastAPI locally, pointing to cloud vLLM
3. Run frontend locally

## Troubleshooting

### vLLM Server Issues

**Problem**: Out of memory
```bash
# Solution: Reduce MAX_MODEL_LEN or GPU_MEMORY_UTILIZATION
# In .env:
MAX_MODEL_LEN=4096
GPU_MEMORY_UTILIZATION=0.7
```

**Problem**: Slow inference
```bash
# Solution: Increase tensor parallelism if you have more GPUs
TENSOR_PARALLEL_SIZE=4
```

### Voice Issues

**Problem**: Whisper model not loading
```bash
# Solution: Use smaller model
WHISPER_MODEL=tiny
```

**Problem**: ElevenLabs API error
```bash
# Solution: Check API key and quota
# Verify ELEVENLABS_API_KEY in .env
```

### Frontend Issues

**Problem**: Cannot connect to API
```bash
# Solution: Check CORS settings in main.py
# Ensure API URL is correct in settings
```

### Docker Issues

**Problem**: GPU not accessible in container
```bash
# Solution: Verify NVIDIA Docker Runtime
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

## Performance Optimization

### vLLM Optimization

```env
# Enable FP8 for faster inference (if supported)
VLLM_USE_FP8=true

# Enable KV cache
VLLM_ENABLE_KV_CACHE=true

# Increase batch size for throughput
VLLM_MAX_BATCH_SIZE=32
```

### Network Optimization

```bash
# Use high-performance network for multi-node
# Configure MTU for better throughput
```

### Caching

```bash
# Use Redis for response caching
# Already included in docker-compose.yml
```

## Security Considerations

1. **API Keys**: Never commit `.env` file
2. **Firewall**: Restrict access to ports 8000, 8001, 3000
3. **Authentication**: Add API authentication for production
4. **HTTPS**: Use reverse proxy with SSL for production
5. **Rate Limiting**: Implement rate limiting on API endpoints

## Monitoring

### Health Checks

```bash
# Check all services
curl http://localhost:8000/health
docker ps
docker logs deepseek-vllm
```

### Logs

```bash
# View logs
docker logs -f deepseek-vllm
docker logs -f deepseek-frontend
```

### Metrics

Consider adding Prometheus + Grafana for production monitoring.

## Cost Estimation

### Cloud Costs (Approximate)

**AWS p3.8xlarge**: ~$31/hour
- 4x V100 GPUs
- 122 GB RAM
- Suitable for development/testing

**AWS p4d.24xlarge**: ~$32/hour
- 8x A100 GPUs
- 512 GB RAM
- Suitable for production

**Monthly Estimate**: $22,000 - $24,000 for 24/7 operation

### Cost Optimization

1. Use spot instances for development
2. Auto-scale based on demand
3. Use smaller models for testing
4. Cache frequently used responses

## Next Steps

1. **Deploy to Cloud**: Follow Step 1 for your preferred cloud provider
2. **Setup Local Access**: Configure your laptop to connect to cloud instance
3. **Customize**: Modify the frontend and backend to your needs
4. **Scale**: Add more GPUs or instances as needed
5. **Monitor**: Set up monitoring and alerting

## Support

- DeepSeek-V3 GitHub: https://github.com/deepseek-ai/DeepSeek-V3
- vLLM Documentation: https://docs.vllm.ai
- FastAPI Documentation: https://fastapi.tiangolo.com
- Issues: https://github.com/deepseek-ai/DeepSeek-V3/issues
