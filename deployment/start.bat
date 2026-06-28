@echo off
REM Windows startup script

REM Start vLLM server in background
echo Starting vLLM server...
start /B python start_vllm.py

REM Wait for vLLM to be ready
echo Waiting for vLLM server to start...
timeout /t 60

REM Start FastAPI application
echo Starting FastAPI application...
python main.py
