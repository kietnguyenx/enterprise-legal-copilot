# ========================================================
# SecureDoc AI — Enterprise Containerization Dockerfile
# ========================================================
FROM python:3.11-slim

# Prevent Python from writing .pyc files & enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install minimal OS dependencies for health checking & networking
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and web assets
COPY src/ ./src/
COPY web/ ./web/
COPY data/ ./data/
COPY server.py .

# Create persistent data directory and set permissions
RUN mkdir -p /app/data

# Expose FastAPI Olympus port
EXPOSE 8000

# Health check against native /api/health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Launch FastAPI ASGI server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
