"""
Busca na internet (OpenAlex e, como fallback, Semantic Scholar) o
abstract dos artigos de uma lista — pensado para os itens que
heuristics/check_abstract_for_list.py marcou como "sem abstract", ou
seja, artigos cujo abstract não veio em nenhuma das bases coletadas.

Não usa nenhuma chave de API: OpenAlex e Semantic Scholar são públicas.
O e-mail OPENALEX_MAILTO (do .env) é enviado à OpenAlex como cortesia.

Entrada aceita (detectada pela extensão):
  .txt  -> mesmo formato das listas em data/heuristic_lists/:
           source_db|~|título|~|ano|~|venue|~|url
  .csv  -> CSV separado por ";" com as colunas
           id;source_db;title;year;venue;link  (com ou sem cabeçalho)

Saída: CSV (separador ";") ao lado do arquivo de entrada, com sufixo
_com_abstracts, colunas id;source_db;title;year;venue;link;has_abstract;abstract.

Uso:
    python heuristics/fetch_abstracts_for_list.py data/heuristic_lists/lista_1.txt
    python heuristics/fetch_abstracts_for_list.py lista.csv
"""

import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import OPENALEX_MAILTO

SLEEP_BETWEEN_ITEMS_S = 0.2  # intervalo de cortesia para as APIs públicas
TIMEOUT_S = 12


def _get_json(url: str, headers: dict) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def reconstruct_openalex_abstract(inverted_index) -> str:
    """Reconstrói o abstract a partir do abstract_inverted_index do OpenAlex."""
    if not inverted_index:
        return ""
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort(key=lambda item: item[0])
    return " ".join(w for _, w in word_positions)


def fetch_from_openalex(title: str, link: str = "") -> str:
    headers = {"User-Agent": f"mailto:{OPENALEX_MAILTO}" if OPENALEX_MAILTO else "lit-review-pipeline"}

    # 1. Link direto do OpenAlex (ex: https://openalex.org/W2980264084)
    openalex_match = re.search(r"(W\d+)", str(link))
    if "openalex.org" in str(link) and openalex_match:
        try:
            data = _get_json(f"https://api.openalex.org/works/{openalex_match.group(1)}", headers)
            abstract = reconstruct_openalex_abstract(data.get("abstract_inverted_index"))
            if abstract:
                return abstract
        except Exception:
            pass

    # 2. DOI presente no link
    doi_match = re.search(r"(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", str(link))
    if doi_match:
        doi = urllib.parse.quote(doi_match.group(1))
        try:
            data = _get_json(f"https://api.openalex.org/works/https://doi.org/{doi}", headers)
            abstract = reconstruct_openalex_abstract(data.get("abstract_inverted_index"))
            if abstract:
                return abstract
        except Exception:
            pass

    # 3. Busca por título
    clean_title = urllib.parse.quote(str(title).strip())
    try:
        data = _get_json(
            f"https://api.openalex.org/works?filter=title.search:{clean_title}&per-page=1", headers
        )
        results = data.get("results", [])
        if results:
            abstract = reconstruct_openalex_abstract(results[0].get("abstract_inverted_index"))
            if abstract:
                return abstract
    except Exception:
        pass

    return ""


def fetch_from_semanticscholar(title: str) -> str:
    clean_title = urllib.parse.quote(str(title).strip())
    url = (
        "https://api.semanticscholar.org/graph/v1/paper/search"
        f"?query={clean_title}&limit=1&fields=title,abstract"
    )
    try:
        data = _get_json(url, {"User-Agent": "lit-review-pipeline/1.0"})
        papers = data.get("data", [])
        if papers and papers[0].get("abstract"):
            return papers[0]["abstract"]
    except Exception:
        pass
    return ""


def load_items(path: str) -> list[dict]:
    """Lê a lista de artigos (.txt no formato |~| ou .csv separado por ';')."""
    items = []
    if path.lower().endswith(".csv"):
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            reader = csv.reader(f, delimiter=";")
            for row in reader:
                if not row or len(row) < 3:
                    continue
                if row[0].strip().lower() == "id" and row[2].strip().lower() == "title":
                    continue  # cabeçalho
                row = row + [""] * 6
                rec_id, source_db, title, year, venue, link = [str(x).strip() for x in row[:6]]
                items.append({"id": rec_id, "source_db": source_db, "title": title,
                              "year": year, "venue": venue, "link": link})
    else:
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, start=1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("|~|")
                if len(parts) != 5:
                    print(f"AVISO: linha mal formatada, pulando: {line[:80]}")
                    continue
                source_db, title, year, venue, link = parts
                items.append({"id": str(len(items) + 1), "source_db": source_db, "title": title,
                              "year": year, "venue": venue, "link": link})
    return items


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    input_path = sys.argv[1]
    if not os.path.isfile(input_path):
        raise SystemExit(f"Arquivo não encontrado: {input_path}")

    base, _ = os.path.splitext(input_path)
    output_path = f"{base}_com_abstracts.csv"

    items = load_items(input_path)
    total = len(items)
    print(f"Arquivo de entrada: {input_path}")
    print(f"Arquivo de saída:   {output_path}")
    print(f"Total de artigos para processar: {total}\n", flush=True)

    fieldnames = ["id", "source_db", "title", "year", "venue", "link", "has_abstract", "abstract"]
    output_rows = []

    for idx, item in enumerate(items, start=1):
        print(f"[{idx}/{total}] Buscando: {item['title'][:70]}...", flush=True)

        abstract = fetch_from_openalex(item["title"], item["link"])
        if not abstract:
            abstract = fetch_from_semanticscholar(item["title"])

        output_rows.append({**item, "has_abstract": "Sim" if abstract else "Nao",
                            "abstract": abstract.strip()})
        time.sleep(SLEEP_BETWEEN_ITEMS_S)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(output_rows)

    found = sum(1 for r in output_rows if r["has_abstract"] == "Sim")
    pct = (found / total * 100) if total else 0
    print(f"\nFINALIZADO! Abstracts encontrados: {found}/{total} ({pct:.1f}%)")
    print(f"Salvo em: {output_path}")


if __name__ == "__main__":
    main()
