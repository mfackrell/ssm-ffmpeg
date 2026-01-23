import os
import json
import uuid
import subprocess
import tempfile
import requests
from google.cloud import storage
import runpod

BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")

def _gcs_client():
    key_json = os.environ.get("GCS_KEY_JSON")
    if key_json:
        creds = json.loads(key_json)
        return storage.Client.from_service_account_info(creds)
    return storage.Client()

gcs = _gcs_client()

def download(url: str, dest_path: str):
    with requests.get(url, stream=True, headers={"User-Agent": "Mozilla/5.0"}) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

def handler(job):
    job_input = job.get("input") or {}
    images = job_input.get("images")
    audio = job_input.get("audio")

    if (not isinstance(images, list)) or len(images) != 5 or (not audio):
        raise ValueError("Invalid input: expected 5 images and 1 audio URL")

    if not BUCKET_NAME:
        raise ValueError("Missing env var: GCS_BUCKET_NAME")

    file_name = f"video-{uuid.uuid4().hex}.mp4"

    with tempfile.TemporaryDirectory() as tmp:
        img_paths = [os.path.join(tmp, f"img{i}.jpg") for i in range(5)]
        audio_path = os.path.join(tmp, "audio.ogg")
        out_path = os.path.join(tmp, file_name)

        # Download
        for i, url in enumerate(images):
            download(url, img_paths[i])
        download(audio, audio_path)

        # FFmpeg
        cmd = [
            "ffmpeg",
            "-y",
            "-loop","1","-t","12","-i",img_paths[0],
            "-loop","1","-t","12","-i",img_paths[1],
            "-loop","1","-t","12","-i",img_paths[2],
            "-loop","1","-t","12","-i",img_paths[3],
            "-loop","1","-t","11","-i",img_paths[4],
            "-i", audio_path,
            "-c:v","libx264",
            "-pix_fmt","yuv420p",
            "-shortest",
            out_path
        ]
        subprocess.check_call(cmd)

        # Upload to GCS
        bucket = gcs.bucket(BUCKET_NAME)
        blob = bucket.blob(file_name)
        blob.upload_from_filename(out_path, content_type="video/mp4")

    return {
        "status": "completed",
        "url": f"https://storage.googleapis.com/{BUCKET_NAME}/{file_name}"
    }

runpod.serverless.start({"handler": handler})
