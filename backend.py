import json
import os
import shutil
import subprocess
import time

import google.generativeai as genai

from prompt_template import get_bjj_analysis_prompt


def get_ffmpeg_path():
    """
    Smart routing: Detects OS.
    Cloud uses native Linux ffmpeg. Windows uses the Python fallback.
    """
    # 1. Cloud Check: If native ffmpeg exists, use it instantly.
    if shutil.which("ffmpeg"):
        return "ffmpeg"

    # 2. Local Windows Check: Only import this if native isn't found!
    # This prevents the Streamlit Cloud 'pkg_resources' crash.
    try:
        import imageio_ffmpeg

        exe_path = imageio_ffmpeg.get_ffmpeg_exe()

        # Failsafe for WinError 2
        if not os.path.exists(exe_path):
            raise Exception("FFmpeg .exe is missing from your Python environment.")
        return exe_path

    except ImportError:
        raise Exception("Missing local compressor! Run: pip install imageio-ffmpeg")


def compress_video_locally(input_path, output_path, status_callback):
    """
    Strict FFmpeg compression.
    """
    status_callback("⚡ Compressing video locally (480p, 3 FPS)...")

    try:
        ffmpeg_exe = get_ffmpeg_path()

        cmd = [
            ffmpeg_exe,
            "-y",
            "-i",
            input_path,
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-vf",
            "scale=-2:480",
            "-r",
            "3",
            "-an",
            output_path,
        ]

        process = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if process.returncode != 0:
            raise Exception(f"FFmpeg crashed: {process.stderr}")

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise Exception("Output file was created but is empty.")

        return output_path

    except Exception as e:
        raise Exception(f"Compression failed: {str(e)}")


def analyze_video_with_gemini(
    video_path, user_desc, opp_desc, match_context, api_key, status_callback=None
):
    def update_status(msg):
        if status_callback:
            status_callback(msg)

    compressed_path = video_path + "_compressed.mp4"
    video_file = None

    try:
        genai.configure(api_key=api_key)

        # 1. Compress Video
        upload_path = compress_video_locally(video_path, compressed_path, update_status)

        file_size_mb = os.path.getsize(upload_path) / (1024 * 1024)
        update_status(
            f"Uploading optimized video ({file_size_mb:.2f} MB) to Google's servers..."
        )

        # 2. Upload Video
        for attempt in range(3):
            try:
                video_file = genai.upload_file(path=upload_path)
                break
            except Exception as e:
                if attempt == 2:
                    raise
                update_status(
                    f"Upload connection dropped. Retrying... ({attempt + 1}/3)"
                )
                time.sleep(2)

        # 3. Wait for processing to complete
        update_status("Extracting frames and processing video content...")
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            raise Exception("Video processing failed on Google's servers.")

        # 4. Generate Prompt
        prompt = get_bjj_analysis_prompt(user_desc, opp_desc, match_context)

        # 5. Initialize Model
        # 5. Initialize Model
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",  # <-- THE UPGRADE
            generation_config={
                "temperature": 0.1,
                "response_mime_type": "application/json",
                "max_output_tokens": 8192,
            },
        )

        # 6. Call API
        update_status(
            "Analyzing micro-battles and formatting Coach Notes (This takes ~15-45 seconds)..."
        )
        for attempt in range(3):
            try:
                response = model.generate_content(
                    [video_file, prompt], request_options={"timeout": 120}
                )
                break
            except Exception as e:
                if attempt == 2:
                    raise
                update_status(
                    f"Google API hung. Retrying generation... ({attempt + 1}/3)"
                )
                time.sleep(2)

        result_json = json.loads(response.text)
        return result_json

    except Exception as e:
        raise Exception(f"{str(e)}")

    finally:
        if video_file:
            try:
                update_status("Cleaning up temporary cloud files...")
                genai.delete_file(video_file.name)
            except:
                pass

        if os.path.exists(compressed_path):
            try:
                time.sleep(1)
                os.remove(compressed_path)
            except:
                pass
