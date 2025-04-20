FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ffmpeg \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project (including cookies)
COPY . /app/

# Fix permissions for directories
RUN mkdir -p /app/downloads /app/staticfiles /app/cookies \
    && chown -R appuser:appuser /app \
    && chmod 644 /app/cookies/youtube.com_cookies.txt \
    && chmod 644 /app/cookies/instagram.com_cookies.txt


# Create non-root user
RUN useradd -m appuser
USER appuser

# Entrypoint/command will be set in docker-compose
