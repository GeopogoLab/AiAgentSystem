#!/usr/bin/env python3
"""Test script for streaming TTS WebSocket endpoint"""

import asyncio
import json
import base64
import websocket
import time

def test_streaming_tts():
    """Test WebSocket streaming TTS"""
    ws_url = "ws://localhost:8000/ws/tts"

    print(f"Connecting to {ws_url}...")
    ws = websocket.create_connection(ws_url)
    print("✓ Connected!")

    # Send TTS request
    test_text = "Hello, this is a streaming text to speech test."
    request = {
        "text": test_text,
        "format": "mp3"
    }

    print(f"\nSending request: {test_text}")
    ws.send(json.dumps(request))

    # Receive streaming chunks
    chunk_count = 0
    total_bytes = 0
    start_time = time.time()
    first_chunk_time = None

    print("\nReceiving audio chunks:")

    while True:
        response = ws.recv()
        data = json.loads(response)

        if data.get("message_type") == "error":
            print(f"✗ Error: {data.get('error')}")
            break

        if data.get("message_type") == "audio_chunk":
            if data.get("is_final"):
                print(f"\n✓ Streaming complete!")
                break

            if first_chunk_time is None:
                first_chunk_time = time.time() - start_time
                print(f"  ⏱️  Time to first byte: {first_chunk_time:.3f}s")

            audio_data = data.get("audio_data", "")
            if audio_data:
                chunk_size = len(base64.b64decode(audio_data))
                total_bytes += chunk_size
                chunk_count += 1
                print(f"  📦 Chunk {chunk_count}: {chunk_size} bytes (total: {total_bytes} bytes)")

    ws.close()
    total_time = time.time() - start_time

    print(f"\n{'='*50}")
    print(f"📊 Test Results:")
    print(f"  Total chunks: {chunk_count}")
    print(f"  Total audio: {total_bytes} bytes ({total_bytes/1024:.2f} KB)")
    print(f"  Time to first byte: {first_chunk_time:.3f}s" if first_chunk_time else "  No chunks received")
    print(f"  Total time: {total_time:.3f}s")
    print(f"  Average chunk size: {total_bytes/chunk_count:.0f} bytes" if chunk_count > 0 else "")
    print(f"{'='*50}")

if __name__ == "__main__":
    try:
        test_streaming_tts()
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
