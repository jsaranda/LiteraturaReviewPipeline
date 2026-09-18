"""
Conector para a Springer Nature Meta API.
Docs: https://dev.springernature.com/

Credencial: variável de ambiente SPRINGER_API_KEY (ver .env.example).

LIMITES TÍPICOS DE UMA CHAVE GRATUITA (Meta API):
- 100 requisições/minuto
- 500 requisições/dia

Este conector respeita os dois limites: espera entre requisições para
não estourar o limite por minuto, e para automaticamente se o
orçamento diário (500) for atingido — mesmo que a busca completa ainda
não tenha terminado (nesse caso, rode de novo no dia seguinte para
continuar de onde parou, usando o parâmetro `start` da paginação).
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

SPRINGER_META_URL = "https://api.springernature.com/meta/v2/json"

# Limites da chave (ver painel "API management" -> Meta API)
DAILY_LIMIT = 500
PER_MINUTE_LIMIT = 100
# folga de segurança maior que antes: 1.1x (~0.66s) estourou o rate
# limit na prática, então usamos 2x de folga
SLEEP_BETWEEN_REQUESTS_S = 60 / PER_MINUTE_LIMIT * 2  # ~1.2s por chamada

RESULTS_PER_PAGE = 25  # limite real do plano gratuito (descoberto por diagnóstico — 30+ dá 403)

MAX_429_RETRIES = 5       # quantas vezes tenta de novo a mesma página após 429
RETRY_429_WAIT_S = 30     # espera padrão se a API não mandar um Retry-After


def _build_query() -> str:
    """
    Monta a query no formato aceito pela Springer Meta API:
    title:("termo1" OR "termo2") AND title:(...) AND ...
    (a Meta API busca por padrão em título+abstract com o campo bare,
    mas usamos escopo explícito para ficar mais previsível).

    OBS: o filtro de data (onlinedatefrom/onlinedateto) foi removido
    daqui de propósito — ele pode não ser suportado no seu nível de
    acesso e causar 403 Forbidden. O filtro por ano é aplicado depois,
    em Python, sobre os resultados já retornados (ver search_springer).
    """
    blocks = []
    for terms in SEARCH_BLOCKS.values():
        quoted = [f'"{t}"' for t in terms]
        or_group = " OR ".join(quoted)
        blocks.append(f"({or_group})")

    return " AND ".join(blocks)


def _year_in_range(year: int | None) -> bool:
    """Filtro de ano aplicado em Python (não no servidor)."""
    if year is None:
        return True  # sem ano conhecido, não descarta — deixa pra revisão manual
    if YEAR_FROM and year < YEAR_FROM:
        return False
    if YEAR_TO and year > YEAR_TO:
        return False
    return True


def _record_to_paper(record: dict) -> Paper:
    authors = "; ".join(
        c.get("creator", "") for c in record.get("creators", []) or []
    )
    return Paper(
        source_db="springer",
        title=record.get("title", "") or "",
        authors=authors,
        year=int(record.get("publicationDate", "0000")[:4]) if record.get("publicationDate") else None,
        venue=record.get("publicationName", "") or "",
        doi=record.get("doi", "") or "",
        abstract=record.get("abstract", "") or "",
        url=next(
            (u.get("value", "") for u in record.get("url", []) if isinstance(u, dict)),
            "",
        ),
        raw_id=record.get("identifier", ""),
        query_used="springer_meta_api",
    )


def search_springer(start: int = 1, max_records: int | None = None) -> list[Paper]:
    """
    Busca paginada na Springer Meta API, respeitando o limite diário de
    requisições. `start` permite retomar de onde parou em outro dia caso
    o limite diário seja atingido antes de terminar.

    O filtro de ano (YEAR_FROM/YEAR_TO) é aplicado aqui em Python sobre
    os resultados retornados, não como parâmetro da API — ver nota em
    _build_query().

    Tratamento de erros: um 429 (rate limit de rajada) é tratado com
    espera + nova tentativa da MESMA página, até MAX_429_RETRIES vezes.
    Qualquer outro erro inesperado interrompe a busca, mas a função
    ainda retorna tudo que já foi baixado até aquele ponto — nunca
    perde o progresso por causa de uma exceção no meio do caminho.
    """
    api_key = require_env("SPRINGER_API_KEY")
    query = _build_query()

    papers: list[Paper] = []
    n_excluded_by_year = 0
    requests_made = 0
    current_start = start
    retries_left = MAX_429_RETRIES

    while True:
        if requests_made >= DAILY_LIMIT:
            print(
                f"Limite diário de {DAILY_LIMIT} requisições atingido. "
                f"Pare por hoje e retome amanhã com start={current_start}."
            )
            break

        params = {
            "q": query,
            "api_key": api_key,
            "s": current_start,       # índice inicial (1-based)
            "p": RESULTS_PER_PAGE,    # tamanho da página
        }

        try:
            resp = requests.get(SPRINGER_META_URL, params=params, timeout=30)
            requests_made += 1

            if resp.status_code == 429:
                if retries_left <= 0:
                    print(
                        f"Rate limit (429) persistiu após {MAX_429_RETRIES} tentativas. "
                        f"Parando aqui — retome depois com start={current_start}."
                    )
                    break
                wait_s = int(resp.headers.get("Retry-After", RETRY_429_WAIT_S))
                print(f"  [429] Rate limit atingido. Esperando {wait_s}s antes de tentar de novo "
                      f"({retries_left} tentativas restantes)...", flush=True)
                time.sleep(wait_s)
                retries_left -= 1
                continue  # tenta a MESMA página de novo (não avança current_start)

            retries_left = MAX_429_RETRIES  # reset após sucesso
            resp.raise_for_status()
            data = resp.json()

        except Exception as e:
            print(f"Erro inesperado na requisição (start={current_start}): {e}")
            print(f"Parando aqui — {len(papers)} registros já baixados serão salvos mesmo assim. "
                  f"Retome depois com start={current_start}.")
            break

        records = data.get("records", [])
        for rec in records:
            paper = _record_to_paper(rec)
            if _year_in_range(paper.year):
                papers.append(paper)
            else:
                n_excluded_by_year += 1

        total_results = int(data.get("result", [{}])[0].get("total", 0))

        if requests_made == 1:
            print(f"Total de resultados na Springer para esta query: {total_results}")

        print(f"  ...{current_start + len(records) - 1}/{total_results} processados "
              f"({requests_made} requisições usadas)", flush=True)

        current_start += RESULTS_PER_PAGE

        if not records or current_start > total_results:
            break
        if max_records and len(papers) >= max_records:
            papers = papers[:max_records]
            break

        time.sleep(SLEEP_BETWEEN_REQUESTS_S)

    print(f"Requisições usadas nesta execução: {requests_made}/{DAILY_LIMIT}")
    print(f"Registros descartados pelo filtro de ano (fora de {YEAR_FROM}+): {n_excluded_by_year}")
    return papers


if __name__ == "__main__":
    import csv

    # Permite retomar de onde parou: python connectors/springer.py 501
    # (o número é o "start" que o script imprimiu quando bateu a cota
    # diária). Sem argumento, começa do 1 (busca nova).
    resume_start = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    results = search_springer(start=resume_start)
    print(f"Total de registros obtidos nesta execução: {len(results)}")

    out_path = os.path.join("data", "raw", "springer_results.csv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    file_exists = os.path.exists(out_path)
    # 'a' (append) quando está retomando ou o arquivo já existe de uma
    # execução anterior — nunca sobrescreve o que já foi baixado.
    mode = "a" if file_exists else "w"

    with open(out_path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].to_dict().keys()) if results else PAPER_FIELDS)
        if not file_exists:
            writer.writeheader()
        for p in results:
            writer.writerow(p.to_dict())

    action = "adicionados ao" if file_exists else "salvos em novo arquivo"
    print(f"Registros {action} {out_path}")
