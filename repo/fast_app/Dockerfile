# ─────────────────────────────────────────────────────────────────────────────
# SAP SOC Log Ingestion API — Dockerfile
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

# Don't write .pyc files; stream logs straight to stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies first (layer-cached until requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# The output/ dir (logs.csv, access_logs.csv) and api_keys.json are mounted
# at runtime via docker-compose volumes — do NOT bake them into the image.

EXPOSE 8000

# Use 2 workers; for a hackathon 1 is fine too. --no-access-log keeps stdout clean
# since we write our own access log to CSV.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1"]
