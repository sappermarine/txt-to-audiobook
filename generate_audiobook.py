#!/usr/bin/env python3
"""Convert a .txt file to an MP3 audiobook using Google Cloud Text-to-Speech.

Uses Neural2/WaveNet voices (covered by Google Cloud free tier: 1M chars/month).
Supports parallel requests, automatic retries, and resume from partial runs.

Usage:
    python generate_audiobook.py input.txt [output.mp3]
    python generate_audiobook.py input.txt -v en-US-Neural2-D  # different voice
    python generate_audiobook.py input.txt -r 1.2              # faster speech
    python generate_audiobook.py input.txt --workers 10        # more parallelism
"""

import argparse
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from google.cloud import texttospeech

# Google TTS limit is 5000 bytes per request
MAX_BYTES = 4800  # margin for safety

# Default credentials path
DEFAULT_CREDENTIALS = os.path.expanduser(
    "~/.config/work-credentials/gcloud-tts-key.json"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert a text file to an MP3 audiobook via Google Cloud TTS."
    )
    parser.add_argument("input", help="Path to the .txt file")
    parser.add_argument("output", nargs="?", help="Output .mp3 path (default: same name as input)")
    parser.add_argument("-v", "--voice", default="en-US-Neural2-J",
                        help="Voice name (default: en-US-Neural2-J). Run with --list-voices to see options.")
    parser.add_argument("-r", "--rate", type=float, default=1.0,
                        help="Speaking rate 0.5-2.0 (default: 1.0)")
    parser.add_argument("-w", "--workers", type=int, default=8,
                        help="Parallel workers (default: 8)")
    parser.add_argument("--credentials", default=DEFAULT_CREDENTIALS,
                        help="Path to Google Cloud service account JSON key")
    parser.add_argument("--list-voices", action="store_true",
                        help="List available English Neural2/WaveNet voices and exit")
    parser.add_argument("--timeout", type=float, default=30,
                        help="Timeout per API request in seconds (default: 30)")
    return parser.parse_args()


def list_voices(credentials_path: str):
    """List available high-quality English voices."""
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    client = texttospeech.TextToSpeechClient()
    response = client.list_voices(language_code="en")
    voices = []
    for voice in response.voices:
        if any(k in voice.name for k in ("Neural2", "WaveNet", "Studio")):
            gender = texttospeech.SsmlVoiceGender(voice.ssml_gender).name
            voices.append((voice.name, gender))
    voices.sort()
    print("Available high-quality English voices:")
    for name, gender in voices:
        print(f"  {name:30s} {gender}")
    print(f"\n{len(voices)} voices available. Use -v NAME to select one.")


def split_text_into_chunks(text: str, max_bytes: int = MAX_BYTES) -> list[str]:
    """Split text into chunks that fit within the byte limit, breaking at sentence boundaries."""
    chunks = []
    paragraphs = text.split("\n")
    current_chunk = ""

    for para in paragraphs:
        sentences = re.split(r'(?<=[.!?])\s+', para)
        for sentence in sentences:
            test = current_chunk + " " + sentence if current_chunk else sentence
            if len(test.encode("utf-8")) > max_bytes:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk = test
        if current_chunk and not current_chunk.endswith("\n"):
            current_chunk += "\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def synthesize_chunk(client, chunk: str, voice_params, audio_config, timeout: float) -> bytes:
    """Send one chunk to the TTS API and return MP3 bytes."""
    input_text = texttospeech.SynthesisInput(text=chunk)
    response = client.synthesize_speech(
        input=input_text, voice=voice_params, audio_config=audio_config,
        timeout=timeout,
    )
    return response.audio_content


def process_chunk(args_tuple):
    """Worker function for parallel processing. Returns (index, audio_bytes) or raises."""
    i, chunk, client, voice_params, audio_config, timeout, max_retries = args_tuple

    for attempt in range(max_retries):
        try:
            audio = synthesize_chunk(client, chunk, voice_params, audio_config, timeout)
            return i, audio
        except Exception as e:
            if attempt < max_retries - 1:
                wait = min(2 ** attempt, 16)
                time.sleep(wait)
            else:
                raise RuntimeError(f"Chunk {i} failed after {max_retries} attempts: {e}")


def main():
    args = parse_args()

    if args.list_voices:
        list_voices(args.credentials)
        return

    # Validate input
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"Error: {input_path} not found")
        sys.exit(1)

    # Set output path
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
    else:
        output_path = input_path.with_suffix(".mp3")

    chunks_dir = output_path.parent / f".{output_path.stem}_chunks"

    # Auth
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = args.credentials

    # Read and split
    print(f"Reading: {input_path}")
    text = input_path.read_text(encoding="utf-8")
    char_count = len(text)
    print(f"Book size: {char_count:,} characters")
    print(f"Estimated Google TTS usage: {char_count:,} / 1,000,000 free monthly chars")

    chunks = split_text_into_chunks(text)
    total = len(chunks)
    print(f"Split into {total} chunks")

    # Check for existing progress
    chunks_dir.mkdir(parents=True, exist_ok=True)
    existing = set(os.listdir(chunks_dir))
    pending = []
    for i, chunk in enumerate(chunks):
        filename = f"chunk_{i:05d}.mp3"
        if filename not in existing:
            pending.append((i, chunk))

    skipped = total - len(pending)
    if skipped > 0:
        print(f"Resuming: {skipped} chunks already done, {len(pending)} remaining")

    if not pending:
        print("All chunks already generated, stitching...")
    else:
        # Set up TTS client
        client = texttospeech.TextToSpeechClient()
        lang_code = "-".join(args.voice.split("-")[:2])
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=lang_code,
            name=args.voice,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=args.rate,
        )

        # Process in parallel batches
        completed = 0
        failed = 0
        batch_size = args.workers * 2
        print(f"Generating with {args.workers} parallel workers...")

        for batch_start in range(0, len(pending), batch_size):
            batch = pending[batch_start:batch_start + batch_size]
            work_items = [
                (i, chunk, client, voice_params, audio_config, args.timeout, 5)
                for i, chunk in batch
            ]

            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = {executor.submit(process_chunk, item): item[0] for item in work_items}
                for future in as_completed(futures):
                    chunk_idx = futures[future]
                    try:
                        i, audio = future.result()
                        filepath = chunks_dir / f"chunk_{i:05d}.mp3"
                        filepath.write_bytes(audio)
                        completed += 1
                        total_done = skipped + completed
                        if completed % 20 == 0 or total_done == total:
                            print(f"  Progress: {total_done}/{total} ({total_done/total*100:.0f}%)")
                    except Exception as e:
                        failed += 1
                        print(f"  {e}")

            # Small delay between batches to avoid rate limits
            if batch_start + batch_size < len(pending):
                time.sleep(0.5)

        if failed > 0:
            print(f"\n{failed} chunks failed. Re-run to retry them.")
            sys.exit(1)

    # Stitch all chunks into one MP3
    print(f"\nStitching {total} chunks into final audiobook...")
    chunk_files = sorted(chunks_dir.glob("chunk_*.mp3"))
    with open(output_path, "wb") as outfile:
        for cf in chunk_files:
            outfile.write(cf.read_bytes())

    final_mb = output_path.stat().st_size / 1024 / 1024
    print(f"\nDone! Audiobook saved to: {output_path}")
    print(f"File size: {final_mb:.1f} MB")
    print(f"Characters used: {char_count:,}")


if __name__ == "__main__":
    main()
