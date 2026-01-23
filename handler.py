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
        render = job_input.get("render", {})
        duration = float(render.get("duration", 12))
        fps = int(render.get("fps", 30))
        width = int(render.get("width", 1080))
        height = int(render.get("height", 1920))
        transition = render.get("transition", "cut")  # "cut" or "fade"
        fade_duration = float(render.get("fade_duration", 0.5))


        if not isinstance(images, list) or len(images) == 0:
            raise ValueError("Expected at least 1 image URLs")

        if not audio:
            raise ValueError("Missing audio URL")

        if not BUCKET_NAME:
            raise ValueError("Missing env var: GCS_BUCKET_NAME")

        file_name = f"video-{uuid.uuid4().hex}.mp4"

        with tempfile.TemporaryDirectory() as tmp:
            img_paths = []
            for i in range(len(images)):
                img_path = os.path.join(tmp, f"img{i}.jpg")
                print(f"Downloading image {i}: {images[i]}")
                download(images[i], img_path)
                img_paths.append(img_path)

            audio_path = os.path.join(tmp, "audio")
            print(f"Downloading audio: {audio}")
            download(audio, audio_path)

            out_path = os.path.join(tmp, file_name)

            print("Running FFmpeg...")

            # 1. Compute per-image duration
            image_duration = duration / len(img_paths)
            
            # 2. Build ffmpeg inputs
            ffmpeg_inputs = []
            filter_chains = []
            
            for i, img in enumerate(img_paths):
                ffmpeg_inputs += ["-loop", "1", "-t", str(image_duration), "-i", img]
                # Scale and pad to fit the target resolution without stretching
                filter_chains.append(
                    f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]"
                )
            
            # 3. Join the filter chains and concat
            concat_input = "".join([f"[v{i}]" for i in range(len(img_paths))])
            filter_complex = (
                f"{';'.join(filter_chains)};"
                f"{concat_input}concat=n={len(img_paths)}:v=1:a=0[v]"
            )
            
            # 4. Final Command
            cmd = (
                ["ffmpeg", "-y"]
                + ffmpeg_inputs
                + ["-i", audio_path]
                + [
                    "-filter_complex", filter_complex,
                    "-map", "[v]",
                    "-map", f"{len(img_paths)}:a", # Audio is the last index
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-r", str(fps),
                    "-movflags", "+faststart", # Better for web playback
                    "-shortest",
                    out_path
                ]
            )
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
