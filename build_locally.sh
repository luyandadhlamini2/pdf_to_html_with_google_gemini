#!/bin/bash

# Set the name of your container image
IMAGE_NAME="pdf-to-markdown"

echo "Setting up local testing environment..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker is not running or not installed."
  exit 1
fi

# Build the Docker image
echo "Building Docker image for local testing..."
docker build -t $IMAGE_NAME .

# Run the container
# Map port 8080 (container) to 8000 (host) for local testing
echo "Starting container for local testing..."
docker run -it -p 8000:8080 $IMAGE_NAME

echo "Application is running at http://localhost:8000"
echo "Access the API documentation at http://localhost:8000/docs"
