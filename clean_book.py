#!/usr/bin/env python3
"""Clean up OCR output from Kindle page screenshots."""

import re

input_file = "/Users/sappermarine/kindle_extraction/book_raw.txt"
output_file = "/Users/sappermarine/kindle_extraction/The_Lost_Gems_of_Genesis.txt"

with open(input_file, 'r') as f:
    text = f.read()

# Remove page break markers
text = text.replace('\n\n--- PAGE BREAK ---\n\n', '\n\n')

# Remove any stray Kindle UI text that might have leaked through
ui_patterns = [
    r'^.*Kindle Library.*$',
    r'^.*THE LOST GEMS OF GENE\.\.\.\s*=:.*$',
    r'^.*Learning reading speed.*$',
    r'^Page \d+ of \d+.*$',
    r'^Back to \d+$',
    r'^\d+ Kindle Library$',
    r'^W$',  # Lone bookmark icon artifact
]
for pattern in ui_patterns:
    text = re.sub(pattern, '', text, flags=re.MULTILINE)

# Clean up excessive blank lines (more than 2 consecutive)
text = re.sub(r'\n{4,}', '\n\n\n', text)

# Clean up leading/trailing whitespace
text = text.strip() + '\n'

with open(output_file, 'w') as f:
    f.write(text)

# Stats
lines = text.split('\n')
words = len(text.split())
chars = len(text)
print(f"Cleaned book written to: {output_file}")
print(f"Stats: {chars:,} characters, {words:,} words, {len(lines):,} lines")
