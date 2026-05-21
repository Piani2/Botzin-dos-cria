"""Menu principal do Albion Black Market Tracker baseado na API."""

import logging
import os
import sys
from datetime import datetime

from gerar_planilha_api import (
    API_HOSTS,
    DEFAULT_LOCATIONS,
    build_catalog,
    build_rows,
    fetch_daily_sales_history,
    fetch_prices,
    save_spreadsheet,
    selected_categories,
)
from modules.albion_html_generator import AlbionHTMLGenerator


file_handler = logging.FileHandler("albion_tracker.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(message)s"))

logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
logger = logging.getLogger(__name__)


DEFAULT_TIERS = [5, 6, 7, 8]
DEFAULT_ENCHANTS = [0, 1, 2, 3]
DEFAULT_QUALITY = [1, 2, 3]
DEFAULT_SERVER = "west"
DEFAULT_CSV_OUTPUT = "reports/albion_api_prices.csv"
DEFAULT_HTML_OUTPUT = "reports/market_analysis.html"
DEFAULT_NAVIGATION_CITY = "Caerleon"
PURCHASE_TIER_GROUPS = [
    ("T5.0", [("T5", ".0")]),
    ("T5.1 e T6.0", [("T5", ".1"), ("T6", ".0")]),
    ("T6.1 e T7.0", [("T6", ".1"), ("T7", ".0")]),
]


class AlbionTracker:
    def __init__(self):
        self.html_gen = AlbionHTMLGenerator()
        logger.info("Albion Market Tracker inicializado em modo API")

    def update_api_outputs(
        self,
        category="ambos",
        server=DEFAULT_SERVER,
        tiers=None,
        enchants=None,
        quality=None,
        csv_output=DEFAULT_CSV_OUTPUT,
        html_output=DEFAULT_HTML_OUTPUT,
        open_html=True,
        timeout=25,
    ):
        tiers = tiers or DEFAULT_TIERS
        enchants = enchants or DEFAULT_ENCHANTS
        quality = quality or DEFAULT_QUALITY

        host = API_HOSTS[server]
        generated_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        catalog = build_catalog(category, tiers, enchants)
        item_ids = sorted({item["item_id"] for item in catalog})

        print(f"Itens unicos na consulta: {len(item_ids)}")
        prices = fetch_prices(host, item_ids, DEFAULT_LOCATIONS, quality, timeout)
        history = fetch_daily_sales_history(host, item_ids, quality, timeout)
        rows = build_rows(catalog, prices, history, generated_at)

        csv_path = save_spreadsheet(rows, csv_output)
        html = self.html_gen.generate_from_api_rows(
            rows,
            timestamp=generated_at,
            categories=selected_categories(category),
            server=server,
        )
        self.html_gen.save_html(html, html_output)

        print(f"CSV atualizado: {csv_path}")
        print(f"HTML atualizado: {html_output}")

        if open_html:
            self.open_file(html_output)

        return rows

    def open_file(self, filepath):
        try:
            if os.name == "nt":
                os.startfile(filepath)
            else:
                os.system(f"open {filepath}")
        except Exception as exc:
            logger.warning(f"Nao foi possivel abrir {filepath}: {exc}")

    def run_store_navigation(self):
        category = self.ask_category()
        city = input(f"Cidade onde voce esta [{DEFAULT_NAVIGATION_CITY}]: ").strip() or DEFAULT_NAVIGATION_CITY
        min_profit = self.ask_optional_int("Lucro minimo por item", default=1)
        quantity_per_item = self.ask_optional_int("Quantidade maxima para comprar por item", default=1)
        max_items = self.ask_optional_int("Maximo de itens para navegar", default=20)

        rows = self.update_api_outputs(category=category, open_html=False)

        from modules.store_navigator import StoreNavigator

        navigator = StoreNavigator()
        navigator.navigate_rows(
            rows,
            city=city,
            min_profit=min_profit,
            quantity_per_item=quantity_per_item,
            max_items=max_items,
        )

    def run_purchase_flow(self):
        category = self.ask_category()
        budget = self.ask_optional_int("Quanto em prata e para gastar", default=0)
        if budget <= 0:
            print("Banco invalido. Compra cancelada.")
            return

        profit_percent = self.ask_optional_float("Lucro minimo (%)", default=50)
        tier_limits = self.ask_purchase_tier_groups()
        if not tier_limits:
            print("Nenhum grupo de tier selecionado.")
            return

        rows = self.update_api_outputs(category=category, open_html=False)

        from modules.store_navigator import StoreNavigator

        navigator = StoreNavigator()
        navigator.prepare_purchase_plan(
            rows,
            budget=budget,
            profit_percent=profit_percent,
            tier_limits=tier_limits,
        )

    def ask_purchase_tier_groups(self):
        selected = {}
        print("\nGrupos para comprar:")
        for label, tier_pairs in PURCHASE_TIER_GROUPS:
            if not self.ask_yes_no(f"Comprar itens de tier {label}?"):
                continue
            value = input(
                f"Limite de compra para {label} "
                "(ENTER usa vendidos 24h da tabela): "
            ).strip().replace(".", "")
            limit = None
            if value:
                try:
                    limit = int(value)
                except ValueError:
                    print("Limite invalido; usando vendidos 24h da tabela.")
            for tier, enchantment in tier_pairs:
                selected[f"{tier}{enchantment}"] = limit
        return selected

    def ask_category(self):
        print("\nCategoria:")
        print("1. Armas")
        print("2. Armaduras")
        print("3. Ambos")
        choice = input("\nEscolha: ").strip()
        if choice == "1":
            return "armas"
        if choice == "2":
            return "armaduras"
        return "ambos"

    def ask_optional_int(self, prompt, default):
        value = input(f"{prompt} [{default}]: ").strip().replace(".", "")
        if not value:
            return default
        try:
            return int(value)
        except ValueError:
            print(f"Valor invalido; usando {default}.")
            return default

    def ask_optional_float(self, prompt, default):
        value = input(f"{prompt} [{default}]: ").strip().replace(",", ".")
        if not value:
            return float(default)
        try:
            return float(value)
        except ValueError:
            print(f"Valor invalido; usando {default}.")
            return float(default)

    def ask_yes_no(self, prompt, default=False):
        suffix = "S/n" if default else "s/N"
        value = input(f"{prompt} ({suffix}): ").strip().lower()
        if not value:
            return default
        return value.startswith("s")

    def run_interactive_menu(self):
        while True:
            print("\n" + "=" * 50)
            print("=== ALBION MARKET TRACKER - API ===")
            print("=" * 50)
            print("\n1. Atualizar ARMAS")
            print("2. Atualizar ARMADURAS")
            print("3. Atualizar AMBOS")
            print("4. Navegar loja por oportunidades da API")
            print("5. Comprar itens")
            print("6. Sair")

            choice = input("\nEscolha uma opcao: ").strip()

            if choice == "1":
                self.update_api_outputs(category="armas")
            elif choice == "2":
                self.update_api_outputs(category="armaduras")
            elif choice == "3":
                self.update_api_outputs(category="ambos")
            elif choice == "4":
                self.run_store_navigation()
            elif choice == "5":
                self.run_purchase_flow()
            elif choice == "6":
                logger.info("Aplicacao encerrada")
                break
            else:
                print("[ERRO] Opcao invalida")


def main():
    try:
        tracker = AlbionTracker()
        tracker.run_interactive_menu()
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuario")
    except Exception as exc:
        logger.error(f"Erro geral: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
