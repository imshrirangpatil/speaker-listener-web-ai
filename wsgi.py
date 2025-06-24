#!/usr/bin/env python3
"""
WSGI entry point for production deployment.
This file is used by gunicorn to serve the Flask-SocketIO application.
"""

import os
from app import app, socketio

# Set production environment
os.environ.setdefault("FLASK_ENV", "production")

if __name__ == "__main__":
    # For gunicorn deployment
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
else:
    # For WSGI server
    application = socketio 