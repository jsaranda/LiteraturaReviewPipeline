"""
Gera a tabela de funil por base, no formato do fluxograma de referência
(Initial Search -> Impurity Removal -> Filter by Title -> Filter by
Abstract -> Combination), lendo os CSVs intermediários que já foram
gerados. Isso é só um RELATÓRIO — não recalcula nada, só agrupa por
source_db o que já está nos arquivos.

Rode depois de cada etapa (impurity, title, abstract) para conferir os
números por base antes de fazer a Combination final.

Os números da coluna "Initial Search" (total retornado por cada base
na busca inicial, já com o filtro de data) não são recalculados aqui —
eles vêm de data/initial_search_counts.json, que você preenche à mão
com o que cada base/conector reportou (os connectors/diagnostics/
*_count_check.py ajudam a obter esses totais). Se o arquivo não existir,
a coluna é preenchida com a contagem do pool bruto (01_build_raw_pool).

Rode: python pipeline/extras/report_per_base_funnel.py
"""

import csv
import json
import os

INITIAL_SEARCH_PATH = os.path.join("data", "initial_search_counts.json")
RAW_POOL_PATH = os.path.join("data", "processed", "raw_pool_no_dedup.csv")


def load_initial_search() -> dict:
    if os.path.exists(INITIAL_SEARCH_PATH):
        with open(INITIAL_SEARCH_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {k: int(v) for k, v in data.items() if not k.startswith("_")}
    print(f"(aviso) {INITIAL_SEARCH_PATH} não encontrado — usando a contagem do pool bruto "
          f"como 'Initial Search'.\n")
    return count_by_source(RAW_POOL_PATH)


def count_by_source(path: str) -> dict:
    counts = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            source = row.get("source_db", "desconhecido")
            counts[source] = counts.get(source, 0) + 1
    return counts


def print_funnel_table(stages: dict, initial_search: dict) -> None:
    """
    stages: {"Nome da Etapa": {source_db: count}, ...}, em ordem.
    A coluna "Initial" vem de initial_search.
    """
    stage_names = list(stages.keys())
    all_sources = sorted(initial_search.keys())

    col_width = 14
    header = f"{'Base':<18}" + "".join(f"{s:>{col_width}}" for s in ["Initial"] + stage_names)
    print(header)
    print("-" * len(header))

    totals = {"Initial": 0}
    for name in stage_names:
        totals[name] = 0

    for source in all_sources:
        row = f"{source:<18}"
        initial = initial_search[source]
        row += f"{initial:>{col_width}}"
        totals["Initial"] += initial
        for name in stage_names:
            count = stages[name].get(source, 0)
            row += f"{count:>{col_width}}"
            totals[name] += count
        print(row)

    print("-" * len(header))
    row = f"{'TOTAL':<18}{totals['Initial']:>{col_width}}"
    for name in stage_names:
        row += f"{totals[name]:>{col_width}}"
    print(row)

    # % filtrado por etapa (relativo à etapa anterior)
    print()
    prev_key = "Initial"
    for name in stage_names:
        prev_total = totals[prev_key]
        pct = (1 - totals[name] / prev_total) * 100 if prev_total else 0
        print(f"% filtrado em '{name}' (total): {pct:.2f}%")
        prev_key = name


if __name__ == "__main__":
    stages = {}

    # (nome da coluna, arquivo gerado pela etapa correspondente)
    stage_files = [
        ("Impurity Removal", os.path.join("data", "processed", "after_language_filter.csv")),
        ("Filter by Title", os.path.join("data", "processed", "after_title_filter_clean.csv")),
        ("Filter by Abstract", os.path.join("data", "processed", "after_abstract_filter.csv")),
    ]
    for name, path in stage_files:
        if os.path.exists(path):
            stages[name] = count_by_source(path)

    print_funnel_table(stages, load_initial_search())