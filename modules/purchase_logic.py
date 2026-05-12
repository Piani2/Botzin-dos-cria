"""Logica de decisao para compra de itens."""

from dataclasses import dataclass
import unicodedata

from modules.market_data import repair_mojibake


PURCHASE_TIER_GROUPS = [
    ("T5.0", [("T5", ".0")]),
    ("T5.1 e T6.0", [("T5", ".1"), ("T6", ".0")]),
    ("T6.1 e T7.0", [("T6", ".1"), ("T7", ".0")]),
    ("T8.2 e T8.3", [("T8", ".2"), ("T8", ".3")]),
]

CHEAP_TIER_KEYS = {"T5.0", "T5.1", "T6.0", "T6.1", "T7.0"}


@dataclass
class PurchaseCandidate:
    item_name: str
    category: str
    tier: str
    enchantment: str
    target_price: int
    quantity_sold: int
    max_buy_price: int
    remaining_limit: int

    @property
    def tier_key(self):
        return f"{self.tier}{self.enchantment}"


class PurchaseBank:
    """Orcamento de compra que diminui a cada unidade comprada."""

    def __init__(self, initial_silver):
        self.initial_silver = max(0, int(initial_silver))
        self.remaining_silver = self.initial_silver
        self.spent_silver = 0

    def can_afford(self, price):
        return price > 0 and self.remaining_silver >= price

    def record_purchase(self, price):
        if not self.can_afford(price):
            return False
        self.remaining_silver -= price
        self.spent_silver += price
        return True


class PurchasePlanner:
    def __init__(self, market_data, category_items, profit_margin_percent=50):
        self.market_data = market_data or {}
        self.category_items = {
            category: {self._normalize_item_name(item) for item in items}
            for category, items in (category_items or {}).items()
        }
        self.profit_margin_percent = max(0, float(profit_margin_percent))

    def build_candidates(self, categories, enabled_tiers, cheap_tier_limits=None):
        cheap_tier_limits = cheap_tier_limits or {}
        categories = set(categories)
        enabled_tiers = set(enabled_tiers)
        candidates = []

        for item_name, tiers in self.market_data.items():
            category = self._category_for_item(item_name)
            if category not in categories:
                continue

            for tier, enchants in tiers.items():
                for enchantment, data in enchants.items():
                    tier_key = f"{tier}{enchantment}"
                    if tier_key not in enabled_tiers:
                        continue

                    target_price = int(data.get("price") or 0)
                    quantity_sold = int(data.get("quantity_sold") or 0)
                    if target_price <= 0 or quantity_sold <= 0:
                        continue

                    max_buy_price = self.max_profitable_buy_price(target_price)
                    if max_buy_price <= 0:
                        continue

                    limit = quantity_sold
                    if tier_key in CHEAP_TIER_KEYS and cheap_tier_limits.get(tier_key):
                        limit = min(quantity_sold, int(cheap_tier_limits[tier_key]))

                    if limit <= 0:
                        continue

                    candidates.append(
                        PurchaseCandidate(
                            item_name=item_name,
                            category=category,
                            tier=tier,
                            enchantment=enchantment,
                            target_price=target_price,
                            quantity_sold=quantity_sold,
                            max_buy_price=max_buy_price,
                            remaining_limit=limit,
                        )
                    )

        candidates.sort(
            key=lambda candidate: (
                candidate.tier,
                candidate.enchantment,
                candidate.item_name.casefold(),
            )
        )
        return candidates

    def max_profitable_buy_price(self, target_price):
        multiplier = 1 + (self.profit_margin_percent / 100)
        return int(target_price / multiplier)

    def is_profitable(self, candidate, live_buy_price):
        if live_buy_price is None or live_buy_price <= 0:
            return False
        return live_buy_price <= candidate.max_buy_price

    def max_units_for_live_offer(self, candidate, live_buy_price, bank):
        if not self.is_profitable(candidate, live_buy_price):
            return 0
        if candidate.remaining_limit <= 0:
            return 0
        if not bank.can_afford(live_buy_price):
            return 0
        return min(candidate.remaining_limit, bank.remaining_silver // live_buy_price)

    def _category_for_item(self, item_name):
        normalized_item = self._normalize_item_name(item_name)
        for category, items in self.category_items.items():
            if normalized_item in items:
                return category
        return None

    def _normalize_item_name(self, item_name):
        repaired = repair_mojibake(item_name or "")
        normalized = unicodedata.normalize("NFD", repaired)
        normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return normalized.casefold().strip()
