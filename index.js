import express from "express";
import ffmpegPath from "ffmpeg-static";
import { execFileSync } from "child_process";
import fs from "fs";
import path from "path";
import axios from "axios";
import { fileURLToPath } from "url";
import { Storage } from "@google-cloud/storage";

const app = express();
app.use(express.json({ limit: "50mb" }));

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const storage = new Storage();
const BUCKET_NAME = process.env.GCS_BUCKET_NAME;

async function download(url, dest) {
  const writer = fs.createWriteStream(dest);
  const response = await axios({
    url,
    method: "GET",
    responseType: "stream",
    headers: { "User-Agent": "Mozilla/5.0" }
  });

  response.data.pipe(writer);

  return new Promise((resolve, reject) => {
    writer.on("finish", resolve);
    writer.on("error", reject);
  });
}

async function renderVideo(fileName, imageUrls, audioUrl) {
  const tmp = "/tmp";
  const imageFiles = [];

  for (let i = 0; i < 5; i++) {
    const p = path.join(tmp, `img${i}.jpg`);
    await download(imageUrls[i], p);
    imageFiles.push(p);
  }

  const audioFile = path.join(tmp, "audio.wav");
  await download(audioUrl, audioFile);

  const output = path.join(tmp, fileName);

  const filters =
    "[0:v]scale=1080:1080,format=rgba[v0];" +
    "[1:v]scale=1080:1080,format=rgba[v1];" +
    "[2:v]scale=1080:1080,format=rgba[v2];" +
    "[3:v]scale=1080:1080,format=rgba[v3];" +
    "[4:v]scale=1080:1080,format=rgba[v4];" +
    "[v0][v1]xfade=fade:1:11[v01];" +
    "[v01][v2]xfade=fade:1:22[v012];" +
    "[v012][v3]xfade=fade:1:33[v0123];" +
    "[v0123][v4]xfade=fade:1:44[v]";

  const args = [
    "-loop","1","-t","12","-i",imageFiles[0],
    "-loop","1","-t","12","-i",imageFiles[1],
    "-loop","1","-t","12","-i",imageFiles[2],
    "-loop","1","-t","12","-i",imageFiles[3],
    "-loop","1","-t","11","-i",imageFiles[4],
    "-i",audioFile,
    "-filter_complex",filters,
    "-map","[v]",
    "-map","5:a",
    "-c:v","libx264",
    "-pix_fmt","yuv420p",
    "-r","30",
    "-shortest",
    output
  ];

  execFileSync(ffmpegPath, args);

  await storage.bucket(BUCKET_NAME).upload(output, {
    destination: fileName
  });

  return `https://storage.googleapis.com/${BUCKET_NAME}/${fileName}`;
}

app.post("/render", async (req, res) => {
  try {
    const { images, audio } = req.body;

    if (!images || images.length !== 5 || !audio) {
      return res.status(400).json({ error: "Requires 5 images + audio" });
    }

    const fileName = `video-${Date.now()}.mp4`;
    const url = await renderVideo(fileName, images, audio);

    res.json({ status: "completed", url });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

app.listen(8000, () => {
  console.log("FFmpeg renderer listening on port 8000");
});
