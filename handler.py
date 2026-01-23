import os
import subprocess
import tempfile
from datetime import datetime

import requests
from google.cloud import storage
import runpod

BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
storage_client = storage.Client() if BUCKET_NAME else None

def download(url, path):
    r = requests.get(url, stream=True, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

def upload_to_gcs(local_path, destination_name):
    if not storage_client or not BUCKET_NAME:
        return None

    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(destination_name)
    blob.upload_from_filename(local_path)
    return f"https://storage.googleapis.com/{BUCKET_NAME}/{destination_name}"


def build_ffmpeg_command(image_files, audio_path, output_path):
import os
import subprocess
import tempfile
from datetime import datetime

import requests
from google.cloud import storage
import runpod

BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
storage_client = storage.Client() if BUCKET_NAME else None

def download(url, path):
    r = requests.get(url, stream=True, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

def upload_to_gcs(local_path, destination_name):
    if not storage_client or not BUCKET_NAME:
        return None

    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(destination_name)
    blob.upload_from_filename(local_path)
    return f"https://storage.googleapis.com/{BUCKET_NAME}/{destination_name}"


def build_ffmpeg_command(image_files, audio_path, output_path):
    filters = (
        "[0:v]scale=1080:1080,format=rgba[v0];"
        "[1:v]scale=1080:1080,format=rgba[v1];"
        "[2:v]scale=1080:1080,format=rgba[v2];"
        "[3:v]scale=1080:1080,format=rgba[v3];"
        "[4:v]scale=1080:1080,format=rgba[v4];"
        "[v0][v1]xfade=transition=fade:duration=1:offset=11[v01];"
        "[v0][v1]xfade=transition=fade:duration=1:offset=22[v012];"
        "[v0][v1]xfade=transition=fade:duration=1:offset=33[v0123];"
        "[v0][v1]xfade=transition=fade:duration=1:offset=44[v]"
    )

    return [
        "ffmpeg",
        "-y",
        "-loop", "1", "-t", "12", "-i", image_files[0],
        "-loop", "1", "-t", "12", "-i", image_files[1],
        "-loop", "1", "-t", "12", "-i", image_files[2],
        "-loop", "1", "-t", "12", "-i", image_files[3],
        "-loop", "1", "-t", "11", "-i", image_files[4],
        "-i", audio_path,
        "-filter_complex", filters,
        "-map", "[v]",
        "-map", "5:a",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-shortest",
        output_path,
    ]


def handler(event):
    print("EVENT RECEIVED:", event, flush=True)

    payload = event.get("input", {})
    images = payload.get("images")
    audio_url = payload.get("audio")

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
        cmd = build_ffmpeg_command(image_files, audio_path, output_path)

        subprocess.run(cmd, check=True)

        destination_name = f"video-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.mp4"
        uploaded_url = upload_to_gcs(output_path, destination_name)

        response = {"status": "ok"}
        if uploaded_url:
            response["url"] = uploaded_url
        else:
            response["local_output"] = output_path
            response["warning"] = "GCS_BUCKET_NAME not set; returning local path only."

        return response

# 🔴 THIS WAS MISSING
runpod.serverless.start({
    "handler": handler
})


    return [
        "ffmpeg",
        "-y",
        "-loop", "1", "-t", "12", "-i", image_files[0],
        "-loop", "1", "-t", "12", "-i", image_files[1],
        "-loop", "1", "-t", "12", "-i", image_files[2],
        "-loop", "1", "-t", "12", "-i", image_files[3],
        "-loop", "1", "-t", "11", "-i", image_files[4],
        "-i", audio_path,
        "-filter_complex", filters,
        "-map", "[v]",
        "-map", "5:a",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-shortest",
        output_path,
    ]


def handler(event):
    print("EVENT RECEIVED:", event, flush=True)

    payload = event.get("input", {})
    images = payload.get("images")
    audio_url = payload.get("audio")

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
        cmd = build_ffmpeg_command(image_files, audio_path, output_path)

        subprocess.run(cmd, check=True)

        destination_name = f"video-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.mp4"
        uploaded_url = upload_to_gcs(output_path, destination_name)

        response = {"status": "ok"}
        if uploaded_url:
            response["url"] = uploaded_url
        else:
            response["local_output"] = output_path
            response["warning"] = "GCS_BUCKET_NAME not set; returning local path only."

        return response

# 🔴 THIS WAS MISSING
runpod.serverless.start({
    "handler": handler
})
