FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install requests prometheus_client

# Copy canary script and image
COPY canary.py /app/
COPY jeep.jpg /app/

# Make script executable
RUN chmod +x canary.py

# Expose Prometheus metrics port
EXPOSE 9100

# Run the canary service
CMD ["python", "canary.py"]
