import os
import subprocess
import tempfile
import traceback
from datetime import datetime
import requests
import runpod


def download(url, path):
    r = requests.get(url, stream=True, timeout=30)
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)


def build_ffmpeg_command(image_files, audio_path, output_path):
    filters = (
        "[0:v]scale=1080:1080,format=rgba[v0];"
        "[1:v]scale=1080:1080,format=rgba[v1];"
        "[2:v]scale=1080:1080,format=rgba[v2];"
        "[3:v]scale=1080:1080,format=rgba[v3];"
        "[4:v]scale=1080:1080,format=rgba[v4];"
        "[v0][v1]xfade=transition=fade:duration=1:offset=11[v01];"
        "[v01][v2]xfade=transition=fade:duration=1:offset=22[v012];"
        "[v012][v3]xfade=transition=fade:duration=1:offset=33[v0123];"
        "[v0123][v4]xfade=transition=fade:duration=1:offset=44[v]"
    )

    return [
        "ffmpeg", "-y",
        "-loop", "1", "-t", "12", "-i", image_files[0],
        "-loop", "1", "-t", "12", "-i", image_files[1],
        "-loop", "1", "-t", "12", "-i", image_files[2],
        "-loop", "1", "-t", "12", "-i", image_files[3],
        "-loop", "1", "-t", "11", "-i", image_files[4],
        "-i", audio_path,
        "-filter_complex", filters,
        "-map", "[v]", "-map", "5:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", "30", "-shortest",
        output_path
    ]


def handler(event):
    try:
        payload = event.get("input", {})
        images = payload.get("images")
        audio = payload.get("audio")

        if not images or len(images) != 5 or not audio:
            return {"error": "Must provide exactly 5 images and 1 audio URL"}

        with tempfile.TemporaryDirectory() as tmp:
            imgs = []
            for i, url in enumerate(images):
                p = os.path.join(tmp, f"img{i}.jpg")
                download(url, p)
                imgs.append(p)

            audio_path = os.path.join(tmp, "audio.wav")
            download(audio, audio_path)

            out = os.path.join(tmp, "out.mp4")

            proc = subprocess.run(
                build_ffmpeg_command(imgs, audio_path, out),
                capture_output=True,
                text=True
            )

            if proc.returncode != 0:
                return {"error": "ffmpeg failed", "stderr": proc.stderr}

            return {"status": "ok", "message": "video rendered successfully"}

    except Exception as e:
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }


runpod.serverless.start({"handler": handler})
