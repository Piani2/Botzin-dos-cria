"""
Recalibra coordenadas dos tiers no dropdown (T5, T6, T7, T8) para um perfil específico.

Use este script quando algum grupo de itens exigir um mapeamento de clique diferente,
mas a coleta continuar limitada a T5-T8.
"""

import time
import yaml
from modules.automation_controller import AutomationController
from modules.screen_capture import ScreenCapture
import keyboard
import pyautogui

CONFIG_FILE = 'config.yaml'


def load_config():
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def resolve_open_coord(config, profile_name):
    black_market_ui = config.get('black_market_ui', {})
    tier_profiles = black_market_ui.get('tier_dropdown_profiles', {}) or {}

    profile_data = tier_profiles.get(profile_name, {}) if isinstance(tier_profiles, dict) else {}
    open_coord = profile_data.get('open')

    if not open_coord:
        open_coord = black_market_ui.get('tier_dropdown', {}).get('open')

    return open_coord


def save_profile(config, profile_name, open_coord, calibrated_coords):
    black_market_ui = config.setdefault('black_market_ui', {})
    tier_profiles = black_market_ui.setdefault('tier_dropdown_profiles', {})

    profile_data = tier_profiles.get(profile_name, {})
    profile_data['open'] = open_coord
    profile_data['options'] = calibrated_coords
    tier_profiles[profile_name] = profile_data

    if profile_name == 'default':
        black_market_ui['tier_dropdown'] = {
            'open': open_coord,
            'options': calibrated_coords,
        }

    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def get_profile_options(config, profile_name):
    black_market_ui = config.get('black_market_ui', {})
    tier_profiles = black_market_ui.get('tier_dropdown_profiles', {}) or {}

    profile_data = tier_profiles.get(profile_name, {}) if isinstance(tier_profiles, dict) else {}
    options = profile_data.get('options')
    if isinstance(options, dict) and options:
        return dict(options)

    legacy_options = black_market_ui.get('tier_dropdown', {}).get('options', {})
    if isinstance(legacy_options, dict):
        return dict(legacy_options)

    return {}

config = load_config()
controller = AutomationController(config.get('automation', {}))
screen = ScreenCapture(region=config.get('screenshot_region'))

black_market_ui = config.get('black_market_ui', {})
profile_name = input("Nome do perfil de mapeamento [default/t1_to_t8/t2_to_t8/t3_to_t8]: ").strip() or 'default'
open_coord = resolve_open_coord(config, profile_name)

print("=== RECALIBRAÇÃO DE TIERS ===\n")
print(f"Perfil selecionado: {profile_name}")

if not open_coord:
    print("❌ Coordenada de abertura do dropdown não encontrada!")
    exit(1)

print(f"Coordenada de abertura: {open_coord}")

tiers_input = input(
    "Quais tiers recalibrar? [todos/T5,T6,T7,T8] (padrão: todos): "
).strip().upper()

all_tiers = ['T5', 'T6', 'T7', 'T8']
if not tiers_input or tiers_input == 'TODOS':
    tiers = all_tiers
else:
    requested = [tier.strip() for tier in tiers_input.split(',') if tier.strip()]
    tiers = [tier for tier in all_tiers if tier in requested]
    if not tiers:
        print("❌ Nenhum tier válido informado. Use T5,T6,T7,T8 ou 'todos'.")
        exit(1)

print("Pressione ENTER para começar...\n")
keyboard.wait('enter')

calibrated_coords = get_profile_options(config, profile_name)

for tier in tiers:
    print(f"\n{'='*50}")
    print(f"Calibrando {tier}")
    print(f"{'='*50}")
    
    print("1. Abrindo dropdown...")
    controller.click(open_coord[0], open_coord[1])
    time.sleep(0.3)
    
    print("2. Posicione o mouse EXATAMENTE no centro de {tier}".format(tier=tier))
    print("   (quando estiver correto, pressione ENTER)")
    
    keyboard.wait('enter')
    
    # Captura posição do mouse
    x, y = pyautogui.position()
    calibrated_coords[tier] = [x, y]
    
    print(f"   ✓ Posição capturada: [{x}, {y}]")
    
    # Clica para confirmar seleção
    print("3. Clicando para confirmar...")
    controller.click(x, y)
    time.sleep(0.5)

print(f"\n{'='*50}")
print("RESUMO DAS COORDENADAS CALIBRADAS:")
print(f"{'='*50}\n")

for tier in all_tiers:
    coord = calibrated_coords.get(tier)
    if not coord:
        continue
    print(f"{tier}: {coord}")

# Salva no config
print("\nSalvando coordenadas no config.yaml...")
save_profile(config, profile_name, open_coord, calibrated_coords)

print("✓ Coordenadas salvas com sucesso!")
print("\nAgora use o perfil correspondente no coletor para validar as novas coordenadas.")
