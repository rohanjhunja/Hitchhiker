---
name: hitchhiker-book-processing
description: >-
  Automates text cleaning, word indexing, gallery preview extraction, and index page card registration for books in the Hitchhikers repository.
  Use this skill whenever processing, cleaning, indexing, or adding a new text file or book (e.g. Odyssey, LOTR, Dune, etc.) to avoid unnecessary token usage.
---

# Hitchhiker Book Processing Skill

This skill provides a zero-token-overhead, deterministic CLI tool to process text files for books in the Hitchhikers repository.

## Overview

When adding or processing a new book directory in this project:
1. **Clean Text**: Removes outer Project Gutenberg license headers/footers and normalizes line endings into `book.txt`.
2. **Build Index**: Detects chapters (`BOOK I`, `CHAPTER 1`, `Book 1`, `====`) and paragraph boundaries to produce `hhgttg_word_index.csv` and `hhgttg_word_index.json`.
3. **Gallery Previews**: Scans paragraph color occurrences (`COLOR_MAP`) and updates `gallery_previews.json`.
4. **HTML Card Registration**: Inserts the book poster card into `index.html`.
5. **Verification**: Verifies character offsets against `book.txt` automatically.

## Quick Usage

Run the automated script from the repository root:

```bash
python3 scripts/process_book.py <BookFolder> [--title "Book Title"] [--author "Author Name"]
```

### Example:

```bash
python3 scripts/process_book.py Odyssey --title "The Odyssey" --author "Homer"
```

## Manual / Step-by-Step Reference

If you need to inspect or customize specific steps:
- **Index Script**: `python3 <BookFolder>/build_word_index.py <BookFolder>/book.txt --csv <BookFolder>/hhgttg_word_index.csv --json <BookFolder>/hhgttg_word_index.json`
- **Offset Verification**: Ensure `hhgttg_word_index.json` offsets point directly to exact characters in `book.txt`.
- **Previews**: Ensure `gallery_previews.json` contains a key matching `<BookFolder>`.
