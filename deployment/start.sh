#!/bin/bash

# Start vLLM server in background
echo "Starting vLLM server..."
python start_vllm.py &
VLLM_PID=$!

# Wait for vLLM to be ready
echo "Waiting for vLLM server to start..."
sleep 60

# Start FastAPI application
echo "Starting FastAPI application..."
python main.py
