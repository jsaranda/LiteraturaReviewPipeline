"""
Busca e funde os resultados de todos os batches ainda não recuperados
do Filter by Abstract.
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

# Entrada: o corpus pós-título já enriquecido com abstracts do Scopus
# (etapa 10). Se a etapa 10 não foi rodada, usa o corpus da etapa 09.
_WITH_ABSTRACTS = os.path.join("data", "processed", "after_title_filter_with_abstracts.csv")
_CLEAN = os.path.join("data", "processed", "after_title_filter_clean.csv")
IN_PATH = _WITH_ABSTRACTS if os.path.exists(_WITH_ABSTRACTS) else _CLEAN
REGISTRY_PATH = os.path.join("data", "processed", "abstract_screening_batches_registry.json")
RESULTS_PATH = os.path.join("data", "processed", "abstract_screening_results.csv")


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
        print("Nenhum batch enviado ainda. Rode 11_llm_abstract_screening_submit.py primeiro.")
        return

    with open(REGISTRY_PATH, encoding="utf-8") as f:
        registry = json.load(f)

    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    fieldnames_out = fieldnames + ["abstract_decision", "abstract_reason"]

    decisions = {}
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH, encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f)):
                if row.get("abstract_decision") in ("include", "exclude"):
                    decisions[i] = {"decision": row["abstract_decision"], "reason": row.get("abstract_reason", "")}

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
            row["abstract_decision"] = d["decision"]
            row["abstract_reason"] = d["reason"]
            writer.writerow(row)

    n_total = len(rows)
    n_done = len(decisions)
    print(f"\nProgresso: {n_done}/{n_total} ({n_done/n_total*100:.1f}%)")
    print("Distribuição:", dict(Counter(d["decision"] for d in decisions.values())))
    print(f"\nResultado em {RESULTS_PATH}")


if __name__ == "__main__":
    main()