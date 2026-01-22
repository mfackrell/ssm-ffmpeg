FROM node:20-slim

RUN apt-get update && apt-get install -y \
  ca-certificates \
  fonts-liberation \
  libnss3 \
  libx11-6 \
  libxrender1 \
  libxext6 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY . .

EXPOSE 8000
CMD ["node", "index.js"]
