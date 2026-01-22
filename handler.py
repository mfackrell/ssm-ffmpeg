import os
import subprocess
import requests
import tempfile
from google.cloud import storage

BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "ssm-renders-8822")

storage_client = storage.Client()

def download(url, path):
    r = requests.get(url, stream=True, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

def handler(event):
    images = event["input"].get("images")
    audio_url = event["input"].get("audio")

    if not images or len(images) != 5 or not audio_url:
        return {"error": "Must provide exactly 5 images and 1 audio URL"}

    with tempfile.TemporaryDirectory() as tmp:
        image_files = []
        for i, url in enumerate(images):
            img_path = os.path.join(tmp, f"img{i}.jpg")
            download(url, img_path)
            image_files.append(img_path)

        audio_path = os.path.join(tmp, "audio.wav")
        download(audio_url, audio_path)

        output_path = os.path.join(tmp, "output.mp4")

        filter_complex = (
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

        cmd = [
            "ffmpeg",
            "-loop","1","-t","12","-i",ima
