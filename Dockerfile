# Use a slim base image to reduce container size
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Use port 8080 as per Google Cloud Run recommendations
ENV PORT=8080

# Command to run the application using JSON format with a shell to expand the PORT variable
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
