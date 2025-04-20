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

# Create appuser first
RUN useradd -m appuser

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Create directories for media - owned by appuser
RUN mkdir -p /app/downloads /app/staticfiles /app/cookies && \
    chown -R appuser:appuser /app

# Handle cookie files separately before copying all project files
COPY cookies/*.txt /app/cookies/
RUN chown -R appuser:appuser /app/cookies && \
    chmod -R 755 /app/cookies && \
    chmod 666 /app/cookies/*.txt || true

# Copy the rest of the project files
COPY --chown=appuser:appuser . /app/

# Set permissions again for the cookies after all files are copied
RUN chown -R appuser:appuser /app/cookies && \
    chmod -R 755 /app/cookies && \
    chmod 666 /app/cookies/*.txt || true

# Switch to appuser for running the application
USER appuser

# Command to run when container starts
CMD ["python", "app.py"]