#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Build lightweight gallery quote files containing authentic color block quotes
and metadata for all books in the Hitchhikers repository.
Maps each color block in gallery_previews.json directly to its corresponding
paragraph segment in book.txt deterministically with ZERO synthetic placeholders.

Outputs:
1. gallery/quotes/<bookKey>.json (per-book on-demand files)
2. gallery_quotes.json (root fallback file)
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from process_book import (
    COLOR_MAP,
    COLOR_REGEX,
    is_verb_context,
    normalize_color_token,
)

HEX_TO_COLOR_NAME = {}
for k, v in COLOR_MAP.items():
    if v not in HEX_TO_COLOR_NAME:
        HEX_TO_COLOR_NAME[v] = k


def clean_excerpt(para_text, match_start, match_end):
    """
    Extracts a natural 16-24 word excerpt centered on the exact color match.
    """
    words = para_text.split()
    if not words:
        return ""
    if len(words) <= 24:
        return " ".join(words)

    char_pos = 0
    target_w_idx = 0
    for idx, w in enumerate(words):
        char_pos += len(w) + 1
        if char_pos > match_start:
            target_w_idx = idx
            break

    start_w = max(0, target_w_idx - 8)
    end_w = min(len(words), start_w + 18)
    if end_w - start_w < 18:
        start_w = max(0, end_w - 18)

    res = " ".join(words[start_w:end_w])
    if start_w > 0:
        res = "…" + res
    if end_w < len(words):
        res = res + "…"
    return res


def extract_book_quotes(repo_root, book_key, expected_preview_tiles=None):
    """
    Deterministically extracts authentic quotes for each merged color tile in a book.
    """
    book_dir = repo_root / book_key
    txt_path = book_dir / "book.txt"
    idx_path = book_dir / "hhgttg_word_index.json"

    if not txt_path.exists() and book_key == "HitchhikersGuide":
        alt_txt = repo_root / "Hitchhiker Guide to the Galaxy.txt"
        if alt_txt.exists():
            txt_path = alt_txt

    if not txt_path.exists() or not idx_path.exists():
        print(f"Warning: Missing book.txt or hhgttg_word_index.json for {book_key}, skipping.")
        return None

    with open(txt_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    with open(idx_path, "r", encoding="utf-8") as f:
        words = json.load(f)

    by_para = defaultdict(list)
    for r in words:
        by_para[r["paragraph_idx"]].append(r)

    paras_segments = []
    for pid in sorted(by_para.keys()):
        list_w = sorted(by_para[pid], key=lambda x: x["start_char"])
        start = list_w[0]["start_char"]
        last = list_w[-1]
        end = last["start_char"] + len(last["word"])
        c_idx = list_w[0]["chapter_idx"]

        while start > 0 and text[start - 1] in "\"'(«[—–-":
            start -= 1
        while end < len(text) and text[end] in '."?!\'")]:;…—–- ':
            if text[end] in "\r\n":
                break
            end += 1
        while end > start and text[end - 1] == " ":
            end -= 1

        para_text = text[start:end]
        para_len = max(1, end - start)

        matches = []
        for m in COLOR_REGEX.finditer(para_text):
            for g_idx in (1, 2):
                tok = m.group(g_idx)
                norm = normalize_color_token(tok)
                if norm:
                    m_start = m.start(g_idx)
                    m_end = m.end(g_idx)
                    left_c = para_text[max(0, m_start - 40) : m_start]
                    right_c = para_text[m_end : min(len(para_text), m_end + 40)]
                    if not is_verb_context(norm, left_c, right_c):
                        matches.append({
                            "start": m_start,
                            "end": m_end,
                            "hex": COLOR_MAP[norm],
                            "color": norm
                        })

        N = len(matches)
        if N == 1:
            paras_segments.append({
                "chapter_idx": c_idx,
                "len": para_len,
                "hex": matches[0]["hex"],
                "color": matches[0]["color"],
                "para_text": para_text,
                "para_idx": pid,
                "match": matches[0]
            })
        elif N > 1:
            for i, match in enumerate(matches):
                seg_start = 0 if i == 0 else (matches[i - 1]["end"] + match["start"]) // 2
                seg_end = para_len if i == N - 1 else (match["end"] + matches[i + 1]["start"]) // 2
                seg_len = max(1, seg_end - seg_start)
                paras_segments.append({
                    "chapter_idx": c_idx,
                    "len": seg_len,
                    "hex": match["hex"],
                    "color": match["color"],
                    "para_text": para_text,
                    "para_idx": pid,
                    "match": match
                })

    by_chapter = defaultdict(list)
    for seg in paras_segments:
        by_chapter[seg["chapter_idx"]].append(seg)

    book_quotes = []
    block_counter = 0

    for ci in sorted(by_chapter.keys()):
        ch_merged = []
        for seg in by_chapter[ci]:
            if ch_merged and ch_merged[-1]["hex"] == seg["hex"]:
                ch_merged[-1]["len"] += seg["len"]
            else:
                ch_merged.append(dict(seg))

        for seg in ch_merged:
            color_name = seg.get("color") or HEX_TO_COLOR_NAME.get(seg["hex"], "color")
            excerpt = clean_excerpt(seg["para_text"], seg["match"]["start"], seg["match"]["end"])
            book_quotes.append({
                "id": block_counter,
                "ch": ci + 1,
                "para": seg["para_idx"] + 1,
                "color": seg["hex"],
                "name": color_name.capitalize(),
                "quote": excerpt
            })
            block_counter += 1

    if expected_preview_tiles is not None and len(expected_preview_tiles) != len(book_quotes):
        print(f"Warning: {book_key} quote count ({len(book_quotes)}) != preview tiles count ({len(expected_preview_tiles)})")

    return book_quotes


def build_quotes(target_book=None):
    previews_path = REPO_ROOT / "gallery_previews.json"
    if not previews_path.exists():
        print(f"Error: {previews_path} not found.", file=sys.stderr)
        return

    with open(previews_path, "r", encoding="utf-8") as f:
        previews = json.load(f)

    gallery_quotes_dir = REPO_ROOT / "gallery" / "quotes"
    gallery_quotes_dir.mkdir(parents=True, exist_ok=True)

    out_path = REPO_ROOT / "gallery_quotes.json"
    existing_quotes = {}
    if out_path.exists():
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                existing_quotes = json.load(f)
        except Exception:
            existing_quotes = {}

    books_to_process = [target_book] if target_book else list(previews.keys())
    processed_count = 0

    for book_key in books_to_process:
        if book_key not in previews:
            print(f"Warning: {book_key} not in gallery_previews.json, skipping.")
            continue

        preview_tiles = [t for ch in previews[book_key] for t in ch]
        quotes = extract_book_quotes(REPO_ROOT, book_key, preview_tiles)
        if quotes is not None:
            per_book_path = gallery_quotes_dir / f"{book_key}.json"
            with open(per_book_path, "w", encoding="utf-8") as f:
                json.dump(quotes, f, ensure_ascii=False, indent=None)

            existing_quotes[book_key] = quotes
            processed_count += 1
            print(f"✓ Processed {book_key}: {len(quotes)} quotes -> {per_book_path.name} ({per_book_path.stat().st_size / 1024:.1f} KB)")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(existing_quotes, f, ensure_ascii=False, indent=None)

    size_kb = out_path.stat().st_size / 1024
    print(f"\nSuccessfully generated {processed_count} book quote file(s).")
    print(f"Updated monolithic {out_path} ({size_kb:.1f} KB, {len(existing_quotes)} books total).")


def main():
    parser = argparse.ArgumentParser(description="Build authentic color block quotes without placeholders.")
    parser.add_argument("book_name", nargs="?", default=None, help="Optional book key to process. If omitted, all books are processed.")
    args = parser.parse_args()

    build_quotes(args.book_name)


if __name__ == "__main__":
    main()
