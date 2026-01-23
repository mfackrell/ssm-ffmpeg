# 1. Use a slim Python base since your RunPod is set to CPU
FROM python:3.10-slim-buster

# 2. Install FFmpeg and necessary system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 3. Copy only necessary files
COPY handler.py .

# 4. Install Python dependencies
RUN pip3 install --no-cache-dir \
    requests \
    google-cloud-storage \
    runpod

# 5. Run the handler with unbuffered output for real-time logs
CMD ["python3", "-u", "handler.py"]
