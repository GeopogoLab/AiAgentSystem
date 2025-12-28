"""Test script for local TTS service."""
import asyncio
import base64
from pathlib import Path

# Set up environment before importing
import os
os.environ['TTS_PROVIDER'] = 'local'
os.environ['LOCAL_TTS_MODEL'] = 'tts_models/en/ljspeech/tacotron2-DDC'
os.environ['LOCAL_TTS_DEVICE'] = 'cpu'

from voice_service.local_tts import synthesize_local_tts


async def test_tts():
    """Test local TTS synthesis."""
    print("Testing Local TTS Service")
    print("=" * 50)

    # Test text
    test_text = "Hello, this is a test of the local text to speech system."
    print(f"\nInput text: {test_text}")

    try:
        # Synthesize speech
        print("\nSynthesizing speech...")
        response = await synthesize_local_tts(test_text)

        # Save the audio
        audio_bytes = base64.b64decode(response.audio_base64)
        output_path = Path("test_output.wav")
        output_path.write_bytes(audio_bytes)

        print(f"✅ Success!")
        print(f"   Voice: {response.voice}")
        print(f"   Format: {response.format}")
        print(f"   Audio size: {len(audio_bytes)} bytes")
        print(f"   Saved to: {output_path.absolute()}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_tts())
