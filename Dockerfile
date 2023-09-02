# Use Nvidia's latest Ubuntu 22.04 image as the base image
FROM nvidia/cuda:12.2.0-devel-ubuntu22.04

# Install python3.11
RUN apt update && apt install -y python3.11

# Install pip
RUN apt -y install python3-pip

# Set the working directory to /app
WORKDIR /app

# Copy the working directory contents into the container at /app
COPY . .

# Install any needed packages specified in pyproject.toml
RUN sed -i 's/dynamic = \["version"\]/version = "0.0.0"/' pyproject.toml && \
    pip install --no-cache-dir .

# Make port 8488 available to the world outside this container
EXPOSE 8488

# Run the gunicorn server with the FastAPI app
ENTRYPOINT ["gunicorn", "--bind", "0.0.0.0:8488", "src.flint.main:app", "--workers", "3", "-k", "uvicorn.workers.UvicornWorker", "--timeout", "600", "--keep-alive", "120", "--threads", "3"]
