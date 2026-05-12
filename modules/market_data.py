"""Armazenamento dos dados coletados do Mercado Negro."""

import json
import logging

logger = logging.getLogger(__name__)

MOJIBAKE_REPLACEMENTS = {
    "\u00c3\u00a1": "á",
    "\u00c3\u00a0": "à",
    "\u00c3\u00a2": "â",
    "\u00c3\u00a3": "ã",
    "\u00c3\u00a9": "é",
    "\u00c3\u00aa": "ê",
    "\u00c3\u00ad": "í",
    "\u00c3\u00b3": "ó",
    "\u00c3\u00b4": "ô",
    "\u00c3\u00b5": "õ",
    "\u00c3\u00ba": "ú",
    "\u00c3\u00a7": "ç",
    "\u00c3\u0081": "Á",
    "\u00c3\u0080": "À",
    "\u00c3\u0082": "Â",
    "\u00c3\u0083": "Ã",
    "\u00c3\u0089": "É",
    "\u00c3\u008a": "Ê",
    "\u00c3\u008d": "Í",
    "\u00c3\u0093": "Ó",
    "\u00c3\u0094": "Ô",
    "\u00c3\u0095": "Õ",
    "\u00c3\u009a": "Ú",
    "\u00c3\u0087": "Ç",
}


def repair_mojibake(value):
    """Corrige textos UTF-8 que foram lidos como Windows-1252."""
    if not isinstance(value, str):
        return value

    for broken, fixed in MOJIBAKE_REPLACEMENTS.items():
        value = value.replace(broken, fixed)
    return value


class MarketData:
    def __init__(self):
        self.data = {}

    def add_item(self, item_name, tier, enchantment, price, quantity_sold):
        item_name = repair_mojibake(item_name)

        if item_name not in self.data:
            self.data[item_name] = {}

        if tier not in self.data[item_name]:
            self.data[item_name][tier] = {}

        self.data[item_name][tier][enchantment] = {
            "price": price,
            "quantity_sold": quantity_sold,
        }
        logger.debug(
            f"Item adicionado: {item_name} {tier}{enchantment} - "
            f"Preço: {price}, Vendidos: {quantity_sold}"
        )

    def get_all_items(self):
        return self.data

    def save_to_json(self, filepath):
        try:
            self.data = self._repair_item_names(self.data)
            with open(filepath, "w", encoding="utf-8") as file_handle:
                json.dump(self.data, file_handle, indent=2, ensure_ascii=False)
            logger.info(f"Dados salvos em {filepath}")
        except Exception as e:
            logger.error(f"Erro ao salvar JSON: {e}")

    def load_from_json(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as file_handle:
                self.data = self._repair_item_names(json.load(file_handle))
            logger.info(f"Dados carregados de {filepath}")
        except Exception as e:
            logger.error(f"Erro ao carregar JSON: {e}")

    def export_for_html(self):
        try:
            html_data = []

            for item_name, tiers in self._repair_item_names(self.data).items():
                for tier in ["T5", "T6", "T7", "T8"]:
                    if tier not in tiers:
                        continue

                    row = {
                        "name": item_name,
                        "tier": tier,
                        "enchants": {},
                    }

                    for enchant in [".0", ".1", ".2", ".3"]:
                        if enchant in tiers[tier]:
                            data = tiers[tier][enchant]
                            row["enchants"][enchant] = {
                                "quantity": data["quantity_sold"],
                                "price": data["price"],
                            }
                        else:
                            row["enchants"][enchant] = None

                    html_data.append(row)

            return html_data
        except Exception as e:
            logger.error(f"Erro ao exportar para HTML: {e}")
            return []

    def _repair_item_names(self, data):
        repaired = {}
        for item_name, tiers in data.items():
            repaired[repair_mojibake(item_name)] = tiers
        return repaired
