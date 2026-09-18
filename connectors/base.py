"""
Schema comum para registros vindos de qualquer base (API ou exportação manual).
Todo conector/importador deve produzir uma lista de dicts nesse formato,
para que a etapa de combinação/deduplicação funcione igual para todas as fontes.
"""

from dataclasses import dataclass, asdict, field
from typing import Optional


PAPER_FIELDS = [
    "source_db",     # ex: "openalex", "scopus", "acm_dl", "google_scholar"
    "title",
    "authors",       # string única, autores separados por "; "
    "year",
    "venue",         # periódico/conferência
    "doi",
    "abstract",
    "url",
    "raw_id",        # id nativo da base (útil para debug/rastreio)
    "query_used",    # qual bloco/consulta trouxe esse registro
]


@dataclass
class Paper:
    source_db: str
    title: str
    authors: str = ""
    year: Optional[int] = None
    venue: str = ""
    doi: str = ""
    abstract: str = ""
    url: str = ""
    raw_id: str = ""
    query_used: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_doi(doi: str) -> str:
    """Normaliza DOI para comparação (minúsculo, sem prefixo de URL)."""
    if not doi:
        return ""
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi.strip("/")


def normalize_title(title: str) -> str:
    """Normaliza título para comparação (minúsculo, sem pontuação/espaços extras)."""
    import re
    if not title:
        return ""
    title = title.lower()
    title = re.sub(r"[^a-z0-9\s]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title
