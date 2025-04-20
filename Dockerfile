FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ffmpeg \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user first
RUN useradd -m appuser

# Copy project (including cookies early)
COPY . /app/

# Create folders and fix permissions
RUN mkdir -p /app/downloads /app/staticfiles /app/cookies \
    && chmod 644 /app/cookies/youtube.com_cookies.txt || true \
    && chmod 644 /app/cookies/instagram.com_cookies.txt || true \
    && chown -R appuser:appuser /app

# Install Python deps
RUN pip install --no-cache-dir -r /app/requirements.txt

# Switch to non-root user
USER appuser
