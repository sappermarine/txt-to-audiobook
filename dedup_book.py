#!/usr/bin/env python3
"""Deduplicate pages from OCR output where Kindle reader errors caused repeated screenshots."""

import re

input_file = "/Users/sappermarine/kindle_extraction/book_raw.txt"
output_file = "/Users/sappermarine/kindle_extraction/The_Lost_Gems_of_Genesis.txt"

with open(input_file, 'r') as f:
    text = f.read()

# Split into pages
pages = text.split('\n\n--- PAGE BREAK ---\n\n')
print(f"Total pages before dedup: {len(pages)}")

# Deduplicate consecutive pages
# Use first 200 chars of each page as a fingerprint (handles minor OCR variations)
deduped = []
prev_fingerprint = None

for page in pages:
    page_stripped = page.strip()
    if not page_stripped:
        continue

    # Use first 200 non-whitespace chars as fingerprint
    fingerprint = re.sub(r'\s+', ' ', page_stripped[:200])

    if fingerprint == prev_fingerprint:
        # Skip duplicate
        continue

    deduped.append(page_stripped)
    prev_fingerprint = fingerprint

print(f"Pages after dedup: {len(deduped)}")
print(f"Removed {len(pages) - len(deduped)} duplicate pages")

# Rejoin with clean paragraph breaks
clean_text = '\n\n'.join(deduped)

# Remove any stray Kindle UI text
ui_patterns = [
    r'^.*Kindle Library.*$',
    r'^.*THE LOST GEMS OF GENE\.\.\.\s*=:.*$',
    r'^.*Learning reading speed.*$',
    r'^Page \d+ of \d+.*$',
    r'^Back to \d+$',
    r'^\d+ Kindle Library$',
    r'^W$',
]
for pattern in ui_patterns:
    clean_text = re.sub(pattern, '', clean_text, flags=re.MULTILINE)

# Clean up excessive blank lines
clean_text = re.sub(r'\n{4,}', '\n\n\n', clean_text)
clean_text = clean_text.strip() + '\n'

with open(output_file, 'w') as f:
    f.write(clean_text)

words = len(clean_text.split())
chars = len(clean_text)
lines = len(clean_text.split('\n'))
print(f"\nCleaned book written to: {output_file}")
print(f"Stats: {chars:,} characters, {words:,} words, {lines:,} lines")
print(f"Amazon reported word count: 131,452")
print(f"Ratio: {words/131452:.2f}x (ideally close to 1.0)")
