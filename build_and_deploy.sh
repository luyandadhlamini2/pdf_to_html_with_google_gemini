#!/bin/bash

# Set your GCP project ID
PROJECT_ID="YOUR_PROJECT_ID"

# Set the name of your container image
IMAGE_NAME="pdf-to-markdown"

# Set the region for Cloud Run deployment
REGION="us-central1" # Change to your preferred region

echo "Starting deployment process to Google Cloud Run..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker is not running or not installed."
  exit 1
fi

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
  echo "Error: Google Cloud SDK (gcloud) is not installed."
  echo "Please install it from https://cloud.google.com/sdk/docs/install"
  exit 1
fi

# Build the Docker image
echo "Building Docker image..."
docker build -t gcr.io/$PROJECT_ID/$IMAGE_NAME .

# Push the image to Google Container Registry
echo "Pushing Docker image to Google Container Registry..."
if ! docker push gcr.io/$PROJECT_ID/$IMAGE_NAME; then
  echo "Error: Failed to push image to Google Container Registry."
  echo "Make sure you're authenticated and have the necessary permissions."
  echo "Run: gcloud auth configure-docker"
  exit 1
fi

# Deploy the Cloud Run service
echo "Deploying to Google Cloud Run..."
gcloud run deploy $IMAGE_NAME \
  --image gcr.io/$PROJECT_ID/$IMAGE_NAME \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated # REMOVE THIS LINE FOR PRODUCTION

if [ $? -eq 0 ]; then
  echo "Deployment complete! Access your application at:"
  gcloud run services describe $IMAGE_NAME --region=$REGION --format="value(status.url)"
else
  echo "Deployment failed. Please check the error messages above."
  exit 1
fi
