# Multi-tenant RAG Backend Dockerfile
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HF_HOME=/tmp/huggingface

# Install system dependencies including Tesseract OCR for PDF scanning fallback
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definition and install packages (CPU-optimized PyTorch)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model so container cold starts are fast
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy backend application code
COPY app ./app

# Expose default port
EXPOSE 8000

# Start Uvicorn bound to dynamic PORT provided by host environment (e.g., Render / Railway)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
