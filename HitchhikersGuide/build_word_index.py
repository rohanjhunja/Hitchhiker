#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import csv
import re
from pathlib import Path

def detect_chapters(text):
    pattern = re.compile(r'^\s*=\s*=\s*=\s*=\s*=\s*=\s*$', re.MULTILINE)
    starts = [m.start() for m in pattern.finditer(text)]
    if not starts:
        return [(0, len(text), 0)]
    if starts[0] > 0:
        starts.insert(0, 0)
    filtered_starts = []
    for s in starts:
        if not filtered_starts or (s - filtered_starts[-1] > 200):
            filtered_starts.append(s)
    spans = []
    for i, s in enumerate(filtered_starts):
        e = filtered_starts[i+1] if i+1 < len(filtered_starts) else len(text)
        spans.append((s, e, i))
    return spans

def detect_paragraphs(text):
    para_split = re.compile(r'(?:?
){2,}|?
(?=\s{4}|	)|(?<=
)(?=\s*=\s*=\s*=\s*=\s*=)')
    spans = []
    last = 0
    for m in para_split.finditer(text):
        if m.start() > last:
            if text[last:m.start()].strip():
                spans.append((last, m.start()))
        last = m.end()
    if last < len(text) and text[last:].strip():
        spans.append((last, len(text)))
    return spans

def chapter_idx_for_position(spans, pos):
    for s, e, ci in spans:
        if s <= pos < e:
            return ci
    return spans[-1][2] if spans else 0

def build_index(text, keep_hyphens=False):
    if keep_hyphens:
        word_pattern = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")
    else:
        word_pattern = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?")

    chapter_spans = detect_chapters(text)
    para_spans = detect_paragraphs(text)

    rows = []
    wid = 0

    for p_idx, (ps, pe) in enumerate(para_spans):
        paragraph_text = text[ps:pe]
        c_idx = chapter_idx_for_position(chapter_spans, ps)
        for m in word_pattern.finditer(paragraph_text):
            rows.append({
                "word_idx": wid,
                "start_char": ps + m.start(),
                "word": m.group(0),
                "paragraph_idx": p_idx,
                "chapter_idx": c_idx
            })
            wid += 1
    return rows

def write_csv(rows, out_csv):
    if not rows:
        Path(out_csv).write_text("", encoding="utf-8")
        return
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["word_idx", "start_char", "word", "paragraph_idx", "chapter_idx"]
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

def write_json(rows, out_json):
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

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

    text = Path(args.input_txt).read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
    rows = build_index(text, keep_hyphens=args.keep_hyphens)
    write_csv(rows, args.csv)
    write_json(rows, args.json)

    print(f"Done.\nCSV : {args.csv}\nJSON: {args.json}\nWords indexed: {len(rows)}")

if __name__ == "__main__":
    main()
