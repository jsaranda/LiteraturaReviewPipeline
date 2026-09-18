"""
Conector para a IEEE Xplore Metadata Search API.
Docs: https://developer.ieee.org/docs

Credencial: variável de ambiente IEEE_API_KEY (ver .env.example).

Chaves recém-criadas aparecem no painel da IEEE com status "waiting"
por um tempo — se a primeira chamada retornar erro de autorização,
espere e tente de novo antes de assumir que algo está errado no código.

LIMITES TÍPICOS DE UMA CHAVE (Metadata Search):
- 10 requisições/segundo
- 200 requisições/dia   <- este é o gargalo real, bem mais apertado que
  Springer (500/dia) e OpenAlex (sem limite prático). Planeje as buscas
  de teste com poucos registros para não gastar a cota à toa.
"""

import os
import sys
import time
import requests

# Garante que a raiz do projeto (pasta que contém config.py) esteja no
# sys.path, não importa de onde/como este script seja executado
# (terminal, botão Run do VS Code, outro diretório etc.)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SEARCH_BLOCKS, YEAR_FROM, YEAR_TO, require_env
from connectors.base import Paper, PAPER_FIELDS

IEEE_SEARCH_URL = "https://ieeexploreapi.ieee.org/api/v1/search/articles"

DAILY_LIMIT = 200
PER_SECOND_LIMIT = 10
SLEEP_BETWEEN_REQUESTS_S = 1 / PER_SECOND_LIMIT * 1.2  # folga de segurança

MAX_RECORDS_PER_CALL = 200  # máximo aceito pela API por chamada


def _build_query() -> str:
    """
    Monta a query no formato aceito pelo parâmetro querytext da IEEE
    Xplore API: operadores AND/OR/NOT, frases entre aspas.
    """
    blocks = []
    for terms in SEARCH_BLOCKS.values():
        quoted = [f'"{t}"' for t in terms]
        or_group = " OR ".join(quoted)
        blocks.append(f"({or_group})")

    return " AND ".join(blocks)


def _article_to_paper(article: dict) -> Paper:
    authors = "; ".join(
        a.get("full_name", "")
        for a in (article.get("authors", {}) or {}).get("authors", []) or []
    )
    return Paper(
        source_db="ieee_xplore",
        title=article.get("title", "") or "",
        authors=authors,
        year=article.get("publication_year"),
        venue=article.get("publication_title", "") or "",
        doi=article.get("doi", "") or "",
        abstract=article.get("abstract", "") or "",
        url=article.get("html_url", "") or "",
        raw_id=str(article.get("article_number", "")),
        query_used="ieee_metadata_search",
    )


def search_ieee(start_record: int = 1, max_records: int | None = None) -> list[Paper]:
    """
    Busca paginada na IEEE Xplore Metadata Search API, respeitando o
    limite diário de 200 requisições. `start_record` permite retomar de
    onde parou em outro dia caso o limite seja atingido antes de
    terminar a busca completa.
    """
    query = _build_query()

    papers: list[Paper] = []
    requests_made = 0
    current_start = start_record

    while True:
        if requests_made >= DAILY_LIMIT:
            print(
                f"Limite diário de {DAILY_LIMIT} requisições atingido. "
                f"Pare por hoje e retome amanhã com start_record={current_start}."
            )
            break

        params = {
            "apikey": require_env("IEEE_API_KEY"),
            "querytext": query,
            "start_record": current_start,
            "max_records": MAX_RECORDS_PER_CALL,
        }
        if YEAR_FROM:
            params["start_year"] = YEAR_FROM
        if YEAR_TO:
            params["end_year"] = YEAR_TO

        resp = requests.get(IEEE_SEARCH_URL, params=params, timeout=30)
        requests_made += 1
        resp.raise_for_status()
        data = resp.json()

        articles = data.get("articles", [])
        for article in articles:
            papers.append(_article_to_paper(article))

        total_records = int(data.get("total_records", 0))

        if requests_made == 1:
            print(f"Total de resultados na IEEE Xplore para esta query: {total_records}")

        print(f"  ...{len(papers)}/{total_records} registros baixados "
              f"({requests_made}/{DAILY_LIMIT} requisições usadas)", flush=True)

        current_start += MAX_RECORDS_PER_CALL

        if not articles or current_start > total_records:
            break
        if max_records and len(papers) >= max_records:
            papers = papers[:max_records]
            break

        time.sleep(SLEEP_BETWEEN_REQUESTS_S)

    print(f"Requisições usadas nesta execução: {requests_made}/{DAILY_LIMIT}")
    return papers


if __name__ == "__main__":
    import csv
    import os

    # Busca completa (sem limite). Cada requisição já traz até 200
    # registros, então isso só vira problema se o total de resultados
    # passar de ~40.000 (200 req/dia x 200 registros/req) — bem
    # improvável para esta query. O script para sozinho e avisa de onde
    # retomar amanhã caso bata o limite diário.
    results = search_ieee()
    print(f"Total de registros obtidos: {len(results)}")

    out_path = os.path.join("data", "raw", "ieee_xplore_results.csv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PAPER_FIELDS)
        writer.writeheader()
        for p in results:
            writer.writerow(p.to_dict())
    print(f"Salvo em {out_path}")
