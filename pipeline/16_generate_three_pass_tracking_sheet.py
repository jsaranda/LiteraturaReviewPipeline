"""
Gera a planilha de acompanhamento do método de três passadas, a partir
do corpus final (final_after_ec6.csv, etapa 15).

Simplificado pra ser RÁPIDO de preencher: uma coluna única "Válido?"
onde você digita S ou N (sem dropdown, sem checkbox de verdade — o
Excel/openpyxl não suporta checkbox nativo de forma confiável nessa
geração automática). Em branco = ainda pendente.

Requer: openpyxl (está no requirements.txt)

Rode: python pipeline/16_generate_three_pass_tracking_sheet.py
"""

import csv
import os

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

IN_PATH = os.path.join("data", "processed", "final_after_ec6.csv")
OUT_PATH = os.path.join("data", "processed", "Three_Pass_Tracking.xlsx")


def build_link(row: dict) -> str:
    url = row.get("url", "").strip()
    if url:
        return url
    doi = row.get("doi", "").strip()
    if doi:
        return doi if doi.startswith("http") else f"https://doi.org/{doi}"
    return ""


def main() -> None:
    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Three-Pass Tracking"

    headers = ["#", "Base", "Título", "Ano", "Venue", "Link/DOI", "Válido? (S/N)", "Nota"]

    header_font = Font(name="Arial", bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="2E5C8A", end_color="2E5C8A", fill_type="solid")
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=col, value=h)
        c.font = header_font
        c.fill = header_fill
        c.border = border
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for i, row in enumerate(rows, start=1):
        r = i + 1
        link = build_link(row)

        values = [i, row.get("source_db", ""), row.get("title", ""),
                  row.get("year", ""), row.get("venue", ""), link, "", ""]
        for col, val in enumerate(values, start=1):
            cell = ws.cell(row=r, column=col, value=val)
            cell.font = Font(name="Arial")
            cell.border = border
            if col == 3:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            elif col == 6 and link:
                cell.hyperlink = link
                cell.font = Font(name="Arial", color="0563C1", underline="single")
            elif col == 7:
                cell.alignment = Alignment(horizontal="center")

    widths = [6, 16, 50, 8, 28, 35, 14, 30]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 30

    # Congela também a formatação condicional: S = verde, N = vermelho,
    # pra você bater o olho e ver o progresso sem precisar ler a coluna
    from openpyxl.formatting.rule import CellIsRule
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    rng = f"G2:G{len(rows) + 1}"
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"S"'], fill=green_fill))
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"N"'], fill=red_fill))

    wb.save(OUT_PATH)
    print(f"Planilha gerada com {len(rows)} artigos: {OUT_PATH}")


if __name__ == "__main__":
    main()