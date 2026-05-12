"""
Recalibra apenas os dropdowns de Tier/Enchant no Mercado Negro.
Captura coordenadas por clique global do mouse (sem depender de Enter/foco no terminal).

Uso:
    python recalibrar_dropdowns.py
"""

import threading
import time

import yaml
from pynput import keyboard, mouse

CONFIG_FILE = "config.yaml"

STEPS = [
    ("tier_open", "Clique no botão que ABRE o dropdown de Tier"),
    ("tier_T5", "Clique 2x: (1) abrir dropdown de Tier, (2) opção T5"),
    ("tier_T6", "Clique 2x: (1) abrir dropdown de Tier, (2) opção T6"),
    ("tier_T7", "Clique 2x: (1) abrir dropdown de Tier, (2) opção T7"),
    ("tier_T8", "Clique 2x: (1) abrir dropdown de Tier, (2) opção T8"),
    ("enchant_open", "Clique no botão que ABRE o dropdown de Enchant"),
    ("enchant_0", "Clique 2x: (1) abrir dropdown de Enchant, (2) opção .0"),
    ("enchant_1", "Clique 2x: (1) abrir dropdown de Enchant, (2) opção .1"),
    ("enchant_2", "Clique 2x: (1) abrir dropdown de Enchant, (2) opção .2"),
    ("enchant_3", "Clique 2x: (1) abrir dropdown de Enchant, (2) opção .3"),
]


def capture_click(prompt_text):
    print("\n" + prompt_text)
    print("  -> Aguardando clique esquerdo... (ESC cancela)")

    done = threading.Event()
    cancelled = threading.Event()
    result = {"point": None}

    def on_click(x, y, button, pressed):
        if cancelled.is_set() or done.is_set():
            return False
        if pressed and button == mouse.Button.left:
            result["point"] = [int(x), int(y)]
            done.set()
            return False

    def on_press(key):
        if key == keyboard.Key.esc:
            cancelled.set()
            done.set()
            return False

    m_listener = mouse.Listener(on_click=on_click)
    k_listener = keyboard.Listener(on_press=on_press)

    m_listener.start()
    k_listener.start()

    while not done.is_set():
        time.sleep(0.02)

    m_listener.stop()
    k_listener.stop()

    if cancelled.is_set() or result["point"] is None:
        return None

    print(f"  ✓ Capturado: {tuple(result['point'])}")
    return result["point"]


def capture_two_clicks_second(prompt_text):
    """Captura dois cliques e retorna apenas o segundo (opção do dropdown)."""
    print("\n" + prompt_text)
    print("  -> Aguardando 2 cliques esquerdos... (ESC cancela)")

    done = threading.Event()
    cancelled = threading.Event()
    clicks = []

    def on_click(x, y, button, pressed):
        if cancelled.is_set() or done.is_set():
            return False
        if pressed and button == mouse.Button.left:
            clicks.append([int(x), int(y)])
            print(f"    clique {len(clicks)}/2: {tuple(clicks[-1])}")
            if len(clicks) >= 2:
                done.set()
                return False

    def on_press(key):
        if key == keyboard.Key.esc:
            cancelled.set()
            done.set()
            return False

    m_listener = mouse.Listener(on_click=on_click)
    k_listener = keyboard.Listener(on_press=on_press)

    m_listener.start()
    k_listener.start()

    while not done.is_set():
        time.sleep(0.02)

    m_listener.stop()
    k_listener.stop()

    if cancelled.is_set() or len(clicks) < 2:
        return None

    second = clicks[1]
    print(f"  ✓ Opção capturada (2º clique): {tuple(second)}")
    return second


def main():
    print("\n=== Recalibrador de Dropdowns (Tier/Enchant) ===\n")
    print("Abra o Albion na tela de venda do Mercado Negro antes de continuar.")
    print("Esse script só recalibra os botões de Tier/Enchant e preserva o restante do config.")

    captured = {}
    for key, prompt in STEPS:
        if key.startswith("tier_T") or key.startswith("enchant_") and key != "enchant_open":
            point = capture_two_clicks_second(prompt)
        else:
            point = capture_click(prompt)
        if point is None:
            print("\n✗ Calibração cancelada.")
            return
        captured[key] = point
        time.sleep(0.15)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        config = {}

    black_market_ui = config.get("black_market_ui", {})
    tier_dropdown = black_market_ui.get("tier_dropdown", {})
    enchant_dropdown = black_market_ui.get("enchant_dropdown", {})

    tier_dropdown["open"] = captured["tier_open"]
    tier_dropdown["options"] = {
        "T5": captured["tier_T5"],
        "T6": captured["tier_T6"],
        "T7": captured["tier_T7"],
        "T8": captured["tier_T8"],
    }

    enchant_dropdown["open"] = captured["enchant_open"]
    enchant_dropdown["options"] = {
        ".0": captured["enchant_0"],
        ".1": captured["enchant_1"],
        ".2": captured["enchant_2"],
        ".3": captured["enchant_3"],
    }

    black_market_ui["tier_dropdown"] = tier_dropdown
    black_market_ui["enchant_dropdown"] = enchant_dropdown
    config["black_market_ui"] = black_market_ui

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print("\n✅ Recalibração concluída e salva em config.yaml")


if __name__ == "__main__":
    main()
