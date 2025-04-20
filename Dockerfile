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

# Create directories with proper permissions
RUN mkdir -p /app/downloads /app/staticfiles /app/cookies

# Create empty cookies file if it doesn't exist in the source
RUN touch /app/cookies/youtube.com_cookies.txt

# Set very permissive permissions
RUN chmod -R 777 /app/cookies
RUN chmod 666 /app/cookies/youtube.com_cookies.txt

# Copy project (will overwrite the empty cookies file if one exists in your source)
COPY . /app/

# Ensure permissions again after copying (in case the file was overwritten)
RUN chmod -R 777 /app/cookies
RUN chmod 666 /app/cookies/youtube.com_cookies.txt

# Run as non-root user (for security)
RUN useradd -m appuser
RUN chown -R appuser:appuser /app
USER appuser

# Verify the file exists and has correct permissions
RUN ls -la /app/cookies/