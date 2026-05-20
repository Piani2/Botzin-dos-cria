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
        rows = build_rows(catalog, prices, {}, generated_at)

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

    def run_interactive_menu(self):
        while True:
            print("\n" + "=" * 50)
            print("=== ALBION MARKET TRACKER - API ===")
            print("=" * 50)
            print("\n1. Atualizar ARMAS")
            print("2. Atualizar ARMADURAS")
            print("3. Atualizar AMBOS")
            print("4. Navegar loja por oportunidades da API")
            print("5. Sair")

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
