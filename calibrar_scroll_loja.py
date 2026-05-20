"""Calibra a navegacao de scroll/lista da loja sem OCR."""

from calibration_utils import (
    ask_int,
    ask_yes_no,
    capture_point,
    ensure_path,
    load_config,
    save_config,
)


PAGE_SIZE = 5


def choose_profile():
    print("\nQual lista voce quer calibrar?")
    print("1. Armas")
    print("2. Armaduras")
    print("3. Manual")
    choice = input("\nEscolha: ").strip()

    if choice == "1":
        return "armas", 48
    if choice == "2":
        return "armaduras", 38

    profile = input("Nome do perfil manual: ").strip().lower() or "manual"
    total_items = ask_int("Total de itens nessa lista", minimum=1)
    return profile, total_items


def capture_page_rows(page_index, row_count):
    print(f"\nPagina {page_index + 1}: capture os {row_count} itens visiveis.")
    rows = []
    for row_index in range(row_count):
        rows.append(
            capture_point(
                f"Item {row_index + 1}/{row_count} da pagina {page_index + 1}"
            )
        )
    return rows


def capture_drag_step(step_index):
    print(f"\nScroll/arrasto {step_index + 1}")
    start = capture_point("Ponto INICIAL do arrasto da lista")
    end = capture_point("Ponto FINAL do arrasto da lista")
    return {
        "start": start,
        "end": end,
    }


def calibrate_scroll():
    config = load_config()
    black_market_ui = ensure_path(config, "black_market_ui")
    profiles = ensure_path(config, "black_market_ui", "item_paging_profiles")

    profile, default_total_items = choose_profile()
    scroll_count = ask_int("Quantos scrolls/arrastos ate chegar no fim", minimum=0)
    has_different_last_page = ask_yes_no(
        "Depois do ultimo scroll ficam menos de 5 itens diferentes visiveis?"
    )
    if has_different_last_page:
        final_page_count = ask_int("Quantos itens ficam na ultima pagina", minimum=1, maximum=PAGE_SIZE)
    else:
        final_page_count = PAGE_SIZE

    computed_total = (scroll_count * PAGE_SIZE) + final_page_count
    total_items = ask_int("Total de itens do perfil", default=default_total_items or computed_total, minimum=1)
    if total_items != computed_total:
        print(
            f"Aviso: pelos scrolls foi calculado {computed_total} itens, "
            f"mas voce informou {total_items}. Vou salvar o total informado."
        )

    row_positions_by_page = {}
    drag_steps = []

    for page_index in range(scroll_count + 1):
        row_count = final_page_count if page_index == scroll_count else PAGE_SIZE
        row_positions_by_page[str(page_index)] = capture_page_rows(page_index, row_count)

        if page_index < scroll_count:
            drag_steps.append(capture_drag_step(page_index))
            input("Execute esse scroll/arrasto no jogo se ainda nao executou, e pressione ENTER para calibrar a proxima pagina...")

    profile_data = {
        "enabled": True,
        "method": "drag",
        "profile": profile,
        "page_size": PAGE_SIZE,
        "total_items": total_items,
        "reset_key": "home",
        "drag_duration": 0.35,
        "row_positions": row_positions_by_page.get("0", []),
        "page_row_positions": row_positions_by_page,
        "drag_steps": drag_steps,
    }

    profiles[profile] = profile_data
    profiles[str(total_items)] = profile_data
    if profile == "armas":
        black_market_ui["item_paging"] = profile_data

    save_config(config)
    print(f"\nCalibracao de scroll salva em store_navigation.json no perfil '{profile}'.")


def main():
    print("=== CALIBRAR SCROLL DA LOJA ===")
    print("Este calibrador salva apenas coordenadas de clique e arrasto.")
    print("Nao ha print, OCR ou leitura da tela.")
    calibrate_scroll()


if __name__ == "__main__":
    main()
