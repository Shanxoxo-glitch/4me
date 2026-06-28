# Quick Setup Instructions

## API Key Configured

Your ElevenLabs API key has been configured in `deployment.env`:
```
ELEVENLABS_API_KEY=sk_04a09721abb7f6bdfab32108c64a74def908a26419ad3064
```

## Local Deployment (Windows)

### Step 1: Copy Environment File
```powershell
cd e:\deepseek\DeepSeek-V3\deployment
copy ..\..\deployment.env .env
```

### Step 2: Install Python Dependencies
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3: Install Frontend Dependencies
```powershell
cd e:\deepseek\frontend
npm install
```

### Step 4: Start Services

**Terminal 1 - vLLM Server:**
```powershell
cd e:\deepseek\DeepSeek-V3\deployment
.\venv\Scripts\activate
python start_vllm.py
```

**Terminal 2 - FastAPI Server:**
```powershell
cd e:\deepseek\DeepSeek-V3\deployment
.\venv\Scripts\activate
python main.py
```

**Terminal 3 - Frontend:**
```powershell
cd e:\deepseek\frontend
npm run dev
```

### Step 5: Access the Application
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Docker Deployment

### Step 1: Copy Environment File
```powershell
cd e:\deepseek\DeepSeek-V3\deployment
copy ..\..\deployment.env .env
```

### Step 2: Deploy with Docker Compose
```powershell
docker-compose up -d
```

### Step 3: Access the Application
- Frontend: http://localhost:3000
- API: http://localhost:8000

## Cloud Deployment

For cloud deployment, copy the `deployment.env` file to your cloud instance and use it as `.env` in the deployment directory.

## Getting ElevenLabs Voice ID

To get a voice ID for text-to-speech:

1. Go to https://elevenlabs.io/app/voice-lab
2. Choose a voice or create a custom one
3. Copy the Voice ID from the URL or voice settings
4. Update `TTS_VOICE_ID` in your `.env` file

## Notes

- The ElevenLabs API key is already configured
- You may want to add an OpenAI API key for additional features
- For local deployment, ensure you have NVIDIA GPU with CUDA support
- For single GPU local setup, change `TENSOR_PARALLEL_SIZE=1` in .env
