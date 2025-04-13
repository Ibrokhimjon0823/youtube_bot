# bot/Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy bot code
COPY . .

# Create directory for logs
RUN mkdir -p /app/logs && \
    chmod -R 755 /app/logs

# Run as non-root user for better security
RUN useradd -m botuser
RUN chown -R botuser:botuser /app
USER botuser

