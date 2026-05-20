"""Geracao do relatorio HTML com dados vindos da Albion Online Data API."""

import html
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MONEY_COLUMNS = {
    "Black Market pedido venda",
    "Bridgewatch venda min",
    "Caerleon venda min",
    "Fort Sterling venda min",
    "Lymhurst venda min",
    "Martlock venda min",
    "Thetford venda min",
}

RIGHT_COLUMNS = MONEY_COLUMNS
MUTED_COLUMNS = {
    "Gerado em",
    "API ID",
    "Black Market venda atualizado",
}


class AlbionHTMLGenerator:
    """Gera relatorio HTML a partir das mesmas linhas usadas na planilha da API."""

    def generate_from_api_rows(self, rows, timestamp=None, categories=None, server="west"):
        categories = categories or []
        columns = list(rows[0].keys()) if rows else self.default_columns()
        category_label = ", ".join(categories) if categories else "todos"
        table_head = "\n".join(f"<th>{self._text(column)}</th>" for column in columns)
        table_rows = "\n".join(self._render_row(row, columns) for row in rows)
        if not table_rows:
            table_rows = (
                f'<tr><td class="empty-row" colspan="{len(columns)}">'
                "Nenhum dado encontrado."
                "</td></tr>"
            )

        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Albion Black Market API</title>
    <style>
        :root {{
            color-scheme: light;
            --bg: #f5f2ed;
            --panel: #fffdf8;
            --ink: #202833;
            --muted: #657080;
            --line: #d7d0c4;
            --header: #111111;
            --accent: #8b5a2b;
            --good: #176f4a;
            --bad: #a02f2f;
            --empty: #9aa3ad;
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            background: var(--bg);
            color: var(--ink);
            font-family: Arial, "Helvetica Neue", Helvetica, sans-serif;
        }}

        main {{
            width: min(1680px, calc(100% - 32px));
            margin: 0 auto;
            padding: 22px 0 32px;
        }}

        .report-header {{
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 16px;
        }}

        h1 {{
            margin: 0;
            font-size: 26px;
            line-height: 1.1;
            color: var(--header);
            letter-spacing: 0;
        }}

        .subtitle {{
            margin-top: 6px;
            color: var(--muted);
            font-size: 13px;
        }}

        .summary {{
            display: grid;
            grid-template-columns: repeat(3, minmax(120px, 1fr));
            gap: 10px;
            min-width: 460px;
        }}

        .summary-item {{
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel);
            padding: 10px 12px;
        }}

        .summary-label {{
            display: block;
            color: var(--muted);
            font-size: 12px;
            margin-bottom: 3px;
        }}

        .summary-value {{
            display: block;
            font-size: 15px;
            font-weight: 700;
            color: var(--header);
        }}

        .table-container {{
            overflow: auto;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel);
            box-shadow: 0 12px 24px rgba(33, 39, 46, 0.08);
        }}

        table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            min-width: 1480px;
        }}

        thead th {{
            position: sticky;
            top: 0;
            z-index: 2;
            background: var(--header);
            color: #ffffff;
            padding: 11px 10px;
            text-align: left;
            font-size: 13px;
            font-weight: 700;
            border-right: 1px solid rgba(255, 255, 255, 0.12);
            white-space: nowrap;
        }}

        tbody td {{
            padding: 9px 10px;
            border-top: 1px solid var(--line);
            border-right: 1px solid #ece5da;
            text-align: left;
            vertical-align: middle;
            font-size: 13px;
            white-space: nowrap;
        }}

        tbody tr:nth-child(even) {{
            background: #faf6ee;
        }}

        tbody tr:hover td {{
            filter: brightness(0.97);
        }}

        .strong {{
            font-weight: 700;
            color: #273849;
        }}

        .accent {{
            font-weight: 800;
            color: var(--accent);
        }}

        .money,
        .right {{
            text-align: right;
            font-variant-numeric: tabular-nums;
        }}

        .money {{
            color: var(--good);
            font-weight: 800;
        }}

        .negative {{
            color: var(--bad);
        }}

        .muted {{
            color: var(--muted);
        }}

        .empty {{
            color: var(--empty);
            font-weight: 700;
            text-align: center;
        }}

        .empty-row {{
            padding: 18px;
            text-align: center;
            color: var(--empty);
            font-weight: 700;
        }}

        @media (max-width: 820px) {{
            main {{
                width: min(100% - 20px, 1680px);
                padding-top: 14px;
            }}

            .report-header {{
                display: block;
            }}

            .summary {{
                grid-template-columns: 1fr;
                min-width: 0;
                margin-top: 12px;
            }}
        }}
    </style>
</head>
<body>
    <main>
        <header class="report-header">
            <div>
                <h1>Albion Black Market API</h1>
                <div class="subtitle">Relatorio gerado com dados da Albion Online Data API em {self._text(timestamp or "")}</div>
            </div>
            <section class="summary" aria-label="Resumo">
                <div class="summary-item">
                    <span class="summary-label">Servidor</span>
                    <span class="summary-value">{self._text(server)}</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">Categorias</span>
                    <span class="summary-value">{self._text(category_label)}</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">Linhas</span>
                    <span class="summary-value">{len(rows)}</span>
                </div>
            </section>
        </header>

        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        {table_head}
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>
    </main>
</body>
</html>
"""

    def default_columns(self):
        return [
            "Gerado em",
            "Categoria",
            "Item",
            "Tier",
            "Encantamento",
            "API ID",
            "Black Market pedido venda",
            "Black Market venda atualizado",
            "Bridgewatch venda min",
            "Caerleon venda min",
            "Fort Sterling venda min",
            "Lymhurst venda min",
            "Martlock venda min",
            "Thetford venda min",
        ]

    def _render_row(self, row, columns):
        cells = "\n".join(self._render_cell(column, row.get(column)) for column in columns)
        return f"<tr>{cells}</tr>"

    def _render_cell(self, column, value):
        if value in (None, ""):
            return '<td class="empty">-</td>'

        classes = []
        if column in MONEY_COLUMNS:
            classes.append("money")
        if column in RIGHT_COLUMNS:
            classes.append("right")
        if column in MUTED_COLUMNS:
            classes.append("muted")
        if column == "Item":
            classes.append("strong")
        if column in {"Tier", "Encantamento"}:
            classes.append("accent")
        if self._is_negative(value):
            classes.append("negative")

        class_attr = f' class="{" ".join(classes)}"' if classes else ""
        return f"<td{class_attr}>{self._format_value(column, value)}</td>"

    def _format_value(self, column, value):
        if column in MONEY_COLUMNS:
            return self._format_number(value)
        return self._text(value)

    def _text(self, value):
        return html.escape("" if value is None else str(value))

    def _format_number(self, value):
        try:
            return f"{int(value):,}".replace(",", ".")
        except (TypeError, ValueError):
            return self._text(value)

    def _is_negative(self, value):
        try:
            return float(str(value).replace(",", ".")) < 0
        except (TypeError, ValueError):
            return False

    def save_html(self, html_content, filepath):
        try:
            output = Path(filepath)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(html_content, encoding="utf-8")
            logger.info(f"HTML salvo em {filepath}")
            return True
        except Exception as exc:
            logger.error(f"Erro ao salvar HTML: {exc}")
            return False
