# txt-to-audiobook

Convert any `.txt` file into an MP3 audiobook using Google Cloud Text-to-Speech.

Uses Neural2/WaveNet voices (natural-sounding) covered by Google Cloud's **free tier: 1M characters/month** — enough for a ~500-page book.

## Features

- **Parallel processing** — 8 concurrent workers by default (~3 min for a full book)
- **Auto-retry with backoff** — handles transient network errors without dying
- **Resume support** — re-run the same command and it skips already-completed chunks
- **Configurable voice, speed, and parallelism** via CLI flags
- **Request timeouts** — no more hung connections blocking the pipeline

## Setup

### 1. Google Cloud credentials (one-time, free)

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (e.g., `tts-audiobook`)
3. Enable the **Cloud Text-to-Speech API**: [direct link](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)
4. Create a **Service Account** under APIs & Services → Credentials
5. Generate a **JSON key** for the service account
6. Save it somewhere safe (default expected location: `~/.config/work-credentials/gcloud-tts-key.json`)

### 2. Install dependencies

```bash
pip install google-cloud-texttospeech
```

Or using the requirements file:

```bash
pip install -r requirements.txt
```

## Usage

Basic usage:

```bash
python generate_audiobook.py book.txt
# → creates book.mp3 in the same directory
```

Specify output path:

```bash
python generate_audiobook.py book.txt ~/audiobooks/book.mp3
```

Customize voice and speed:

```bash
python generate_audiobook.py book.txt -v en-US-Neural2-D -r 1.2
```

List available voices:

```bash
python generate_audiobook.py --list-voices --credentials path/to/key.json
```

More parallelism (faster, but may hit rate limits):

```bash
python generate_audiobook.py book.txt -w 12
```

Custom credentials path:

```bash
python generate_audiobook.py book.txt --credentials ~/my-key.json
```

### All options

| Flag | Default | Description |
|------|---------|-------------|
| `-v`, `--voice` | `en-US-Neural2-J` | TTS voice name |
| `-r`, `--rate` | `1.0` | Speaking rate (0.5 = slow, 2.0 = fast) |
| `-w`, `--workers` | `8` | Parallel request workers |
| `--credentials` | `~/.config/work-credentials/gcloud-tts-key.json` | Service account key path |
| `--timeout` | `30` | Per-request timeout in seconds |
| `--list-voices` | — | List available voices and exit |

## How it works

1. **Split** — Text is broken into ~4800-byte chunks at sentence boundaries (API limit is 5000 bytes/request)
2. **Synthesize** — Chunks are sent to Google Cloud TTS in parallel with automatic retry on failure
3. **Stitch** — All MP3 chunks are concatenated into a single output file

Intermediate chunks are stored in a hidden directory (`.bookname_chunks/`) next to the output file. If the process is interrupted, re-running the same command resumes from where it left off.

## Cost

Google Cloud TTS free tier includes **1,000,000 Neural2/WaveNet characters per month**. A typical 500-page book is ~700k-800k characters, so one book per month is free.

Beyond the free tier: $16 per 1M characters for Neural2 voices.

## Companion: Kindle book extraction

This repo also includes tools for extracting text from Kindle books you own via the Kindle Web Reader:

1. **`ocr_pages.swift`** — macOS Vision framework OCR for batch-processing screenshots
2. **`clean_book.py`** — Cleans OCR artifacts from raw text output

Pipeline: Kindle Web Reader → screenshots → OCR → clean text → `generate_audiobook.py` → MP3
