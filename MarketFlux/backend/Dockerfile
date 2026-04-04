# MarketFlux Backend - FastAPI
FROM python:3.11-slim

WORKDIR /app

# Install system deps (certifi for MongoDB TLS)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default port
EXPOSE 8001

# Run with uvicorn (PORT from Render/Railway, default 8001)
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8001}"]
