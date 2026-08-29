FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
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

# Start FastAPI server via Gunicorn with UvicornWorker
CMD ["sh", "-c", "gunicorn -w 1 -k uvicorn.workers.UvicornWorker src.main:app --bind 0.0.0.0:${PORT:-8000} --timeout 120"]
