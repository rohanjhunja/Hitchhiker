#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.process_book import process_book

if __name__ == "__main__":
    book_dir = Path(__file__).resolve().parent
    process_book(book_dir)
