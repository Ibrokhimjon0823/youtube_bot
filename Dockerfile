FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
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

# Create directories for media
RUN mkdir -p /app/downloads
RUN mkdir -p /app/staticfiles

# Copy project
COPY . /app/

# Set proper permissions BEFORE switching to non-root user
RUN chmod -R 777 /app/cookies
RUN chmod -R 777 /app/cookies/youtube.com_cookies.txt

# Run as non-root user (for security)
RUN useradd -m appuser
RUN chown -R appuser:appuser /app
USER appuser