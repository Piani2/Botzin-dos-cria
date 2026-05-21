"""Calibra filtros, botoes e regioes da loja."""

from calibration_utils import capture_point, capture_region, ensure_path, load_config, save_config


TIER_PROFILES = [
    ("default", "Padrao"),
    ("t1_to_t8", "Itens que mostram T1-T8"),
    ("t2_to_t8", "Itens que mostram T2-T8"),
    ("t3_to_t8", "Itens que mostram T3-T8"),
]

TIERS = ["T5", "T6", "T7", "T8"]
ENCHANTMENTS = [".0", ".1", ".2", ".3"]
QUALITIES = [
    ("normal", "Normal"),
    ("bom", "Bom"),
    ("excepcional", "Excepcional"),
]


def calibrate_dropdown(option_labels, open_prompt, option_prompt):
    dropdown = {
        "open": capture_point(open_prompt),
        "options": {},
    }

    input("Abra o dropdown no jogo e pressione ENTER para capturar as opcoes...")
    for key, label in option_labels:
        dropdown["options"][key] = capture_point(option_prompt.format(label=label, key=key))

    return dropdown


def calibrate_tier(config):
    print("\nQual perfil de tier voce quer calibrar?")
    for index, (_, label) in enumerate(TIER_PROFILES, start=1):
        print(f"{index}. {label}")

    choice = input("\nEscolha: ").strip()
    try:
        profile_key = TIER_PROFILES[int(choice) - 1][0]
    except (ValueError, IndexError):
        print("Opcao invalida; usando default.")
        profile_key = "default"

    tier_dropdown = calibrate_dropdown(
        [(tier, tier) for tier in TIERS],
        f"Botao que abre o dropdown de tier do perfil {profile_key}",
        "Opcao {label} no dropdown de tier",
    )

    black_market_ui = ensure_path(config, "black_market_ui")
    tier_profiles = ensure_path(config, "black_market_ui", "tier_dropdown_profiles")
    tier_profiles[profile_key] = tier_dropdown

    if profile_key == "default":
        black_market_ui["tier_dropdown"] = tier_dropdown

    print(f"Tier salvo no perfil '{profile_key}'.")


def calibrate_enchantment(config):
    enchant_dropdown = calibrate_dropdown(
        [(enchantment, enchantment) for enchantment in ENCHANTMENTS],
        "Botao que abre o dropdown de encantamento",
        "Opcao {label} no dropdown de encantamento",
    )
    ensure_path(config, "black_market_ui")["enchant_dropdown"] = enchant_dropdown
    print("Encantamento salvo.")


def calibrate_quality(config):
    quality_dropdown = calibrate_dropdown(
        QUALITIES,
        "Botao que abre o dropdown de qualidade",
        "Opcao de qualidade {label}",
    )
    ensure_path(config, "black_market_ui")["quality_dropdown"] = quality_dropdown
    print("Qualidade salva.")


def calibrate_close_tab(config):
    ensure_path(config, "black_market_ui")["item_tab_close"] = capture_point(
        "Botao de fechar a aba/detalhe do item"
    )
    print("Botao de fechar aba salvo.")


def calibrate_search_box(config):
    ensure_path(config, "black_market_ui")["search_box"] = capture_point(
        "Campo/botao onde o bot clica para escrever o nome do item na loja"
    )
    print("Campo de pesquisa salvo.")


def calibrate_price_region(config):
    ensure_path(config, "black_market_ui")["price_region"] = capture_region(
        "Regiao onde aparece o preco do primeiro item/listagem para leitura."
    )
    print("Regiao de preco salva.")


def calibrate_buy_button(config):
    ensure_path(config, "black_market_ui")["buy_button"] = capture_point(
        "Botao de comprar o item selecionado"
    )
    print("Botao de compra salvo.")


def main():
    print("=== CALIBRAR FILTROS DA LOJA ===")
    print("Este calibrador salva tier, encantamento, qualidade, pesquisa, preco, comprar e fechar aba.")

    while True:
        config = load_config()
        print("\n1. Calibrar tier")
        print("2. Calibrar encantamento")
        print("3. Calibrar qualidade")
        print("4. Calibrar fechar aba")
        print("5. Calibrar campo de pesquisa")
        print("6. Calibrar regiao de preco")
        print("7. Calibrar botao comprar")
        print("8. Sair")
        choice = input("\nEscolha: ").strip()

        if choice == "1":
            calibrate_tier(config)
        elif choice == "2":
            calibrate_enchantment(config)
        elif choice == "3":
            calibrate_quality(config)
        elif choice == "4":
            calibrate_close_tab(config)
        elif choice == "5":
            calibrate_search_box(config)
        elif choice == "6":
            calibrate_price_region(config)
        elif choice == "7":
            calibrate_buy_button(config)
        elif choice == "8":
            break
        else:
            print("Opcao invalida.")
            continue

        save_config(config)
        print("Alteracoes salvas em store_navigation.json.")


if __name__ == "__main__":
    main()
