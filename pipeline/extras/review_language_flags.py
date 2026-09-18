"""
Lista os títulos sinalizados como não-inglês pelo 04_check_language.py,
agrupados por idioma detectado, pra revisão manual rápida direto no
terminal (sem precisar abrir o CSV).

Rode: python pipeline/extras/review_language_flags.py
Ou, pra ver só um idioma específico: python pipeline/extras/review_language_flags.py de
"""

import csv
import os
import sys

IN_PATH = os.path.join("data", "processed", "language_check.csv")

lang_filter = sys.argv[1] if len(sys.argv) > 1 else None

by_lang = {}
with open(IN_PATH, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        lang = row.get("detected_language", "")
        if lang == "en":
            continue
        if lang_filter and lang != lang_filter:
            continue
        by_lang.setdefault(lang, []).append(row)

for lang, rows in sorted(by_lang.items(), key=lambda x: -len(x[1])):
    print(f"\n=== {lang} ({len(rows)} registros) ===")
    for row in rows[:15]:  # só os 15 primeiros de cada idioma, pra não poluir
        print(f"  [{row.get('source_db')}] {row.get('title')}")
    if len(rows) > 15:
        print(f"  ... e mais {len(rows) - 15}")