import { Storage } from '@google-cloud/storage';
import ffmpegPath from 'ffmpeg-static';
import { execFileSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import axios from 'axios';

const storage = new Storage({
  credentials: process.env.GCS_KEY_JSON ? JSON.parse(process.env.GCS_KEY_JSON) : undefined,
});

const BUCKET_NAME = process.env.GCS_BUCKET_NAME || 'ssm-renders-8822';

async function download(url, dest) {
  const writer = fs.createWriteStream(dest);
  const response = await axios({ url, method: 'GET', responseType: 'stream', headers: { 'User-Agent': 'Mozilla/5.0' } });
  response.data.pipe(writer);
  return new Promise((resolve, reject) => {
    writer.on('finish', resolve);
    writer.on('error', reject);
  });
}

async function renderVideo(fileName, imageUrls, audioUrl) {
  const tmp = '/tmp';
  const imageFiles = imageUrls.map((_, i) => path.join(tmp, `img${i}-${Date.now()}.jpg`));
  const audioFile = path.join(tmp, `audio-${Date.now()}.wav`);
  const output = path.join(tmp, fileName);

  try {
    // Parallelize downloads for speed
    console.log('Downloading assets...');
    await Promise.all([
      ...imageUrls.map((url, i) => download(url, imageFiles[i])),
      download(audioUrl, audioFile)
    ]);

    const filters = '[0:v]scale=1080:1080,format=rgba[v0];[1:v]scale=1080:1080,format=rgba[v1];[2:v]scale=1080:1080,format=rgba[v2];[3:v]scale=1080:1080,format=rgba[v3];[4:v]scale=1080:1080,format=rgba[v4];[v0][v1]xfade=transition=fade:duration=1:offset=11[v01];[v01][v2]xfade=transition=fade:duration=1:offset=22[v012];[v012][v3]xfade=transition=fade:duration=1:offset=33[v0123];[v0123][v4]xfade=transition=fade:duration=1:offset=44[v]';

    const args = [
      '-loop','1','-t','12','-i',imageFiles[0],
      '-loop','1','-t','12','-i',imageFiles[1],
      '-loop','1','-t','12','-i',imageFiles[2],
      '-loop','1','-t','12','-i',imageFiles[3],
      '-loop','1','-t','11','-i',imageFiles[4],
      '-i',audioFile, '-filter_complex',filters, '-map','[v]', '-map','5:a',
      '-c:v','libx264', '-pix_fmt','yuv420p', '-r','30', '-shortest', output
    ];

    console.log('Running FFmpeg...');
    execFileSync(ffmpegPath, args, { stdio: 'inherit' });

    console.log('Uploading to GCS...');
    await storage.bucket(BUCKET_NAME).upload(output, { destination: fileName });

    return `https://storage.googleapis.com/${BUCKET_NAME}/${fileName}`;
  } finally {
    // Guaranteed cleanup
    [...imageFiles, audioFile, output].forEach(f => {
      if (fs.existsSync(f)) fs.unlinkSync(f);
    });
  }
}

export default async function handler(event) {
  const input = event.input;
  if (!input?.images || input.images.length !== 5 || !input.audio) {
    return { error: 'Invalid input: Need 5 images and 1 audio URL.' };
  }

  const fileName = `video-${Date.now()}.mp4`;
  try {
    const url = await renderVideo(fileName, input.images, input.audio);
    return { status: 'completed', url };
  } catch (err) {
    console.error('Render failed:', err);
    return { error: err.message };
  }
}
