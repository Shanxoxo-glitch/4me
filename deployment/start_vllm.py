#!/usr/bin/env python3
"""
vLLM server startup script for DeepSeek-V3
"""
import os
import subprocess
import sys

def main():
    # Get environment variables
    model_name = os.getenv("MODEL_NAME", "deepseek-ai/DeepSeek-V3")
    tensor_parallel_size = int(os.getenv("TENSOR_PARALLEL_SIZE", "4"))
    max_model_len = int(os.getenv("MAX_MODEL_LEN", "8192"))
    gpu_memory_utilization = float(os.getenv("GPU_MEMORY_UTILIZATION", "0.9"))
    port = int(os.getenv("VLLM_PORT", "8001"))
    
    print(f"Starting vLLM server for {model_name}")
    print(f"Tensor Parallel Size: {tensor_parallel_size}")
    print(f"Max Model Length: {max_model_len}")
    print(f"GPU Memory Utilization: {gpu_memory_utilization}")
    print(f"Port: {port}")
    
    # vLLM server command
    cmd = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", model_name,
        "--tensor-parallel-size", str(tensor_parallel_size),
        "--max-model-len", str(max_model_len),
        "--gpu-memory-utilization", str(gpu_memory_utilization),
        "--port", str(port),
        "--host", "0.0.0.0",
        "--dtype", "auto",
        "--trust-remote-code"
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    
    # Start vLLM server
    subprocess.run(cmd)

if __name__ == "__main__":
    main()
