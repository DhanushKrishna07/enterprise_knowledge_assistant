#!/bin/bash
set -e

# Establish writeable directory for Ollama models on Hugging Face Spaces (runs as non-root)
export HOME=/tmp
export OLLAMA_MODELS=/tmp/ollama/models
mkdir -p /tmp/ollama/models

echo "Starting Ollama server in background..."
ollama serve > /tmp/ollama.log 2>&1 &

# Wait for Ollama service to boot up
echo "Waiting for Ollama to start..."
until curl -s http://127.0.0.1:11434/api/tags > /dev/null; do
    sleep 2
done
echo "Ollama started successfully."

# Retrieve model names from environment variables (fallback if not defined)
PRIMARY_MODEL="${LLM_MODEL:-qwen3:4b}"
FALLBACK_MODEL="${LLM_FALLBACK_MODEL:-qwen3:1.7b}"

# Pull required local LLM models
echo "Pulling primary model: ${PRIMARY_MODEL}..."
ollama pull "${PRIMARY_MODEL}"

echo "Pulling fallback model: ${FALLBACK_MODEL}..."
ollama pull "${FALLBACK_MODEL}"

# Start FastAPI application on Port 7860 (Hugging Face requirement)
echo "Starting FastAPI App..."
exec uvicorn app.api.main:app --host 0.0.0.0 --port 7860
