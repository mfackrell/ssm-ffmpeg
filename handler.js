import runpod from "runpod-sdk";
import { Storage } from "@google-cloud/storage";
import ffmpegPath from "ffmpeg-static";
import { execFileSync } from "child_process";
import fs from "fs";
import path from "path";
import axios from "axios";

const storage = new Storage(
  process.env.GCS_KEY_JSON
    ? { credentials: JSON.parse(process.env.GCS_KEY_JSON) }
    : {}
);

const BUCKET_NAME = process.env.GCS_BUCKET_NAME;

async function download(url, dest) {
  const writer = fs.createWriteStream(dest);
  const response = await axios({
    url,
    method: "GET",
    responseType: "stream",
    headers: { "User-Agent": "Mozilla/5.0" },
  });

  response.data.pipe(writer);

  return new Promise((resolve, reject) => {
    writer.on("finish", resolve);
    writer.on("error", reject);
  });
}

async function renderVideo(fileName, images, audio) {
  const tmp = "/tmp";
  const imageFiles = images.map((_, i) => path.join(tmp, `img${i}.jpg`));
  const audioFile = path.join(tmp, "audio.ogg");
  const output = path.join(tmp, fileName);

  try {
    console.log("Downloading assets");

    await Promise.all([
      ...images.map((u, i) => download(u, imageFiles[i])),
      download(audio, audioFile),
    ]);

    console.log("Running ffmpeg");

    execFileSync(
      ffmpegPath,
      [
        "-loop", "1", "-t", "12", "-i", imageFiles[0],
        "-loop", "1", "-t", "12", "-i", imageFiles[1],
        "-loop", "1", "-t", "12", "-i", imageFiles[2],
        "-loop", "1", "-t", "12", "-i", imageFiles[3],
        "-loop", "1", "-t", "11", "-i", imageFiles[4],
        "-i", audioFile,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output,
      ],
      { stdio: "inherit" }
    );

    console.log("Uploading to GCS");

    await storage.bucket(BUCKET_NAME).upload(output, {
      destination: fileName,
      metadata: { contentType: "video/mp4" },
    });

    return `https://storage.googleapis.com/${BUCKET_NAME}/${fileName}`;
  } finally {
    [...imageFiles, audioFile, output].forEach((f) => {
      if (fs.existsSync(f)) fs.unlinkSync(f);
    });
  }
}

async function handler(event) {
  console.log("Job received:", JSON.stringify(event));

  const { input } = event;

  if (
    !input ||
    !Array.isArray(input.images) ||
    input.images.length !== 5 ||
    !input.audio
  ) {
    throw new Error("Invalid input: expected 5 images and 1 audio URL");
  }

  const fileName = `video-${Date.now()}.mp4`;
  const url = await renderVideo(fileName, input.images, input.audio);

  return {
    status: "completed",
    url,
  };
}

runpod.serverless.start(handler);
