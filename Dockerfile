# Use the official Python image as the base image
FROM python:3.11-slim-buster

# Set the working directory to /app
WORKDIR /app

# Copy the working directory contents into the container at /app
COPY . .

# Install any needed packages specified in pyproject.toml
RUN sed -i 's/dynamic = \["version"\]/version = "0.0.0"/' pyproject.toml && \
    pip install --no-cache-dir .

# Make port 8488 available to the world outside this container
EXPOSE 8488

# Set environment variables
# ARG POSTGRES_HOST
# ENV POSTGRES_HOST=$POSTGRES_HOST

# # Run migrations
# RUN python src/flint/manage.py migrate

# Run src.flint.main.py when the container launches
ENTRYPOINT ["python", "src/flint/main.py"]
