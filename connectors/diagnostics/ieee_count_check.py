"""
Recupera o total de resultados no IEEE Xplore SEM o filtro de ano
(start_year/end_year), pra completar a coluna "Busca Inicial" da
planilha. Faz só 2 chamadas mínimas (max_records=1), gasta muito
pouco da cota diária (200/dia).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import requests
from config import YEAR_FROM
from config import require_env
from connectors.ieee_xplore import IEEE_SEARCH_URL, _build_query


def get_total(with_year_filter: bool) -> int:
    params = {
        "apikey": require_env("IEEE_API_KEY"),
        "querytext": _build_query(),
        "start_record": 1,
        "max_records": 1,
    }
    if with_year_filter and YEAR_FROM:
        params["start_year"] = YEAR_FROM
    resp = requests.get(IEEE_SEARCH_URL, params=params, timeout=30)
    resp.raise_for_status()
    return int(resp.json().get("total_records", 0))


total_sem_filtro = get_total(with_year_filter=False)
print(f"IEEE SEM filtro de data (Busca Inicial real): {total_sem_filtro}")

total_com_filtro = get_total(with_year_filter=True)
print(f"IEEE COM filtro de data ({YEAR_FROM}+): {total_com_filtro}")

print(f"\nDiferença (excluídos pelo filtro de data): {total_sem_filtro - total_com_filtro}")