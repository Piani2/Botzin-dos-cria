"""
Modulo para gerar relatorio HTML do Albion Market Tracker.
"""

import logging

from jinja2 import Template

logger = logging.getLogger(__name__)


class AlbionHTMLGenerator:
    """Gera relatorio HTML com tabela de itens, precos e quantidades."""

    def __init__(self):
        self.template = self.get_template()

    @staticmethod
    def get_template():
        """Retorna template HTML com estilo embutido."""
        return Template("""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Albion Black Market</title>
    <style>
        :root {
            color-scheme: light;
            --bg: #f4f1ea;
            --panel: #fffdf8;
            --ink: #1f2933;
            --muted: #697586;
            --line: #d8d0c2;
            --header: #050505;
            --accent: #a05a2c;
            --good: #1f8a5b;
            --empty: #a4a9b2;
            --ench-0: #b7bec8;
            --ench-1: #9fdab3;
            --ench-2: #9fc9f8;
            --ench-3: #bfa2f5;
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            background: var(--bg);
            color: var(--ink);
            font-family: Arial, "Helvetica Neue", Helvetica, sans-serif;
        }

        main {
            width: min(1480px, calc(100% - 32px));
            margin: 0 auto;
            padding: 22px 0 32px;
        }

        .report-header {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 16px;
        }

        h1 {
            margin: 0;
            font-size: 26px;
            line-height: 1.1;
            color: var(--header);
            letter-spacing: 0;
        }

        .subtitle {
            margin-top: 6px;
            color: var(--muted);
            font-size: 13px;
        }

        .updates {
            display: grid;
            grid-template-columns: repeat(2, minmax(190px, 1fr));
            gap: 10px;
            min-width: 400px;
        }

        .update-card {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel);
            padding: 10px 12px;
        }

        .update-label {
            display: block;
            color: var(--muted);
            font-size: 12px;
            margin-bottom: 3px;
        }

        .update-time {
            display: block;
            font-size: 15px;
            font-weight: 700;
            color: var(--header);
        }

        .table-container {
            overflow: visible;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--panel);
            box-shadow: 0 12px 24px rgba(33, 39, 46, 0.08);
        }

        table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            min-width: 980px;
        }

        thead {
            position: sticky;
            top: 0;
            z-index: 10;
        }

        thead th {
            position: sticky;
            top: 0;
            z-index: 11;
            background: var(--header);
            color: #ffffff;
            padding: 11px 10px;
            text-align: center;
            font-size: 13px;
            font-weight: 700;
            border-right: 1px solid rgba(255, 255, 255, 0.12);
        }

        thead th:first-child {
            text-align: left;
        }

        tbody td {
            padding: 9px 10px;
            border-top: 1px solid var(--line);
            border-right: 1px solid #ece5da;
            text-align: center;
            vertical-align: middle;
            font-size: 13px;
        }

        tbody tr:nth-child(even) {
            background: #faf6ee;
        }

        .item-name {
            text-align: left;
            font-weight: 700;
            color: #273849;
            min-width: 220px;
        }

        .tier {
            width: 70px;
            font-weight: 800;
            color: var(--accent);
            background: rgba(160, 90, 44, 0.08);
        }

        .complex-data {
            display: grid;
            gap: 3px;
            line-height: 1.2;
        }

        .enchant-0 {
            background: var(--ench-0);
        }

        .enchant-1 {
            background: var(--ench-1);
        }

        .enchant-2 {
            background: var(--ench-2);
        }

        .enchant-3 {
            background: var(--ench-3);
        }

        tbody tr:hover td {
            filter: brightness(0.97);
        }

        .quantity {
            color: #111111;
            font-size: 12px;
            font-weight: 700;
        }

        .price {
            color: var(--good);
            font-weight: 800;
            font-size: 14px;
        }

        .empty {
            color: var(--empty);
            font-weight: 700;
        }

        @media (max-width: 820px) {
            main {
                width: min(100% - 20px, 1480px);
                padding-top: 14px;
            }

            .report-header {
                display: block;
            }

            .updates {
                grid-template-columns: 1fr;
                min-width: 0;
                margin-top: 12px;
            }
        }
    </style>
</head>
<body>
    <main>
        <header class="report-header">
            <div>
                <h1>Albion Black Market</h1>
                <div class="subtitle">Arquivo fixo atualizado pelo bot em {{ timestamp }}</div>
            </div>
            <section class="updates" aria-label="Ultimas atualizacoes">
                <div class="update-card">
                    <span class="update-label">Armas</span>
                    <span class="update-time">{{ updates.armas or "Ainda nao atualizado" }}</span>
                </div>
                <div class="update-card">
                    <span class="update-label">Armaduras</span>
                    <span class="update-time">{{ updates.armaduras or "Ainda nao atualizado" }}</span>
                </div>
            </section>
        </header>

        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Nome do Item</th>
                        <th>Tier</th>
                        <th>.0</th>
                        <th>.1</th>
                        <th>.2</th>
                        <th>.3</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in items %}
                    <tr>
                        <td class="item-name">{{ row.name }}</td>
                        <td class="tier">{{ row.tier }}</td>
                        {% for enchant in ['.0', '.1', '.2', '.3'] %}
                        <td class="enchant-cell enchant-{{ loop.index0 }}">
                            {% if row.enchants[enchant] is not none %}
                                <div class="complex-data">
                                    <span class="price">{{ "{:,}".format(row.enchants[enchant].price).replace(',', '.') }}</span>
                                    <span class="quantity">Vendidos: {{ row.enchants[enchant].quantity }}</span>
                                </div>
                            {% else %}
                                <span class="empty">-</span>
                            {% endif %}
                        </td>
                        {% endfor %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </main>
</body>
</html>
        """)

    def generate(self, items_data, timestamp=None, updates=None):
        """Gera HTML a partir dos dados."""
        try:
            if timestamp is None:
                from datetime import datetime

                timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            html = self.template.render(
                items=items_data,
                timestamp=timestamp,
                updates=updates or {},
            )

            logger.info(f"HTML gerado com {len(items_data)} linhas")
            return html

        except Exception as e:
            logger.error(f"Erro ao gerar HTML: {e}")
            return "<h1>Erro ao gerar HTML</h1>"

    def generate_with_prices(self, items_data, timestamp=None, updates=None):
        """Compatibilidade com chamadas antigas; o template atual ja inclui precos."""
        return self.generate(items_data, timestamp=timestamp, updates=updates)

    def save_html(self, html_content, filepath):
        """Salva HTML em arquivo."""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(f"HTML salvo em {filepath}")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar HTML: {e}")
            return False
