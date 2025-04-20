FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# create the app user
RUN addgroup --system appuser && adduser --system --group appuser

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

# Copy project
COPY . /app/

# Create directories for media
RUN mkdir -p /app/downloads
RUN mkdir -p /app/staticfiles


RUN chown -R appuser:appuser /app
RUN chmod -R 755 /app
RUN chown -R appuser:appuser /app/downloads
RUN chown -R appuser:appuser /app/staticfiles
RUN chmod -R 755 /app/downloads
RUN chmod -R 755 /app/staticfiles
USER appuser

# Command will be specified in docker-compose.yml