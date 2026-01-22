FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y \
    ffmpeg \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY handler.py .

RUN pip3 install \
    requests \
    google-cloud-storage

CMD ["python3", "-u", "handler.py"]
