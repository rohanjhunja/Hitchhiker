#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unified Automated Book & Screenplay Processing Pipeline for Hitchhikers Repository.
Supports both standard prose (novels, classics) and screenplays (INT./EXT. script formats).
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
SUFFIX_PAT = r'(?:-ish|ish|-ened|ened|-dened|dened|-ening|ening|-dening|dening|-ness|ness|-dness|dness|-ed|ed|-ded|ded|-ing|ing|-ding|ding|-en|en|-den|den|-y|y)?'

COLOR_REGEX = re.compile(
    rf'(?:^|[^A-Za-z])((?:{TOKEN_PAT}){SUFFIX_PAT})(?=[^A-Za-z]|$)(?:[\-/]((?:{TOKEN_PAT}){SUFFIX_PAT})(?=[^A-Za-z]|$))?',
    re.IGNORECASE
)

def normalize_color_token(tok):
    if not tok:
        return None
    t = tok.lower()
    t = re.sub(r'[^a-z]', '', t)
    if t in CANON_KEYS:
        return 'gray' if t == 'grey' else t
    suffixes = ['ening', 'ened', 'dening', 'dened', 'ness', 'dness', 'ish', 'ing', 'ding', 'ed', 'ded', 'en', 'den', 'y']
    for suf in suffixes:
        if t.endswith(suf):
            cand = t[:-len(suf)]
            if cand == 'grey':
                cand = 'gray'
            if cand in CANON_KEYS:
                return cand
    return None

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

def is_screenplay_format(text):
    scene_pattern = re.compile(r'^(?:INT/EXT\.|EXT/INT\.|INT\.|EXT\.)(?:\s|$)', re.MULTILINE | re.IGNORECASE)
    return len(scene_pattern.findall(text)) >= 5

# --- Screenplay Parsing Helpers ---
def get_clean_location(header):
    s = re.sub(r'^(?:INT/EXT\.|EXT/INT\.|INT\.|EXT\.)(?:\s*)', '', header, flags=re.IGNORECASE)
    s = re.sub(r'\s+\d+(?:\s+\d+)*\s*$', '', s)
    time_words = ['DAY', 'NIGHT', 'DUSK', 'AFTERNOON', 'EVENING', 'DAWN', 'MORNING', 'MIDNIGHT']
    for tw in time_words:
        s = re.sub(rf'(?:\.|\s+)?\b{tw}\b.*$', '', s, flags=re.IGNORECASE)
        s = re.sub(rf'(?:\.|\s+)?\b{tw}\d+.*$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'[\.\s\d]+$', '', s)
    return s.split('-')[0].strip().upper()

def is_character_name(stripped):
    if not stripped or not stripped.isupper():
        return False
    if any(stripped.startswith(p) for p in ["INT.", "EXT.", "INT/EXT.", "EXT/INT.", "CUT TO", "FADE "]):
        return False
    if stripped in ["ON BLACK", "THE END", "Super:", "FADE IN:", "FADE OUT."]:
        return False
    return len(stripped) <= 40

def detect_screenplay_chapters(text):
    scene_pattern = re.compile(r'^(?:INT/EXT\.|EXT/INT\.|INT\.|EXT\.)(?:\s|$).*$', re.MULTILINE | re.IGNORECASE)
    scene_matches = list(scene_pattern.finditer(text))
    
    if not scene_matches:
        return [(0, len(text), 0)]

    scenes = [{"start": m.start(), "header": m.group(0).strip(), "location": get_clean_location(m.group(0).strip())} for m in scene_matches]
    N = max(3, len(scenes) // 15)

    scene_to_chapter = {}
    current_chapter = 0
    current_chapter_scenes = []

    for idx, scene in enumerate(scenes):
        current_chapter_scenes.append(scene)
        scene_to_chapter[idx] = current_chapter
        if len(current_chapter_scenes) >= N:
            if idx + 1 < len(scenes) and scenes[idx + 1]["location"] == scene["location"]:
                continue
            current_chapter += 1
            current_chapter_scenes = []

    spans = []
    for idx, scene in enumerate(scenes):
        start = scene["start"]
        end = scenes[idx + 1]["start"] if idx + 1 < len(scenes) else len(text)
        spans.append((start, end, scene_to_chapter[idx]))
    return spans

def detect_screenplay_paragraphs(text):
    lines = []
    last = 0
    for m in re.finditer(r'(.*)\r?\n', text):
        lines.append((last, m.end(), m.group(1)))
        last = m.end()
    if last < len(text):
        lines.append((last, len(text), text[last:]))

    paragraphs = []
    current_para_start = None
    current_para_end = None
    state = "INTRO"

    for start, end, content in lines:
        stripped = content.strip()
        if not stripped:
            continue
        is_header = bool(re.match(r'^(?:INT/EXT\.|EXT/INT\.|INT\.|EXT\.)(?:\s|$)', stripped, re.IGNORECASE))
        is_transition = bool(re.match(r'^(?:CUT TO:|FADE IN:|FADE OUT\.|ON BLACK)$', stripped, re.IGNORECASE))

        if state == "INTRO":
            if is_header:
                state = "ACTION"
                if current_para_start is not None:
                    paragraphs.append((current_para_start, current_para_end))
                current_para_start = start
                current_para_end = end
            else:
                paragraphs.append((start, end))
            continue

        if is_header or is_transition:
            if current_para_start is not None:
                paragraphs.append((current_para_start, current_para_end))
            paragraphs.append((start, end))
            current_para_start = None
            current_para_end = None
            state = "ACTION"
        elif is_character_name(stripped):
            if current_para_start is not None:
                paragraphs.append((current_para_start, current_para_end))
            current_para_start = start
            current_para_end = end
            state = "DIALOGUE"
        else:
            if current_para_start is None:
                current_para_start = start
            current_para_end = end

    if current_para_start is not None:
        paragraphs.append((current_para_start, current_para_end))
    return paragraphs

# --- Standard Prose Parsing Helpers ---
def detect_prose_chapters(text):
    pattern = re.compile(
        r'^\s*(_?\s*(?:BOOK|Book|CHAPTER|Chapter)\b.*_?|PREFACE TO FIRST EDITION|PREFACE TO SECOND EDITION|FOOTNOTES:|^\s*=\s*=\s*=\s*=\s*=\s*=$)\s*$',
        re.MULTILINE
    )
    raw_starts = [m.start() for m in pattern.finditer(text)]
    if not raw_starts:
        return [(0, len(text), 0)]

    toc_cutoff = 0
    if len(raw_starts) >= 3:
        close_count = sum(1 for i in range(min(5, len(raw_starts)-1)) if raw_starts[i+1] - raw_starts[i] < 200)
        if close_count >= 2:
            for i in range(len(raw_starts)-1):
                if raw_starts[i+1] - raw_starts[i] > 300:
                    toc_cutoff = raw_starts[i+1]
                    break

    starts = [s for s in raw_starts if s >= toc_cutoff]
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

def detect_prose_paragraphs(text):
    para_split = re.compile(r'(?:\r?\n){2,}|(?:\r?\n)(?=\s{2,}\S)')
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

    screenplay = is_screenplay_format(text)
    if screenplay:
        print("Format detected: Screenplay (Scene/Dialogue parsing mode)")
        chapter_spans = detect_screenplay_chapters(text)
        para_spans = detect_screenplay_paragraphs(text)
    else:
        print("Format detected: Standard Prose / Novel")
        chapter_spans = detect_prose_chapters(text)
        para_spans = detect_prose_paragraphs(text)

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

DETERMINERS_PREP_PAT = r'\b(?:a|an|the|this|that|these|those|my|his|her|its|their|your|our|some|any|each|every|no|all|many|few|much|more|most|of|in|with|into|like|as|under|upon|over|through|pale|deep|dark|light|bright|soft|vivid|rich|dull|warm|cool|pure|faint|heavy|fine|coarse|dry|wet|wild|sweet|red|blue|green|yellow|white|bed\s+of)\s*$'
ACTION_AUXILIARY_PAT = r'\b(?:will|would|shall|should|can|could|may|might|must|to|do|did|does)\s*$'
LINKING_VERBS_PAT = r'\b(?:is|are|was|were|be|been|being|became|turned|grew|looked|felt|seemed)\s*$'
SUBJECT_PRONOUNS_PAT = r'\b(?:he|she|it|they|we|you|i|who)\s*$'
PHRASAL_PARTICLES_PAT = r'^\s*(?:up|off|out|away|down|over|back|again)\b'

def is_verb_context(token, left_ctx, right_ctx):
    token_lower = token.lower()
    left_str = left_ctx.lower().strip()
    right_str = right_ctx.lower().strip()

    # 1. Determiners, possessives, prepositions of containment/association, or color modifiers -> ALWAYS COLOR/NOUN
    if re.search(DETERMINERS_PREP_PAT, left_str):
        return False

    # 2. Compound adjectives or compound noun contexts -> ALWAYS COLOR/NOUN
    if re.search(r'^(?:-colored|-coloured|-tinted|-pink|-red|-velvet|-silk|-satin|-hue|-shade|colored|coloured|tinted|shade|hue|petals|hips|water|garden|bush|tree|skin|eyes|hair|cloak|coat|dress|wall|sky|sand|sword|ring|leaves|stone|sea|ocean|desert)\b', right_str):
        return False

    # 3. Linking verbs (was tan, turned pale, grew dark, looked silver) -> COLOR/ADJECTIVE
    if re.search(LINKING_VERBS_PAT, left_str):
        return False

    # 4. Action auxiliary verbs (will rust, to dust, did brown, would tan) -> VERB
    if re.search(ACTION_AUXILIARY_PAT, left_str):
        return True

    # 5. Phrasal verb particles on right context (black out, rose up, dusted off, rusted away) -> VERB
    if re.search(PHRASAL_PARTICLES_PAT, right_str):
        return True

    # 6. Subject pronouns performing active verb functions -> VERB
    if re.search(SUBJECT_PRONOUNS_PAT, left_str):
        if token_lower in ['rose', 'dust', 'rust', 'tan', 'brown']:
            return True

    # 7. Specific past-tense noun subjects performing action 'rose' (sun rose, smoke rose, tide rose)
    if token_lower == 'rose':
        if re.search(r'\b(?:sun|smoke|wind|crowd|voice|tide|dust|figure|curtain|flame|fire|heat)\s*$', left_str):
            return True
        if re.search(r'^\s*(?:from|into|onto|upon|above|to)\b', right_str):
            return True

    return False

def update_gallery_previews(repo_root, book_name, text, words):
    by_para = defaultdict(list)
    for r in words:
        by_para[r['paragraph_idx']].append(r)

    paras_segments = []
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
        para_len = max(1, end - start)

        matches = []
        for m in COLOR_REGEX.finditer(para_text):
            for g_idx in (1, 2):
                tok = m.group(g_idx)
                norm = normalize_color_token(tok)
                if norm:
                    m_start = m.start(g_idx)
                    m_end = m.end(g_idx)
                    left_c = para_text[max(0, m_start-40):m_start]
                    right_c = para_text[m_end:min(len(para_text), m_end+40)]
                    if not is_verb_context(norm, left_c, right_c):
                        matches.append({'start': m_start, 'end': m_end, 'hex': COLOR_MAP[norm]})

        N = len(matches)
        if N == 1:
            paras_segments.append({'chapter_idx': c_idx, 'len': para_len, 'hex': matches[0]['hex']})
        elif N > 1:
            for i, match in enumerate(matches):
                seg_start = 0 if i == 0 else (matches[i-1]['end'] + match['start']) // 2
                seg_end = para_len if i == N - 1 else (match['end'] + matches[i+1]['start']) // 2
                seg_len = max(1, seg_end - seg_start)
                paras_segments.append({'chapter_idx': c_idx, 'len': seg_len, 'hex': match['hex']})

    by_chapter = defaultdict(list)
    for seg in paras_segments:
        by_chapter[seg['chapter_idx']].append(seg)

    book_preview = []
    for ci in sorted(by_chapter.keys()):
        ch_merged = []
        for seg in by_chapter[ci]:
            if ch_merged and ch_merged[-1][1] == seg['hex']:
                ch_merged[-1][0] += seg['len']
            else:
                ch_merged.append([seg['len'], seg['hex']])
        book_preview.append(ch_merged)

    previews_path = repo_root / "gallery_previews.json"
    if previews_path.exists():
        previews = json.loads(previews_path.read_text(encoding='utf-8'))
    else:
        previews = {}

    previews[book_name] = book_preview
    previews_path.write_text(json.dumps(previews, ensure_ascii=False), encoding='utf-8')
    print(f"Updated {previews_path} for '{book_name}' ({len(book_preview)} chapters).")

def update_index_html(repo_root, book_name, title, author):
    for filename in ["index.html", "viewer.html"]:
        index_path = repo_root / filename
        if not index_path.exists():
            continue

        html = index_path.read_text(encoding='utf-8')
        if f'data-book="{book_name}"' in html:
            print(f"Poster card for '{book_name}' already exists in {filename}.")
            continue

        css_class = "poster-" + re.sub(r'[^a-z0-9]+', '-', book_name.lower()).strip('-')
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
            print(f"Added poster card for '{title}' to {filename}.")

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
    ap.add_argument("book_dir", help="Directory of the book or screenplay")
    ap.add_argument("--title", help="Display title of the book for index.html card")
    ap.add_argument("--author", help="Author name of the book for index.html card")
    args = ap.parse_args()

    process_book(args.book_dir, title=args.title, author=args.author)

if __name__ == "__main__":
    main()
