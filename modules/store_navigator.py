"""Navegacao calibrada pela loja usando somente dados da API."""

import json
import logging
import time
import unicodedata
from pathlib import Path

from modules.albion_items import get_category_items
from modules.automation_controller import AutomationController

logger = logging.getLogger(__name__)


MOJIBAKE_REPLACEMENTS = {
    "\u00c3\u00a1": "a",
    "\u00c3\u00a0": "a",
    "\u00c3\u00a2": "a",
    "\u00c3\u00a3": "a",
    "\u00c3\u00a9": "e",
    "\u00c3\u00aa": "e",
    "\u00c3\u00ad": "i",
    "\u00c3\u00b3": "o",
    "\u00c3\u00b4": "o",
    "\u00c3\u00b5": "o",
    "\u00c3\u00ba": "u",
    "\u00c3\u00a7": "c",
    "\u00c3\u0081": "a",
    "\u00c3\u0089": "e",
    "\u00c3\u008d": "i",
    "\u00c3\u0093": "o",
    "\u00c3\u009a": "u",
    "\u00c3\u0087": "c",
}


class StoreNavigator:
    def __init__(self, config_path="store_navigation.json"):
        self.config_path = Path(config_path)
        self.config = self.load_config()
        self.controller = AutomationController(self.config.get("automation", {}))
        self.black_market_ui = self.config.get("black_market_ui", {})
        self.item_tier_groups = self.config.get("item_tier_groups", {})
        self.category_items = get_category_items()
        self.item_indexes = self.build_item_indexes()
        self.current_item_page = None
        self.active_paging = None
        automation = self.config.get("automation", {})
        self.click_delay = float(automation.get("click_delay", 0.25))
        self.dropdown_open_delay = float(automation.get("dropdown_open_delay", 0.18))
        self.dropdown_select_delay = float(automation.get("dropdown_select_delay", 0.12))
        self.filter_settle_delay = float(automation.get("filter_settle_delay", 0.22))
        self.item_select_delay = float(automation.get("item_select_delay", 0.25))
        self.default_quality = self.config.get("navigation", {}).get("default_quality", "normal")

    def load_config(self):
        if not self.config_path.exists():
            return {}
        with self.config_path.open("r", encoding="utf-8") as file_handle:
            return json.load(file_handle) or {}

    def build_item_indexes(self):
        indexes = {}
        for category, items in self.category_items.items():
            indexes[category] = {
                self._normalize_item_name(item): index
                for index, item in enumerate(items)
            }
        return indexes

    def build_navigation_rows(self, rows, city=None, min_profit=None, max_items=None):
        navigation = self.config.get("navigation", {})
        city = city or navigation.get("default_city")
        min_profit = self._int_or_default(min_profit, navigation.get("min_profit", 1))
        max_items = self._int_or_default(max_items, navigation.get("max_items", 20))
        city_price_field = f"{city} venda min"

        candidates = []
        for row in rows:
            city_price = self._int_or_default(row.get(city_price_field), 0)
            black_market_price = self._int_or_default(row.get("Black Market pedido venda"), 0)
            if city_price <= 0 or black_market_price <= 0:
                continue
            if black_market_price - city_price < min_profit:
                continue

            if self.get_item_index(row.get("Categoria"), row.get("Item")) is None:
                continue

            candidates.append(row)

        candidates.sort(
            key=lambda row: (
                row.get("Categoria", ""),
                row.get("Item", ""),
                row.get("Tier", ""),
                row.get("Encantamento", ""),
            )
        )
        return candidates[:max_items] if max_items > 0 else candidates

    def navigate_rows(self, rows, city=None, min_profit=None, quantity_per_item=None, max_items=None):
        self.active_city = city or self.config.get("navigation", {}).get("default_city")
        self.quantity_per_item = self._int_or_default(quantity_per_item, 1)
        candidates = self.build_navigation_rows(
            rows,
            city=self.active_city,
            min_profit=min_profit,
            max_items=max_items,
        )
        if not candidates:
            print("Nenhuma oportunidade encontrada para navegar com os filtros atuais.")
            return []

        print("\nAbra a loja/mercado no Albion e deixe a lista de itens na mesma categoria indicada.")
        print("O bot vai apenas clicar e selecionar filtros; ele nao captura nem le a tela.")
        input("Pressione ENTER quando estiver pronto para iniciar a navegacao...")

        previous_category = None
        for index, row in enumerate(candidates, start=1):
            category = row.get("Categoria")
            if category != previous_category:
                self.prepare_category(category)
                previous_category = category

            self.navigate_to_row(row)
            self.print_row_hint(index, len(candidates), row)

            if self.config.get("navigation", {}).get("pause_between_items", True):
                input("Confira no jogo. Pressione ENTER para fechar este item e continuar...")

            self.close_item(row.get("Item"))

        return candidates

    def prepare_category(self, category):
        item_count = len(self.category_items.get(category, []))
        self.active_paging = self.get_item_paging(item_count, category)
        self.current_item_page = None

        label = "ARMAS" if category == "armas" else "ARMADURAS"
        print(f"\nCategoria {label}. Ajuste a loja para essa lista, se necessario.")
        input("Pressione ENTER para continuar...")

    def navigate_to_row(self, row):
        category = row.get("Categoria")
        item_name = row.get("Item")
        tier = row.get("Tier")
        enchantment = self.normalize_enchantment(row.get("Encantamento"))
        item_index = self.get_item_index(category, item_name)
        if item_index is None:
            raise RuntimeError(f"Item fora do catalogo calibrado: {item_name}")

        tier_profile = self.get_tier_mapping_profile_for_item(item_name)
        self.select_item(item_index)
        time.sleep(self.item_select_delay)

        self.select_quality(row.get("Qualidade") or self.default_quality)
        time.sleep(self.filter_settle_delay)
        self.select_tier_and_enchantment(enchantment=".0", tier_profile=tier_profile)
        time.sleep(self.filter_settle_delay)
        self.select_tier_and_enchantment(tier=tier, tier_profile=tier_profile)
        time.sleep(self.filter_settle_delay)
        self.select_tier_and_enchantment(enchantment=enchantment, tier_profile=tier_profile)
        time.sleep(self.filter_settle_delay)

    def select_item(self, item_index):
        paging = self.active_paging or self.black_market_ui.get("item_paging", {})
        if paging.get("enabled"):
            self.select_item_paged(item_index, paging)
            return

        first_x, first_y = self.black_market_ui.get("item_list_first", [360, 320])
        row_step = self.black_market_ui.get("item_list_row_step", 34)
        visible_rows = max(1, self.black_market_ui.get("item_list_visible_rows", 12))
        scroll_per_row = self.black_market_ui.get("item_list_scroll_per_row", -120)
        target_page = item_index // visible_rows
        target_row = item_index % visible_rows

        self.controller.press_key("home")
        time.sleep(self.click_delay)
        rows_to_scroll = target_page * visible_rows
        if rows_to_scroll > 0:
            self.controller.scroll(scroll_per_row * rows_to_scroll)
            time.sleep(self.click_delay)

        self.controller.click(first_x, first_y + (target_row * row_step))

    def select_item_paged(self, item_index, paging):
        page_size = max(1, int(paging.get("page_size", 5)))
        target_page = item_index // page_size
        target_row = item_index % page_size

        if self.current_item_page is None or target_page < self.current_item_page:
            reset_key = paging.get("reset_key", "home")
            if reset_key:
                self.controller.press_key(reset_key)
            self.current_item_page = 0
            time.sleep(self.item_select_delay)

        while self.current_item_page < target_page:
            self.scroll_item_page(paging, self.current_item_page)
            self.current_item_page += 1
            time.sleep(self.item_select_delay)

        page_row_positions = paging.get("page_row_positions") or {}
        row_positions = page_row_positions.get(str(target_page)) or paging.get("row_positions") or []
        if target_row < len(row_positions):
            click_x, click_y = row_positions[target_row]
        else:
            first_x, first_y = self.black_market_ui.get("item_list_first", [360, 320])
            row_step = self.black_market_ui.get("item_list_row_step", 34)
            click_x = first_x
            click_y = first_y + (target_row * row_step)

        self.controller.click(click_x, click_y)
        time.sleep(self.item_select_delay)

    def scroll_item_page(self, paging, page_index):
        if paging.get("method", "wheel") == "drag":
            drag_steps = paging.get("drag_steps") or []
            if page_index < len(drag_steps):
                step = drag_steps[page_index]
                start = step.get("start")
                end = step.get("end")
            else:
                start = paging.get("drag_start")
                end = paging.get("drag_end")

            if start and end and len(start) == 2 and len(end) == 2:
                self.controller.drag_from_to(
                    start[0],
                    start[1],
                    end[0],
                    end[1],
                    duration=float(paging.get("drag_duration", 0.35)),
                )
                return

        self.controller.scroll(int(paging.get("scroll_per_page", -600)))

    def select_tier_and_enchantment(self, tier=None, enchantment=None, tier_profile="default"):
        if tier is not None:
            tier_dropdown = self.get_tier_dropdown_for_profile(tier_profile)
            self.click_dropdown_option(
                tier_dropdown.get("open"),
                tier_dropdown.get("options", {}).get(tier),
                f"tier {tier}",
            )

        if enchantment is not None:
            enchant_dropdown = self.black_market_ui.get("enchant_dropdown", {})
            self.click_dropdown_option(
                enchant_dropdown.get("open"),
                enchant_dropdown.get("options", {}).get(enchantment),
                f"encantamento {enchantment}",
            )

    def select_quality(self, quality):
        quality_dropdown = self.black_market_ui.get("quality_dropdown", {})
        if not quality_dropdown:
            return
        self.click_dropdown_option(
            quality_dropdown.get("open"),
            quality_dropdown.get("options", {}).get(str(quality).lower()),
            f"qualidade {quality}",
        )

    def click_dropdown_option(self, open_coord, option_coord, label):
        if not open_coord or not option_coord:
            logger.debug(f"Dropdown sem coordenadas para {label}")
            return
        self.controller.click(open_coord[0], open_coord[1])
        time.sleep(self.dropdown_open_delay)
        self.controller.move_mouse(option_coord[0], option_coord[1], duration=0.03)
        self.controller.click(option_coord[0], option_coord[1])
        time.sleep(self.dropdown_select_delay)

    def close_item(self, item_name):
        close_coord = self.black_market_ui.get("item_tab_close")
        if isinstance(close_coord, list) and len(close_coord) == 2:
            self.controller.click(close_coord[0], close_coord[1])
            time.sleep(self.click_delay)
            logger.debug(f"Item fechado: {item_name}")

    def get_item_paging(self, total_items, profile_name=None):
        profiles = self.black_market_ui.get("item_paging_profiles") or {}
        if profile_name:
            profile = profiles.get(str(profile_name).lower())
            if isinstance(profile, dict):
                return profile
        profile = profiles.get(str(total_items))
        if isinstance(profile, dict):
            return profile
        return self.black_market_ui.get("item_paging", {})

    def get_tier_dropdown_for_profile(self, tier_profile):
        tier_profiles = self.black_market_ui.get("tier_dropdown_profiles", {})
        if tier_profile in tier_profiles:
            return tier_profiles[tier_profile]
        if "default" in tier_profiles:
            return tier_profiles["default"]
        return self.black_market_ui.get("tier_dropdown", {})

    def get_tier_mapping_profile_for_item(self, item_name):
        normalized_item = self._normalize_item_name(item_name)
        for group_name, items in self.item_tier_groups.items():
            normalized_items = {self._normalize_item_name(item) for item in items}
            if normalized_item in normalized_items:
                return group_name
        return "default"

    def get_item_index(self, category, item_name):
        return self.item_indexes.get(category, {}).get(self._normalize_item_name(item_name))

    def print_row_hint(self, index, total, row):
        city_price = self._int_or_default(row.get(f"{self.active_city} venda min"), 0)
        black_market_price = self._int_or_default(row.get("Black Market pedido venda"), 0)
        profit = black_market_price - city_price if city_price and black_market_price else 0
        print(
            f"\n[{index}/{total}] {row.get('Item')} {row.get('Tier')}{row.get('Encantamento')}"
            f" | {self.active_city}: {self._format_silver(row.get(f'{self.active_city} venda min'))}"
            f" | BM venda: {self._format_silver(row.get('Black Market pedido venda'))}"
            f" | lucro: {self._format_silver(profit)}"
            f" | quantidade: {self.quantity_per_item}"
        )

    def _normalize_item_name(self, item_name):
        value = str(item_name or "")
        for broken, fixed in MOJIBAKE_REPLACEMENTS.items():
            value = value.replace(broken, fixed)
        normalized = unicodedata.normalize("NFD", value)
        normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return normalized.casefold().strip()

    def normalize_enchantment(self, enchantment):
        value = str(enchantment or "0").strip()
        if not value:
            return ".0"
        if value.startswith("."):
            return value
        return f".{value}"

    def _format_silver(self, value):
        number = self._int_or_default(value, 0)
        return f"{number:,}".replace(",", ".") if number else "-"

    def _int_or_default(self, value, default):
        try:
            if value in (None, ""):
                return default
            return int(str(value).replace(".", "").replace(",", ".").split(".")[0])
        except (TypeError, ValueError):
            return default

    def _float_or_default(self, value, default):
        try:
            if value in (None, ""):
                return default
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return default
