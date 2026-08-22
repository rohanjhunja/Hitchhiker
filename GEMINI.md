# Workspace Rules: Hitchhikers Project

Guidelines and rules for AI agents operating within the Hitchhikers repository.

## Token Efficiency & Book Processing Guidelines

1. **Do NOT Read Full Book Text Files into LLM Context**:
   - Books in this repository range from 150KB to over 1MB of text (100k+ words).
   - Never print or view full `book.txt` files or `hhgttg_word_index.json` files in tool outputs unless inspecting small slices (e.g. `head -n 20` or specific line ranges).

2. **Automated Book Pipeline**:
   - Always use the deterministic CLI tool to process raw text files, build word index CSV/JSON files, update `gallery_previews.json`, and register poster cards in `index.html`:
     ```bash
     python3 scripts/process_book.py <BookFolder> [--title "Book Title"] [--author "Author Name"]
     ```
   - Do not write manual python scripts for text indexing or preview generation when `scripts/process_book.py` is available.

3. **Required Book Directory Files**:
   - Every completed book directory must contain:
     - `book.txt` (Clean text stripped of Project Gutenberg license wrappers)
     - `hhgttg_word_index.csv` (CSV word index)
     - `hhgttg_word_index.json` (JSON word index with exact `start_char` offsets matching `book.txt`)
     - `build_word_index.py` (Local builder script)

4. **Global & Workspace Skill Reference**:
   - Refer to skill `hitchhiker-book-processing` (`.agents/skills/hitchhiker-book-processing/SKILL.md`) for detailed pipeline documentation.
