#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import csv
import re
from pathlib import Path

# --- Helper Screenplay Parsing Functions ---

def get_clean_location(header):
    # Remove INT., EXT. etc.
    s = re.sub(r'^(?:INT/EXT\.|EXT/INT\.|INT\.|EXT\.)(?:\s*)', '', header, flags=re.IGNORECASE)
    # Strip trailing numbers, e.g. " 15 15" or "1 1"
    s = re.sub(r'\s+\d+(?:\s+\d+)*\s*$', '', s)
    # Strip trailing time of day words and their variations
    time_words = ['DAY', 'NIGHT', 'DUSK', 'AFTERNOON', 'EVENING', 'DAWN', 'MORNING', 'MIDNIGHT']
    for tw in time_words:
        s = re.sub(rf'(?:\.|\s+)?\b{tw}\b.*$', '', s, flags=re.IGNORECASE)
        s = re.sub(rf'(?:\.|\s+)?\b{tw}\d+.*$', '', s, flags=re.IGNORECASE)
    
    # Strip trailing dots, scene suffixes, whitespace
    s = re.sub(r'[\.\s\d]+$', '', s)
    
    # Extract base location if there is a dash (e.g. "MCCLUSKIEGUNJ HOUSE - LIVING ROOM" -> "MCCLUSKIEGUNJ HOUSE")
    base_loc = s.split('-')[0].strip()
    return base_loc.upper()

def is_character_name(stripped):
    if not stripped:
        return False
    if not stripped.isupper():
        return False
    # Exclude scene headers and transitions
    if any(stripped.startswith(p) for p in ["INT.", "EXT.", "INT/EXT.", "EXT/INT.", "CUT TO", "FADE "]):
        return False
    if stripped in ["ON BLACK", "THE END", "Super:", "FADE IN:", "FADE OUT."]:
        return False
    if len(stripped) > 40:
        return False
    return True

def is_action_line(content):
    stripped = content.strip()
    if not stripped:
        return False
    # If starts with a Title Case character name followed by space
    for name in ["Nandu", "Brian", "Shutu", "Bonnie", "Mimi", "Tani", "Mrs Curney", "Mr Curney", "Maniya", "Manjari", "Vikram", "Aunty", "Uncle"]:
        if stripped.startswith(name) and not stripped.isupper():
            return True
    # Common action starters
    starters = ["They ", "He ", "She ", "The ", "A ", "An ", "Inside ", "Through ", "In ", "On ", "Their ", "As ", "We "]
    if any(stripped.startswith(s) for s in starters) and len(stripped) > 40:
        return True
    return False

# --- Core Indexing Functions ---

def detect_scenes_and_chapters(text):
    # Scene Heading regex
    scene_pattern = re.compile(r'^(?:INT/EXT\.|EXT/INT\.|INT\.|EXT\.)(?:\s|$).*$', re.MULTILINE | re.IGNORECASE)
    scene_matches = list(scene_pattern.finditer(text))
    
    scenes = []
    for m in scene_matches:
        header = m.group(0).strip()
        clean_loc = get_clean_location(header)
        scenes.append({
            "start": m.start(),
            "header": header,
            "location": clean_loc
        })
    
    if not scenes:
        # Fallback: treat whole text as 1 scene in 1 chapter
        return [(0, len(text), 0)]
    
    # Calculate dynamic target block size N
    total_scenes = len(scenes)
    N = max(3, total_scenes // 15)
    
    # Group scenes into chapters with location preservation
    scene_to_chapter = {}
    current_chapter = 0
    current_chapter_scenes = []
    
    for idx, scene in enumerate(scenes):
        current_chapter_scenes.append(scene)
        scene_to_chapter[idx] = current_chapter
        
        # Check if we should close the chapter
        if len(current_chapter_scenes) >= N:
            if idx + 1 < len(scenes):
                next_scene = scenes[idx + 1]
                if next_scene["location"] == scene["location"]:
                    # Location matches, keep it in the current chapter
                    continue
            current_chapter += 1
            current_chapter_scenes = []
            
    # Map scenes to actual text spans
    spans = []
    for idx, scene in enumerate(scenes):
        start = scene["start"]
        end = scenes[idx + 1]["start"] if idx + 1 < len(scenes) else len(text)
        chapter_idx = scene_to_chapter[idx]
        spans.append((start, end, chapter_idx))
        
    return spans

def detect_paragraphs(text):
    # Extract line character ranges
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
        elif state == "DIALOGUE":
            if is_action_line(content):
                if current_para_start is not None:
                    paragraphs.append((current_para_start, current_para_end))
                current_para_start = start
                current_para_end = end
                state = "ACTION"
            else:
                current_para_end = end
        else: # state == "ACTION"
            if current_para_start is None:
                current_para_start = start
            current_para_end = end
            
    if current_para_start is not None:
        paragraphs.append((current_para_start, current_para_end))
        
    return paragraphs

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
        
    chapter_spans = detect_scenes_and_chapters(text)
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
        description="Build screenplay word index (CSV + JSON) from a screenplay text file."
    )
    ap.add_argument("input_txt", help="Path to the input screenplay .txt file")
    ap.add_argument("--csv", default="hhgttg_word_index.csv", help="Output CSV path")
    ap.add_argument("--json", default="hhgttg_word_index.json", help="Output JSON path")
    ap.add_argument("--keep-hyphens", action="store_true",
                    help="Treat hyphenated words as a single token")
    args = ap.parse_args()
    
    text = Path(args.input_txt).read_text(encoding="utf-8", errors="ignore")
    rows = build_index(text, keep_hyphens=args.keep_hyphens)
    write_csv(rows, args.csv)
    write_json(rows, args.json)
    
    print(f"Done.\nCSV : {args.csv}\nJSON: {args.json}\nWords indexed: {len(rows)}")

if __name__ == "__main__":
    main()
