# Use official Python image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements and script
COPY requirements.txt .
COPY setup_livekit.py .
COPY cleanup_livekit.py .
COPY fixed_cleanup.py .
COPY final_simple_setup.py .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Default command
CMD ["python", "final_simple_setup.py"]

