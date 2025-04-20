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

# Create user first
RUN useradd -m appuser

# Create directories with proper permissions
RUN mkdir -p /app/downloads /app/staticfiles /app/cookies

# Copy project 
COPY . /app/

# Change ownership of everything to appuser
RUN chown -R appuser:appuser /app/cookies

# Set very permissive permissions specifically for cookies directory and files
RUN chmod -R 755 /app/cookies
RUN chmod 666 /app/cookies/*.txt

# Switch to appuser
USER appuser