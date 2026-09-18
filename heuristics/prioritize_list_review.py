"""
Adiciona uma coluna "Prioridade" numa planilha gerada por
heuristics/check_abstract_for_list.py (ou qualquer .xlsx com Título na
coluna C e Abstract na coluna H), separando:

- ALTA: título/abstract menciona sinais de agentic AI de verdade (LLM,
  agentic, generative, autonomous decision-making, foundation model) —
  esses são os candidatos reais a falso negativo, vale ler com atenção.
- BAIXA: só menciona MAS clássico/determinístico (multi-agent system,
  reinforcement learning, agent-based simulation) sem nenhum sinal de
  agentic AI — provavelmente exclusão legítima (EC4/EC5), pode ler por
  cima ou até pular na primeira passada.

Isso não decide nada sozinho — só ordena o trabalho pra você gastar
tempo onde realmente importa. A planilha é modificada IN PLACE.

Uso: python heuristics/prioritize_list_review.py data/processed/Abstracts_lista_3.xlsx
"""

import sys

import openpyxl
from openpyxl.styles import Font, PatternFill

TITLE_COL = 2     # índice 0-based da coluna C (Título)
ABSTRACT_COL = 7  # índice 0-based da coluna H (Abstract)
PRIORITY_COL = 9  # coluna I (1-based) onde a prioridade é escrita

HIGH_SIGNAL_TERMS = [
    "agentic", "llm", "large language model", "generative ai",
    "generative agent", "autonomous decision", "autonomous planning",
    "gpt", "foundation model", "chatgpt", "reasoning agent",
]


def has_high_signal(text: str) -> bool:
    t = text.lower()
    return any(term in t for term in HIGH_SIGNAL_TERMS)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    in_path = sys.argv[1]
    wb = openpyxl.load_workbook(in_path)
    ws = wb.active

    # Adiciona cabeçalho da nova coluna (coluna I, após Abstract em H)
    ws.cell(row=1, column=PRIORITY_COL, value="Prioridade").font = Font(name="Arial", bold=True, color="FFFFFF")
    ws.cell(row=1, column=PRIORITY_COL).fill = PatternFill(start_color="2E5C8A", end_color="2E5C8A", fill_type="solid")

    high_fill = PatternFill(start_color="FFE699", end_color="FFE699", fill_type="solid")
    low_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

    n_high = 0
    n_low = 0

    for row in ws.iter_rows(min_row=2):
        title = row[TITLE_COL].value or ""
        abstract = row[ABSTRACT_COL].value or ""

        combined = f"{title} {abstract}"
        if has_high_signal(combined):
            priority = "ALTA"
            fill = high_fill
            n_high += 1
        else:
            priority = "BAIXA"
            fill = low_fill
            n_low += 1

        cell = ws.cell(row=row[0].row, column=PRIORITY_COL, value=priority)
        cell.font = Font(name="Arial")
        cell.fill = fill

    ws.column_dimensions["I"].width = 12

    wb.save(in_path)
    print(f"Prioridade ALTA (ler com atenção): {n_high}")
    print(f"Prioridade BAIXA (provável exclusão legítima, ler por cima): {n_low}")
    print(f"\nPlanilha atualizada: {in_path}")


if __name__ == "__main__":
    main()