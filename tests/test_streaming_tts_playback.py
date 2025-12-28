#!/usr/bin/env python3
"""Test script that verifies streaming TTS sends decodable MP3 blobs."""

import base64
import json
import subprocess
import tempfile
import time

import websocket


WS_URL = "ws://localhost:8000/ws/tts"
REQUEST_TEXT = (
    "This is a short verification run. "
    "The goal is to ensure each streamed chunk is a well-formed MP3 blob."
)


def verify_mp3_bytes(blob: bytes) -> None:
    """Ensure FFmpeg can decode the joined MP3 blob."""
    if not blob:
        raise ValueError("No audio bytes to verify")

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(blob)
        tmp.flush()
        tmp_path = tmp.name

    try:
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", tmp_path, "-f", "null", "-"],
            check=True,
        )
    finally:
        subprocess.run(["rm", "-f", tmp_path])


def test_streaming_tts_playback() -> None:
    """Connect to the streaming TTS WS endpoint and decode the output."""
    print(f"Connecting to {WS_URL}...")
    ws = websocket.create_connection(WS_URL, timeout=10)
    print("Connected.")

    payload = {"text": REQUEST_TEXT, "format": "mp3"}
    ws.send(json.dumps(payload))

    chunk_bytes = []
    chunk_count = 0
    total_bytes = 0
    first_byte_time = None
    start_time = time.time()

    print("Receiving MP3 chunks...")
    try:
        while True:
            msg = ws.recv()
            data = json.loads(msg)

            if data.get("message_type") == "error":
                raise RuntimeError(f"TTS error: {data.get('error')}")

            if data.get("message_type") != "audio_chunk":
                continue

            if data.get("is_final"):
                print("Received final chunk marker.")
                break

            audio_data = data.get("audio_data", "")
            if not audio_data:
                continue

            if first_byte_time is None:
                first_byte_time = time.time() - start_time
                print(f"First chunk took {first_byte_time:.3f}s")

            decoded = base64.b64decode(audio_data)
            chunk_bytes.append(decoded)
            chunk_count += 1
            total_bytes += len(decoded)
            print(f"  chunk #{chunk_count}: {len(decoded)} bytes")
    finally:
        ws.close()

    print(f"Collected {chunk_count} chunk(s), {total_bytes} total bytes.")
    if not chunk_bytes:
        raise RuntimeError("No audio received")

    print("Verifying MP3 integrity via FFmpeg...")
    joined = b"".join(chunk_bytes)
    verify_mp3_bytes(joined)

    elapsed = time.time() - start_time
    print(f"FFmpeg verification passed in {elapsed:.2f}s")


if __name__ == "__main__":
    try:
        test_streaming_tts_playback()
    except subprocess.CalledProcessError as exc:
        print("FFmpeg reported a decoding failure.")
        raise SystemExit(exc.returncode)
    except Exception as exc:
        print(f"Test failed: {exc}")
        raise SystemExit(1)
