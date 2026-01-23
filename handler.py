import os
import json
import uuid
import subprocess
import tempfile
import requests
from google.cloud import storage
import runpod
import traceback


BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")

def _gcs_client():
    key_json = os.environ.get("GCS_KEY_JSON")
    if key_json:
        creds = json.loads(key_json)
        return storage.Client.from_service_account_info(creds)
    return storage.Client()


def download(url: str, dest_path: str):
    with requests.get(url, stream=True, headers={"User-Agent": "Mozilla/5.0"}) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

def handler(job):
    try:
        gcs = _gcs_client()

        print("JOB RECEIVED:", job)

        job_input = job.get("input") or {}
        images = job_input.get("images")
        audio = job_input.get("audio")

        if not isinstance(images, list) or len(images) != 5:
            raise ValueError("Expected exactly 5 image URLs")

        if not audio:
            raise ValueError("Missing audio URL")

        if not BUCKET_NAME:
            raise ValueError("Missing env var: GCS_BUCKET_NAME")

        file_name = f"video-{uuid.uuid4().hex}.mp4"

        with tempfile.TemporaryDirectory() as tmp:
            img_paths = []
            for i in range(5):
                img_path = os.path.join(tmp, f"img{i}.jpg")
                print(f"Downloading image {i}: {images[i]}")
                download(images[i], img_path)
                img_paths.append(img_path)

            audio_path = os.path.join(tmp, "audio.ogg")
            print(f"Downloading audio: {audio}")
            download(audio, audio_path)

            out_path = os.path.join(tmp, file_name)

            print("Running FFmpeg...")

            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-t", "2.4", "-i", img_paths[0],
                "-loop", "1", "-t", "2.4", "-i", img_paths[1],
                "-loop", "1", "-t", "2.4", "-i", img_paths[2],
                "-loop", "1", "-t", "2.4", "-i", img_paths[3],
                "-loop", "1", "-t", "2.4", "-i", img_paths[4],
                "-i", audio_path,
                "-filter_complex",
                "[0:v][1:v][2:v][3:v][4:v]concat=n=5:v=1:a=0,format=yuv420p[v]",
                "-map", "[v]",
                "-map", "5:a",
                "-c:v", "libx264",
                "-shortest",
                out_path
            ]

            subprocess.check_call(cmd)

            print("Uploading to GCS...")

            bucket = gcs.bucket(BUCKET_NAME)
            blob = bucket.blob(file_name)
            blob.upload_from_filename(out_path, content_type="video/mp4")

        result_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{file_name}"

        print("COMPLETED:", result_url)

        return {
            "status": "completed",
            "url": result_url
        }

    except Exception as e:
        print("ERROR:", str(e))
        print(traceback.format_exc())
        return {
            "status": "error",
            "error": str(e),
            "trace": traceback.format_exc()
        }

runpod.serverless.start({"handler": handler})
