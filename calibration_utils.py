"""Utilitarios compartilhados pelos calibradores de navegacao."""

import json
from pathlib import Path

import pyautogui


CONFIG_PATH = Path("store_navigation.json")


def load_config():
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle) or {}


def save_config(config):
    CONFIG_PATH.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def ensure_path(config, *keys):
    current = config
    for key in keys:
        current = current.setdefault(key, {})
    return current


def capture_point(prompt):
    input(f"{prompt}\nPosicione o mouse e pressione ENTER...")
    position = pyautogui.position()
    point = [int(position.x), int(position.y)]
    print(f"Capturado: {point}")
    return point


def ask_int(prompt, default=None, minimum=None, maximum=None):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        value = input(f"{prompt}{suffix}: ").strip()
        if not value and default is not None:
            return int(default)
        try:
            parsed = int(value)
        except ValueError:
            print("Digite um numero valido.")
            continue
        if minimum is not None and parsed < minimum:
            print(f"Digite um valor maior ou igual a {minimum}.")
            continue
        if maximum is not None and parsed > maximum:
            print(f"Digite um valor menor ou igual a {maximum}.")
            continue
        return parsed


def ask_yes_no(prompt, default=False):
    suffix = "S/n" if default else "s/N"
    value = input(f"{prompt} ({suffix}): ").strip().lower()
    if not value:
        return default
    return value.startswith("s")
