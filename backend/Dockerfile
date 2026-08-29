FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend source code
COPY . /app/backend/

# Set working directory to the backend folder
WORKDIR /app/backend

# Expose port (Railway injects PORT env variable)
EXPOSE 8000

# Run uvicorn server with worker threads optimization or start as jobs worker
CMD ["sh", "-c", "if [ \"$SERVICE_TYPE\" = \"worker\" ]; then python -m src.jobs_worker; else uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${UVICORN_WORKERS:-2}; fi"]
