# Use official Python slim image
FROM python:3.11-slim

# Install system dependencies, including espeak and build tools
RUN apt-get update && apt-get install -y \
    espeak \
    build-essential \
    libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy your code
COPY . /app

# Install python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose the port your app listens on (set to your PORT env variable in Render)
ENV PORT 5000
EXPOSE 5000

# Start your app (adjust if your main app file is different)
CMD ["python", "app.py"]