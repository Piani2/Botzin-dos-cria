"""Menu principal do Albion Black Market Tracker."""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import keyboard
import yaml

from modules.albion_html_generator import AlbionHTMLGenerator
from modules.albion_market_collector import AlbionMarketCollector
from modules.purchase_logic import CHEAP_TIER_KEYS, PURCHASE_TIER_GROUPS, PurchasePlanner


file_handler = logging.FileHandler("albion_tracker.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(message)s"))

logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
logger = logging.getLogger(__name__)


class AlbionTracker:
    def __init__(self, config_file="config.yaml"):
        self.load_config(config_file)
        self.create_directories()
        self.collector = AlbionMarketCollector(self.config)
        self.collector.set_wait_for_continue(self.wait_for_global_enter)
        self.html_gen = AlbionHTMLGenerator()
        self.report_updates = self.load_report_updates()
        self.load_persistent_market_data()
        logger.info("Albion Market Tracker inicializado")

    def load_config(self, config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as file_handle:
                self.config = yaml.safe_load(file_handle) or {}
            logger.info(f"Configurações carregadas de {config_file}")
        except FileNotFoundError:
            logger.error(f"Arquivo de configuração não encontrado: {config_file}")
            self.config = {}

    def create_directories(self):
        for directory in ("data", "reports"):
            Path(directory).mkdir(parents=True, exist_ok=True)

    def wait_for_global_enter(self, message):
        print(message)
        keyboard.wait("enter")
        while keyboard.is_pressed("enter"):
            time.sleep(0.05)

    def get_storage_path(self, key, default):
        return self.config.get("storage", {}).get(key, default)

    def get_persistent_data_path(self):
        return self.get_storage_path("latest_data_file", "data/latest_market_data.json")

    def get_report_updates_path(self):
        return self.get_storage_path("report_updates_file", "data/report_updates.json")

    def load_report_updates(self):
        updates = {"armas": None, "armaduras": None}
        path = self.get_report_updates_path()

        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as file_handle:
                    loaded = json.load(file_handle) or {}
                updates.update({
                    "armas": loaded.get("armas"),
                    "armaduras": loaded.get("armaduras"),
                })
        except Exception as e:
            logger.warning(f"Não foi possível carregar timestamps do relatório: {e}")

        return updates

    def save_report_updates(self):
        path = self.get_report_updates_path()
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as file_handle:
                json.dump(self.report_updates, file_handle, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Não foi possível salvar timestamps do relatório: {e}")

    def load_persistent_market_data(self):
        path = self.get_persistent_data_path()
        if not os.path.exists(path):
            return

        try:
            self.collector.get_collected_data().load_from_json(path)
        except Exception as e:
            logger.warning(f"Não foi possível carregar dados persistentes: {e}")

    def save_persistent_market_data(self):
        path = self.get_persistent_data_path()
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.collector.get_collected_data().save_to_json(path)
        except Exception as e:
            logger.warning(f"Não foi possível salvar dados persistentes: {e}")

    def mark_group_updated(self, item_group):
        if item_group not in {"armas", "armaduras"}:
            return

        self.report_updates[item_group] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.save_report_updates()

    def get_weapons_list(self):
        return [
            "Arco do",
            "Arco longo",
            "Arco de Guerra",
            "Besta do",
            "Besta Pesada",
            "Besta Leve",
            "Machado de Guerra",
            "Machadão",
            "Alabarda",
            "Adaga do",
            "Par de Adagas",
            "Garras do",
            "Martelo do",
            "Martelo Elevado",
            "Martelo de Batalha",
            "Luvas de Lutador",
            "Braçadeiras de Batalha",
            "Manoplas Cravadas",
            "Bordão do",
            "Cajado Férreo",
            "Cajado Bilaminado",
            "Lança do",
            "Pique",
            "Archa",
            "Espada Larga",
            "Montante",
            "Espadas Duplas",
            "Cajado Arcano do",
            "Cajado Arcano Elevado",
            "Cajado Enigmático",
            "Cajado Amaldiçoado",
            "Cajado Amaldiçoado Elevado",
            "Cajado Demoníaco",
            "Cajado de Fogo do",
            "Cajado de Fogo Elevado",
            "Cajado Infernal",
            "Cajado de Gelo do",
            "Cajado de Gelo Elevado",
            "Cajado Glacial",
            "Cajado Sagrado do",
            "Cajado Sagrado Elevado",
            "Cajado Divino",
            "Cajado da Natureza do",
            "Cajado da Natureza Elevado",
            "Cajado Selvagem",
            "Tomo de Feitiços",
            "Tocha do",
            "Escudo do",
        ]

    def get_armors_list(self):
        return [
            "Robe de Erudito",
            "Robe de Clérigo",
            "Robe de Mago",
            "Robe de Druida",
            "Casaco de Mercenário",
            "Casaco de Caçador",
            "Casaco de Assassino",
            "Casaco de Espreitador",
            "Armadura de Soldado",
            "Armadura de Cavaleiro",
            "Armadura de Guardião",
            "Armadura de Guarda-tumbas",
            "Capote de Erudito",
            "Capote de Clérigo",
            "Capote de Mago",
            "Capote de Druida",
            "Capuz de Mercenário",
            "Capuz de Caçador",
            "Capuz de Assassino",
            "Capuz de Espreitador",
            "Elmo de Soldado",
            "Elmo de Cavaleiro",
            "Elmo de Guardião",
            "Elmo de Guarda-tumbas",
            "Sandálias de Erudito",
            "Sandálias de Clérigo",
            "Sandálias de Mago",
            "Sandálias de Druida",
            "Sapatos de Mercenário",
            "Sapatos de Caçador",
            "Sapatos de Assassino",
            "Sapatos de Espreitador",
            "Botas de Soldado",
            "Botas de Cavaleiro",
            "Botas de Guardião",
            "Botas de Guarda-tumbas",
            "Capa",
            "Bolsa",
        ]

    def get_category_items(self):
        return {
            "armas": self.get_weapons_list(),
            "armaduras": self.get_armors_list(),
        }

    def automatic_data_collection(self, items_to_collect, item_group, generate_report_after=True):
        logger.info("\n=== MODO AUTOMÁTICO DE COLETA ===")

        if not self.config.get("price_region") or not self.config.get("quantity_region"):
            logger.warning(
                "As regiões OCR `price_region` e `quantity_region` não estão configuradas. "
                "A extração pode ficar errada até executar o calibrador."
            )

        print(f"Itens a coletar: {len(items_to_collect)}")
        self.wait_for_global_enter(
            "Abra o Mercado Negro, vá em vender e pressione ENTER para começar..."
        )

        try:
            self.collector.collect_multiple_items(items_to_collect, paging_profile=item_group)
            self.mark_group_updated(item_group)
            self.save_persistent_market_data()
        except KeyboardInterrupt:
            logger.info("\nColeta interrompida. Gerando relatório parcial...")
            self.mark_group_updated(item_group)
            self.save_persistent_market_data()
            self.generate_report(open_after_save=False)
            raise

        if generate_report_after:
            self.generate_report()

    def generate_report(self, open_after_save=True):
        try:
            market_data = self.collector.get_collected_data()
            html_data = market_data.export_for_html()

            if not html_data:
                logger.warning("Nenhum dado para gerar relatório")
                return False

            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            html = self.html_gen.generate(
                html_data,
                timestamp=timestamp,
                updates=self.report_updates,
            )

            filepath = self.get_storage_path("html_output", "reports/market_analysis.html")
            self.html_gen.save_html(html, filepath)
            self.save_persistent_market_data()
            logger.info(f"[OK] Relatório gerado: {filepath}")

            if open_after_save:
                if os.name == "nt":
                    os.startfile(filepath)
                else:
                    os.system(f"open {filepath}")

            return True
        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {e}")
            return False

    def run_purchase_menu(self):
        categories = self.ask_purchase_categories()
        if not categories:
            return

        budget = self.ask_int("Quantidade de prata para usar como banco", minimum=1)
        enabled_tiers = self.ask_purchase_tiers()
        if not enabled_tiers:
            print("Nenhum tier selecionado para compra.")
            return

        cheap_limits = self.ask_cheap_tier_limits(enabled_tiers)
        default_margin = self.config.get("trading", {}).get("profit_margin_percent", 50)
        profit_margin = self.ask_float(
            "Lucro mínimo para comprar o item (%)",
            default=default_margin,
            minimum=0,
        )

        planner = PurchasePlanner(
            self.collector.get_collected_data().get_all_items(),
            self.get_category_items(),
            profit_margin_percent=profit_margin,
        )
        candidates = planner.build_candidates(
            categories=categories,
            enabled_tiers=enabled_tiers,
            cheap_tier_limits=cheap_limits,
        )

        self.print_purchase_preview(candidates, budget, profit_margin)

    def ask_purchase_categories(self):
        print("\nComprar quais itens?")
        print("1. Armas")
        print("2. Armaduras")
        print("3. Ambos")
        print("4. Cancelar")
        choice = input("\nEscolha: ").strip()

        if choice == "1":
            return ["armas"]
        if choice == "2":
            return ["armaduras"]
        if choice == "3":
            return ["armas", "armaduras"]
        return []

    def ask_purchase_tiers(self):
        enabled_tiers = []
        print("\nTiers para comprar:")
        for label, tier_pairs in PURCHASE_TIER_GROUPS:
            if self.ask_yes_no(f"Comprar {label}?"):
                enabled_tiers.extend(f"{tier}{enchantment}" for tier, enchantment in tier_pairs)
        return enabled_tiers

    def ask_cheap_tier_limits(self, enabled_tiers):
        limits = {}
        cheap_enabled = [tier_key for tier_key in enabled_tiers if tier_key in CHEAP_TIER_KEYS]
        if not cheap_enabled:
            return limits

        print("\nLimites para tiers baratos/pesados.")
        print("Pressione ENTER para usar o padrão: quantidade vendida nas últimas 24h.")
        for tier_key in cheap_enabled:
            value = input(f"Limite máximo por item para {tier_key}: ").strip()
            if not value:
                continue
            try:
                parsed = int(value)
            except ValueError:
                print(f"Valor inválido para {tier_key}; usando vendidos.")
                continue
            if parsed > 0:
                limits[tier_key] = parsed
        return limits

    def ask_int(self, prompt, minimum=0):
        while True:
            value = input(f"{prompt}: ").strip().replace(".", "").replace(",", "")
            try:
                parsed = int(value)
            except ValueError:
                print("Digite um número válido.")
                continue
            if parsed < minimum:
                print(f"Digite um valor maior ou igual a {minimum}.")
                continue
            return parsed

    def ask_float(self, prompt, default=None, minimum=0):
        suffix = f" [{default}]" if default is not None else ""
        while True:
            value = input(f"{prompt}{suffix}: ").strip().replace(",", ".")
            if not value and default is not None:
                return float(default)
            try:
                parsed = float(value)
            except ValueError:
                print("Digite um número válido.")
                continue
            if parsed < minimum:
                print(f"Digite um valor maior ou igual a {minimum}.")
                continue
            return parsed

    def ask_yes_no(self, prompt, default=False):
        suffix = "s/N" if not default else "S/n"
        value = input(f"{prompt} ({suffix}): ").strip().lower()
        if not value:
            return default
        return value.startswith("s")

    def print_purchase_preview(self, candidates, budget, profit_margin):
        print("\n=== PRÉVIA DA LÓGICA DE COMPRA ===")
        print(f"Banco inicial: {budget:,}".replace(",", "."))
        print(f"Margem mínima configurada: {profit_margin}%")
        print(f"Itens elegíveis: {len(candidates)}")

        if not candidates:
            print("Nenhum item encontrado com os filtros escolhidos.")
            return

        print("\nCada item será comprado somente se o preço ao vivo for menor ou igual ao preço máximo.")
        print("Depois de cada unidade comprada, o bot deve ler novamente o preço antes de comprar outra.")
        print("\nPrimeiros candidatos:")
        for candidate in candidates[:20]:
            print(
                f"- {candidate.item_name} {candidate.tier}{candidate.enchantment} "
                f"| vender: {candidate.target_price:,} "
                f"| comprar até: {candidate.max_buy_price:,} "
                f"| limite: {candidate.remaining_limit}"
            )

        if len(candidates) > 20:
            print(f"... e mais {len(candidates) - 20} candidatos.")

    def run_interactive_menu(self):
        while True:
            print("\n" + "=" * 50)
            print("=== ALBION MARKET TRACKER ===")
            print("=" * 50)
            print("\n1. Coletar ARMAS")
            print("2. Coletar ARMADURAS")
            print("3. Coletar AMBOS")
            print("4. Comprar itens")
            print("5. Gerar relatório")
            print("6. Sair")

            choice = input("\nEscolha uma opção: ").strip()

            if choice == "1":
                self.automatic_data_collection(self.get_weapons_list(), item_group="armas")
            elif choice == "2":
                self.automatic_data_collection(self.get_armors_list(), item_group="armaduras")
            elif choice == "3":
                self.automatic_data_collection(
                    self.get_weapons_list(),
                    item_group="armas",
                    generate_report_after=False,
                )
                self.automatic_data_collection(
                    self.get_armors_list(),
                    item_group="armaduras",
                    generate_report_after=True,
                )
            elif choice == "4":
                self.run_purchase_menu()
            elif choice == "5":
                self.generate_report()
            elif choice == "6":
                logger.info("Aplicação encerrada")
                break
            else:
                print("[ERRO] Opção inválida")


def main():
    try:
        tracker = AlbionTracker("config.yaml")
        tracker.run_interactive_menu()
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro geral: {e}", exc_info=True)


if __name__ == "__main__":
    main()
