FROM node:18-slim

# Install minimal shared libs for FFmpeg-static and GCS
RUN apt-get update && apt-get install -y \
    ca-certificates \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package*.json ./
RUN npm install --production

COPY . .

CMD [ "node", "handler.js" ]
