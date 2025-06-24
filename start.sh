#!/bin/bash

# Set environment variables
export FLASK_ENV=production
export PYTHONUNBUFFERED=1

# Get port from environment or default to 5000
PORT=${PORT:-5000}

echo "Starting application on port $PORT..."

# Use gunicorn with eventlet worker for Socket.IO support
exec gunicorn --worker-class eventlet \
    --workers 1 \
    --bind 0.0.0.0:$PORT \
    --timeout 120 \
    --keep-alive 2 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    wsgi:application 