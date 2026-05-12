"""Calibra e testa a paginacao da lista de itens do Mercado Negro."""

import sys
import time

import keyboard
import pyautogui
import yaml


CONFIG_FILE = "config.yaml"


def wait_enter():
    keyboard.wait("enter")
    while keyboard.is_pressed("enter"):
        time.sleep(0.05)


def capture_point(prompt):
    print(f"\n{prompt}")
    print("Posicione o mouse e pressione ENTER.")
    wait_enter()
    x, y = pyautogui.position()
    print(f"Registrado: ({x}, {y})")
    time.sleep(0.2)
    return [int(x), int(y)]


def read_int(prompt, default):
    value = input(f"{prompt} [{default}]: ").strip()
    if not value:
        return default
    try:
        return max(1, int(value))
    except ValueError:
        print(f"Valor invalido, usando {default}.")
        return default


def read_yes_no(prompt, default=True):
    suffix = "S/n" if default else "s/N"
    value = input(f"{prompt} ({suffix}): ").strip().lower()
    if not value:
        return default
    return value.startswith("s")


def choose_item_group(default="armas"):
    groups = {
        "1": ("armas", 48),
        "2": ("armaduras", 38),
        "3": ("manual", None),
    }
    default_option = "1" if default == "armas" else "2"

    print("\nO que voce vai calibrar?")
    print("1 - Armas (48 itens)")
    print("2 - Armaduras (38 itens)")
    print("3 - Manual")
    option = input(f"Escolha [1/2/3] [{default_option}]: ").strip() or default_option
    group_name, total_items = groups.get(option, groups[default_option])

    if total_items is None:
        total_items = read_int("Quantos itens existem neste conjunto?", 48)

    return group_name, total_items


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as file_handle:
        return yaml.safe_load(file_handle) or {}


def infer_total_items_from_paging(paging):
    if not isinstance(paging, dict):
        return None

    if paging.get("total_items"):
        try:
            return int(paging.get("total_items"))
        except (TypeError, ValueError):
            return None

    page_size = max(1, int(paging.get("page_size", 5) or 5))
    page_row_positions = paging.get("page_row_positions") or {}
    if page_row_positions:
        numeric_pages = [int(page) for page in page_row_positions.keys() if str(page).isdigit()]
        if numeric_pages:
            last_page = max(numeric_pages)
            last_rows = page_row_positions.get(str(last_page)) or []
            if last_rows:
                return (last_page * page_size) + len(last_rows)

    drag_steps = paging.get("drag_steps") or []
    row_positions = paging.get("row_positions") or []
    if drag_steps and row_positions:
        return (len(drag_steps) * page_size) + len(row_positions)

    return None


def test_calibration():
    config = load_config()
    black_market_ui = config.get("black_market_ui", {})
    default_paging = black_market_ui.get("item_paging", {})
    profiles = black_market_ui.get("item_paging_profiles") or {}
    default_page_size = max(1, int(default_paging.get("page_size", 5) or 5))
    default_drag_steps = default_paging.get("drag_steps") or []
    default_rows = default_paging.get("row_positions") or []
    default_total = infer_total_items_from_paging(default_paging)
    if not default_total:
        default_total = (len(default_drag_steps) * default_page_size) + len(default_rows)
    group_name, total_items = choose_item_group("armas")
    if not total_items:
        total_items = default_total
    paging = profiles.get(group_name) or profiles.get(str(total_items)) or default_paging
    if not paging:
        print("Nenhuma calibracao item_paging encontrada em config.yaml.")
        return

    page_size = max(1, int(paging.get("page_size", 5)))
    drag_steps = paging.get("drag_steps") or []
    page_row_positions = paging.get("page_row_positions") or {}
    default_rows = paging.get("row_positions") or []
    click_items = read_yes_no("Deseja clicar nos itens durante o teste?", False)

    print(f"\nTestando perfil: {group_name} ({total_items} itens).")
    print("Abra a lista no topo, como ela fica antes de iniciar a coleta.")
    print("Pressione ENTER para iniciar o teste. Mova o mouse para o canto da tela para abortar pelo failsafe.")
    wait_enter()

    reset_key = paging.get("reset_key", "home")
    if reset_key:
        pyautogui.press(reset_key)
        time.sleep(0.4)

    current_page = 0
    total_pages = (total_items + page_size - 1) // page_size

    for page in range(total_pages):
        if page > current_page:
            step = drag_steps[page - 1] if page - 1 < len(drag_steps) else None
            if step:
                start = step.get("start")
                end = step.get("end")
                print(f"\nDescida {page}: {start} -> {end}")
                pyautogui.moveTo(start[0], start[1], duration=0.08)
                pyautogui.dragTo(end[0], end[1], duration=float(paging.get("drag_duration", 0.35)), button="left")
            else:
                scroll_amount = int(paging.get("scroll_per_page", -600))
                print(f"\nDescida {page}: wheel {scroll_amount}")
                pyautogui.scroll(scroll_amount)
            current_page = page
            time.sleep(0.5)

        rows = page_row_positions.get(str(page)) or default_rows
        items_on_page = min(page_size, total_items - (page * page_size))
        print(f"\nPagina {page + 1}/{total_pages}")
        for row in range(items_on_page):
            if row >= len(rows):
                print(f"Sem ponto calibrado para linha {row + 1}; pulando.")
                continue
            x, y = rows[row]
            item_number = (page * page_size) + row + 1
            print(f"Item {item_number}: ({x}, {y})")
            pyautogui.moveTo(x, y, duration=0.12)
            if click_items:
                pyautogui.click(x, y)
            time.sleep(0.25)

    print("\nTeste concluido.")


def calibrate():
    print("\n=== Calibrador de scroll da lista de itens ===")
    print("Abra o Mercado Negro na lista de itens, no topo da lista.")
    print("Este calibrador salva as linhas visiveis e um arrasto para cada descida.")

    group_name, total_items = choose_item_group("armas")
    page_size = read_int("Quantos itens ficam visiveis por pagina?", 5)
    drag_count = (total_items - 1) // page_size
    last_count = total_items - (drag_count * page_size)

    print(
        f"\nPara {total_items} itens com {page_size} por pagina: "
        f"{drag_count} descidas e {last_count} item(ns) na ultima pagina."
    )

    row_positions = []
    for index in range(1, page_size + 1):
        row_positions.append(capture_point(f"Item visivel {index}/{page_size}"))

    drag_steps = []
    for index in range(1, drag_count + 1):
        print(f"\n--- Descida {index}/{drag_count} ---")
        drag_start = capture_point("Ponto inicial do arrasto desta descida")
        drag_end = capture_point("Ponto final do arrasto desta descida")
        drag_steps.append({"start": drag_start, "end": drag_end})

    page_row_positions = {}
    if last_count != page_size:
        last_positions = []
        print(f"\n--- Posicoes da ultima pagina apos a descida {drag_count} ---")
        for index in range(1, last_count + 1):
            last_positions.append(capture_point(f"Item final {index}/{last_count}"))
        page_row_positions[str(drag_count)] = last_positions

    config = load_config()

    black_market_ui = config.setdefault("black_market_ui", {})
    black_market_ui["item_list_first"] = row_positions[0]
    if len(row_positions) >= 2:
        black_market_ui["item_list_row_step"] = abs(row_positions[1][1] - row_positions[0][1])

    profiles = black_market_ui.setdefault("item_paging_profiles", {})
    existing_paging = black_market_ui.get("item_paging")
    existing_total = infer_total_items_from_paging(existing_paging)
    if existing_total and str(existing_total) not in profiles:
        profiles[str(existing_total)] = existing_paging

    paging_config = {
        "enabled": True,
        "profile": group_name,
        "total_items": total_items,
        "page_size": page_size,
        "method": "drag",
        "reset_key": "home",
        "drag_steps": drag_steps,
        "drag_duration": 0.35,
        "row_positions": row_positions,
        "page_row_positions": page_row_positions,
    }
    black_market_ui["item_paging"] = paging_config
    profiles[group_name] = paging_config
    profiles[str(total_items)] = paging_config

    with open(CONFIG_FILE, "w", encoding="utf-8") as file_handle:
        yaml.dump(config, file_handle, default_flow_style=False, allow_unicode=True)

    print(f"\nCalibracao salva em {CONFIG_FILE}.")
    print(
        f"Perfil {group_name} ({total_items} itens) salvo. "
        f"O bot agora usa {drag_count} arrastos calibrados para este conjunto."
    )


def main():
    if len(sys.argv) > 1 and sys.argv[1].lower() in {"test", "teste", "--test"}:
        test_calibration()
    else:
        calibrate()


if __name__ == "__main__":
    main()
