"""
Busca e funde os resultados de TODOS os batches ainda não recuperados,
registrados por 06_llm_title_screening_submit.py — funciona de forma
cumulativa: pode ser rodado depois de cada execução do submit, e o CSV
de resultado sempre reflete o progresso total até agora.

Rode de novo a qualquer momento para atualizar o progresso.
"""

import csv
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic

from config import LLM_MODEL, require_env

IN_PATH = os.path.join("data", "processed", "after_language_filter.csv")
REGISTRY_PATH = os.path.join("data", "processed", "title_screening_batches_registry.json")
RESULTS_PATH = os.path.join("data", "processed", "title_screening_results.csv")


def extract_json_array(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    return text


def main():
    if not os.path.exists(REGISTRY_PATH):
        print("Nenhum batch foi enviado ainda. Rode 06_llm_title_screening_submit.py primeiro.")
        return

    with open(REGISTRY_PATH, encoding="utf-8") as f:
        registry = json.load(f)

    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    fieldnames_out = fieldnames + ["title_decision", "title_reason"]

    # Carrega decisões já salvas de execuções anteriores (não perde nada)
    decisions = {}
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH, encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f)):
                if row.get("title_decision") not in ("", "NAO_PROCESSADO", None):
                    decisions[i] = {"decision": row["title_decision"], "reason": row.get("title_reason", "")}

    client = anthropic.Anthropic(api_key=require_env("ANTHROPIC_API_KEY"))
    any_updated = False

    for entry in registry:
        if entry["retrieved"]:
            continue

        batch = client.messages.batches.retrieve(entry["batch_id"])
        print(f"Batch {entry['batch_id']}: status={batch.processing_status}")

        if batch.processing_status != "ended":
            continue

        for result in client.messages.batches.results(entry["batch_id"]):
            custom_id = result.custom_id
            if result.result.type != "succeeded":
                print(f"  [FALHOU] {custom_id}: {result.result.type}")
                continue

            message = result.result.message
            text = "".join(b.text for b in message.content if b.type == "text")
            cleaned = extract_json_array(text)

            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as e:
                print(f"  [ERRO DE PARSE] {custom_id}: {e}")
                continue

            idx_group = entry["chunk_map"][custom_id]
            for item in parsed:
                i = item.get("i")
                if i is None or i < 1 or i > len(idx_group):
                    continue
                row_idx = idx_group[i - 1]
                decisions[row_idx] = {"decision": item.get("d", ""), "reason": item.get("r", "")}

        entry["retrieved"] = True
        any_updated = True

    if any_updated:
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(registry, f)

    with open(RESULTS_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_out)
        writer.writeheader()
        for idx, row in enumerate(rows):
            d = decisions.get(idx, {"decision": "NAO_PROCESSADO", "reason": ""})
            row["title_decision"] = d["decision"]
            row["title_reason"] = d["reason"]
            writer.writerow(row)

    n_total = len(rows)
    n_done = len(decisions)
    print(f"\nProgresso total: {n_done}/{n_total} ({n_done/n_total*100:.1f}%)")
    print("Distribuição até agora:", dict(Counter(d["decision"] for d in decisions.values())))
    print(f"\nResultado atualizado em {RESULTS_PATH}")


if __name__ == "__main__":
    main()