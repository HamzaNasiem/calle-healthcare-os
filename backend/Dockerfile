FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PORT=8000 \
    ENCRYPTION_MODE=local \
    ENCRYPTION_KEY=hYggyNW+JO9cGaCKHoMMRrQsvnYFIUIYg+P08iF1UKA=

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY . .

# Expose default port
EXPOSE 8000

# Start FastAPI server
CMD ["sh", "-c", "python -m uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
