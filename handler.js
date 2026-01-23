const { Storage } = require('@google-cloud/storage');
const ffmpegPath = require('ffmpeg-static');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const axios = require('axios');

const storage = new Storage({
  credentials: process.env.GCS_KEY_JSON
    ? JSON.parse(process.env.GCS_KEY_JSON)
    : undefined,
});

const BUCKET_NAME = process.env.GCS_BUCKET_NAME;

async function download(url, dest) {
  const writer = fs.createWriteStream(dest);
  const response = await axios({
    url,
    method: 'GET',
    responseType: 'stream',
    headers: { 'User-Agent': 'Mozilla/5.0' },
  });
  response.data.pipe(writer);
  return new Promise((resolve, reject) => {
    writer.on('finish', resolve);
    writer.on('error', reject);
  });
}

async function renderVideo(fileName, images, audio) {
  const tmp = '/tmp';
  const imageFiles = images.map((_, i) => path.join(tmp, `img${i}.jpg`));
  const audioFile = path.join(tmp, 'audio.ogg');
  const output = path.join(tmp, fileName);

  try {
    console.log('Downloading assets');
    await Promise.all([
      ...images.map((u, i) => download(u, imageFiles[i])),
      download(audio, audioFile),
    ]);

    console.log('Running ffmpeg');
    execFileSync(ffmpegPath, [
      '-loop','1','-t','12','-i',imageFiles[0],
      '-loop','1','-t','12','-i',imageFiles[1],
      '-loop','1','-t','12','-i',imageFiles[2],
      '-loop','1','-t','12','-i',imageFiles[3],
      '-loop','1','-t','11','-i',imageFiles[4],
      '-i',audioFile,
      '-c:v','libx264',
      '-pix_fmt','yuv420p',
      '-shortest',
      output
    ], { stdio: 'inherit' });

    console.log('Uploading to GCS');
    await storage.bucket(BUCKET_NAME).upload(output, {
      destination: fileName,
      metadata: { contentType: 'video/mp4' },
    });

    return `https://storage.googleapis.com/${BUCKET_NAME}/${fileName}`;
  } finally {
    [...imageFiles, audioFile, output].forEach(f => {
      if (fs.existsSync(f)) fs.unlinkSync(f);
    });
  }
}

module.exports = async function (event) {
  console.log('Handler invoked', JSON.stringify(event));

  const input = event.input;
  if (!input || !Array.isArray(input.images) || input.images.length !== 5 || !input.audio) {
    throw new Error('Invalid input: need 5 images and 1 audio');
  }

  const filename = `video-${Date.now()}.mp4`;
  const url = await renderVideo(filename, input.images, input.audio);
  return { status: 'completed', url };
};

