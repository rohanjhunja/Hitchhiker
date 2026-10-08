#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.process_book import build_index, write_csv, write_json

def main():
    ap = argparse.ArgumentParser(
        description="Build word index (CSV + JSON) from a text file."
    )
    ap.add_argument("input_txt", nargs="?", default="book.txt", help="Path to the input .txt file")
    ap.add_argument("--csv", default="hhgttg_word_index.csv", help="Output CSV path")
    ap.add_argument("--json", default="hhgttg_word_index.json", help="Output JSON path")
    ap.add_argument("--keep-hyphens", action="store_true",
                    help="Treat hyphenated words as a single token")
    args = ap.parse_args()

    book_dir = Path(__file__).resolve().parent

    input_file = Path(args.input_txt)
    if not input_file.is_absolute() and not input_file.exists():
        input_file = book_dir / args.input_txt

    csv_file = Path(args.csv)
    if not csv_file.is_absolute() and len(csv_file.parts) == 1:
        csv_file = input_file.parent / args.csv

    json_file = Path(args.json)
    if not json_file.is_absolute() and len(json_file.parts) == 1:
        json_file = input_file.parent / args.json

    text = input_file.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
    rows = build_index(text, keep_hyphens=args.keep_hyphens)
    write_csv(rows, csv_file)
    write_json(rows, json_file)

    print(f"Done.\nCSV : {csv_file}\nJSON: {json_file}\nWords indexed: {len(rows)}")

if __name__ == "__main__":
    main()
