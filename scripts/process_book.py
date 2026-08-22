#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Automated Book Processing Pipeline for Hitchhikers Repository.
Cleans raw text, builds word index (CSV/JSON), updates gallery_previews.json,
and registers poster cards in index.html deterministically.
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

COLOR_MAP = {
    'red': '#ef4444', 'crimson': '#dc2626', 'scarlet': '#f43f5e', 'maroon': '#7f1d1d',
    'ruby': '#e0115f', 'rose': '#ff007f', 'coral': '#fb7185', 'pink': '#f472b6',
    'magenta': '#ec4899', 'rust': '#b7410e', 'copper': '#b87333', 'bronze': '#cd7f32',
    'auburn': '#a52a2a', 'mahogany': '#c04000', 'chestnut': '#954535', 'orange': '#fb923c',
    'peach': '#fdba74', 'amber': '#f59e0b', 'gold': '#f59e0b', 'yellow': '#eab308',
    'mustard': '#ffdb58', 'ochre': '#cc7722', 'ocher': '#cc7722', 'green': '#22c55e',
    'lime': '#84cc16', 'olive': '#4d7c0f', 'emerald': '#50c878', 'teal': '#0d9488',
    'blue': '#3b82f6', 'navy': '#1e3a8a', 'azure': '#0ea5e9', 'cyan': '#06b6d4',
    'sapphire': '#0f52ba', 'turquoise': '#40e0d0', 'indigo': '#6366f1', 'purple': '#a855f7',
    'violet': '#8b5cf6', 'lavender': '#c4b5fd', 'plum': '#8e4585', 'lilac': '#c8a2c8',
    'brown': '#a16207', 'beige': '#f5f5dc', 'tan': '#d2b48c', 'khaki': '#c3b091',
    'sand': '#d4b886', 'dust': '#b0a48a', 'sepia': '#704214', 'chocolate': '#7b3f00',
    'hazel': '#8e7618', 'cream': '#fffdd0', 'black': '#111827', 'ebony': '#282828',
    'charcoal': '#36454f', 'white': '#e5e7eb', 'ivory': '#fffff0', 'snow': '#f8f9fa',
    'pearl': '#eaedec', 'gray': '#6b7280', 'grey': '#6b7280', 'silver': '#9ca3af',
    'ash': '#b2beb5', 'slate': '#708090', 'brass': '#b5a642'
}

CANON_KEYS = [k if k != 'grey' else 'gray' for k in COLOR_MAP.keys()]
TOKENS = sorted(list(set(CANON_KEYS)), key=lambda x: -len(x))
ESCAPED_TOKENS = [re.escape(k) for k in TOKENS]
TOKEN_PAT = '|'.join(ESCAPED_TOKENS)

COLOR_REGEX = re.compile(
    rf'(?:^|[^A-Za-z])((?:{TOKEN_PAT})(?:-ish|ish)?)(?=[^A-Za-z]|$)(?:[\-/]((?:{TOKEN_PAT})(?:-ish|ish)?)(?=[^A-Za-z]|$))?',
    re.IGNORECASE
)

def normalize_color_token(tok):
    if not tok:
        return None
    t = tok.lower()
    t = re.sub(r'[^a-z]', '', t)
    if t.endswith('ish') and len(t) > 4:
        t = t[:-3]
    if t == 'grey':
        t = 'gray'
    return t if t in CANON_KEYS else None

def clean_text(text):
    lines = text.splitlines()
    start_i = 0
    end_i = len(lines)
    for i, line in enumerate(lines):
        if '*** START OF THE PROJECT GUTENBERG EBOOK' in line or '*** START OF THIS PROJECT GUTENBERG EBOOK' in line:
            start_i = i
        if '*** END OF THE PROJECT GUTENBERG EBOOK' in line or '*** END OF THIS PROJECT GUTENBERG EBOOK' in line:
            end_i = i + 1

    clean_lines = lines[start_i:end_i]
    return '\n'.join(clean_lines) + '\n'

def detect_chapters(text):
    pattern = re.compile(
        r'^\s*(BOOK\s+[I|V|X|L|C|D|M]+\b|Book\s+\d+|CHAPTER\b.*|Chapter\b.*|PREFACE TO FIRST EDITION|PREFACE TO SECOND EDITION|FOOTNOTES:|^\s*=\s*=\s*=\s*=\s*=\s*=$)\s*$',
        re.MULTILINE
    )
    starts = []
    for m in pattern.finditer(text):
        line_num = text[:m.start()].count('\n') + 1
        if line_num >= 45 or '==' in m.group(0):
            starts.append(m.start())

    starts.sort()
    if not starts:
        return [(0, len(text), 0)]

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
    para_split = re.compile(r'(?:\r?\n){2,}')
    spans = []
    last = 0
    for m in para_split.finditer(text):
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
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["word_idx", "start_char", "word", "paragraph_idx", "chapter_idx"]
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

def write_json(rows, out_json):
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

def update_gallery_previews(repo_root, book_name, text, words):
    by_para = defaultdict(list)
    for r in words:
        by_para[r['paragraph_idx']].append(r)

    paras = []
    for pid in sorted(by_para.keys()):
        list_w = sorted(by_para[pid], key=lambda x: x['start_char'])
        start = list_w[0]['start_char']
        last = list_w[-1]
        end = last['start_char'] + len(last['word'])
        c_idx = list_w[0]['chapter_idx']

        while start > 0 and text[start-1] in '\"\'(«[—–-':
            start -= 1
        while end < len(text) and text[end] in '.\"?!\'\")]:;…—–- ':
            if text[end] in '\r\n':
                break
            end += 1
        while end > start and text[end-1] == ' ':
            end -= 1

        para_text = text[start:end]
        counts = defaultdict(int)
        for m in COLOR_REGEX.finditer(para_text):
            a = normalize_color_token(m.group(1))
            b = normalize_color_token(m.group(2))
            if a:
                counts[a] += 1
            if b:
                counts[b] += 1

        sorted_colors = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        color_hex = COLOR_MAP[sorted_colors[0][0]] if sorted_colors else 0
        para_len = end - start

        paras.append({
            'idx': pid,
            'chapter_idx': c_idx,
            'len': para_len,
            'colorHex': color_hex
        })

    by_chapter = defaultdict(list)
    for p in paras:
        by_chapter[p['chapter_idx']].append(p)

    book_preview = []
    for ci in sorted(by_chapter.keys()):
        ch_list = [[p['len'], p['colorHex']] for p in by_chapter[ci]]
        book_preview.append(ch_list)

    previews_path = repo_root / "gallery_previews.json"
    if previews_path.exists():
        previews = json.loads(previews_path.read_text(encoding='utf-8'))
    else:
        previews = {}

    previews[book_name] = book_preview
    previews_path.write_text(json.dumps(previews, ensure_ascii=False), encoding='utf-8')
    print(f"Updated {previews_path} for '{book_name}' ({len(book_preview)} chapters).")

def update_index_html(repo_root, book_name, title, author):
    index_path = repo_root / "index.html"
    if not index_path.exists():
        return

    html = index_path.read_text(encoding='utf-8')
    if f'data-book="{book_name}"' in html:
        print(f"Poster card for '{book_name}' already exists in index.html.")
        return

    css_class = "poster-" + book_name.lower()
    card_html = f'''      <!-- {title} -->
      <a href="?book={book_name}" class="poster-card {css_class}">
        <div class="poster-body">
          <div class="poster-preview" data-book="{book_name}"></div>
          <div class="poster-meta">
            <div class="poster-text">
              <h3 class="poster-title">{title}</h3>
              <div class="poster-author">{author}</div>
            </div>
            <button class="poster-print-btn" title="Download Poster SVG" aria-label="Download Poster SVG">
              <svg viewBox="0 0 24 24"><path d="M6 9V2h12v7"></path><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>
            </button>
          </div>
        </div>
      </a>
      
      <!-- Request a Book Form Card -->'''

    if '<!-- Request a Book Form Card -->' in html:
        new_html = html.replace('<!-- Request a Book Form Card -->', card_html, 1)
        index_path.write_text(new_html, encoding='utf-8')
        print(f"Added poster card for '{title}' to index.html.")
    else:
        print("Warning: Could not find insert point in index.html")

def verify_indices(book_dir, text, rows):
    mismatches = 0
    for w in rows[:500]:
        start = w['start_char']
        expected_word = w['word']
        actual_word = text[start:start+len(expected_word)]
        if actual_word != expected_word:
            mismatches += 1
    if mismatches == 0:
        print("Verification SUCCESS: 100% of tested word offsets match book.txt exactly.")
    else:
        print(f"Warning: {mismatches} mismatches found during offset verification!")

def process_book(book_dir_path, title=None, author=None):
    book_dir = Path(book_dir_path).resolve()
    repo_root = book_dir.parent
    book_name = book_dir.name

    book_txt = book_dir / "book.txt"
    if not book_txt.exists():
        raw_candidates = [f for f in book_dir.glob("*") if f.is_file() and f.suffix in ['.txt', ''] and f.name != 'build_word_index.py']
        if not raw_candidates:
            print(f"Error: No text file found in {book_dir}")
            sys.exit(1)
        raw_file = raw_candidates[0]
        print(f"Cleaning raw file: {raw_file}")
        raw_text = raw_file.read_text(encoding='utf-8', errors='ignore')
        cleaned = clean_text(raw_text)
        book_txt.write_text(cleaned, encoding='utf-8')
        print(f"Created {book_txt}")

    text = book_txt.read_text(encoding='utf-8', errors='ignore').replace("\r\n", "\n").replace("\r", "\n")
    print(f"Indexing {book_txt} ({len(text)} chars)...")
    rows = build_index(text)

    csv_path = book_dir / "hhgttg_word_index.csv"
    json_path = book_dir / "hhgttg_word_index.json"

    write_csv(rows, csv_path)
    write_json(rows, json_path)
    print(f"Indexed {len(rows)} words.\nCSV : {csv_path}\nJSON: {json_path}")

    verify_indices(book_dir, text, rows)

    update_gallery_previews(repo_root, book_name, text, rows)

    if title and author:
        update_index_html(repo_root, book_name, title, author)

def main():
    ap = argparse.ArgumentParser(description="Automate text cleaning, word indexing, gallery preview generation, and index registration.")
    ap.add_argument("book_dir", help="Directory of the book (e.g. Odyssey, Dune, LOTR)")
    ap.add_argument("--title", help="Display title of the book for index.html card")
    ap.add_argument("--author", help="Author name of the book for index.html card")
    args = ap.parse_args()

    process_book(args.book_dir, title=args.title, author=args.author)

if __name__ == "__main__":
    main()
