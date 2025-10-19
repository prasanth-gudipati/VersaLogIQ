# VersaLogIQ - Docker Container
# Based on Ubuntu 22.04 to match your host system
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    openssh-client \
    sshpass \
    redis-tools \
    kubectl \
    jq \
    curl \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better Docker layer caching)
COPY backend/requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY backend/ /app/

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && chmod 755 /app/logs

# Expose the Flask port
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=versalogiq_app.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Run the application
CMD ["python", "versalogiq_app.py"]