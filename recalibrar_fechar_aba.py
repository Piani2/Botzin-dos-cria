"""
Mapeia a coordenada do botao de fechar aba do item no Mercado Negro.

Uso:
    python recalibrar_fechar_aba.py
"""

import time
import yaml
import pyautogui
import keyboard

CONFIG_FILE = 'config.yaml'


def load_config():
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def wait_enter():
    keyboard.wait('enter')
    while keyboard.is_pressed('enter'):
        time.sleep(0.05)


def main():
    print('\n=== Mapeamento do botao Fechar Aba ===\n')
    print('1) Abra um item no Mercado Negro para aparecer a aba/detalhe.')
    print('2) Posicione o mouse exatamente no botao X de fechar aba.')
    print('3) Pressione ENTER para capturar a coordenada.\n')

    wait_enter()
    x, y = pyautogui.position()
    print(f'Coordenada capturada: ({x}, {y})')

    config = load_config()
    black_market_ui = config.setdefault('black_market_ui', {})
    black_market_ui['item_tab_close'] = [int(x), int(y)]

    save_config(config)
    print('\nSalvo em config.yaml: black_market_ui.item_tab_close')
    print('Agora o coletor fechara a aba por clique nesse botao (sem usar ESC).')


if __name__ == '__main__':
    main()
