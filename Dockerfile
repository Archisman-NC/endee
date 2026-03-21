# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose ports for Streamlit and Endee (if Endee runs inside this same container, but usually it's separate)
EXPOSE 8501 8080

# The command to run varies by service; defined in docker-compose.yml
CMD ["streamlit", "run", "repomind/frontend/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
