# Build React frontend
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Backend and inference runtime
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    OLLAMA_BASE_URL=http://127.0.0.1:11434

WORKDIR /app

# Install system dependencies & Ollama CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    zstd \
    && curl -fsSL https://ollama.com/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY pyproject.toml .
COPY app/ ./app/
COPY scripts/ ./scripts/
RUN pip install --upgrade pip && pip install .

# Copy remaining application files
COPY . .
COPY --from=frontend-build /frontend/dist ./frontend/dist

# Set up runtime directories and permissions
RUN mkdir -p /app/data && chmod -R 777 /app/data
RUN chmod +x /app/start.sh

# Expose port 7860 for Hugging Face Spaces
EXPOSE 7860

# Run entrypoint script
CMD ["/bin/bash", "/app/start.sh"]
