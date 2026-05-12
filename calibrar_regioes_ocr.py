"""
Calibrador de regiões OCR (preço e quantidade)
Captura cliques globais diretamente na tela do jogo.
"""

import threading
import time

import pyautogui
import yaml
from pynput import keyboard, mouse

from modules.automation_controller import AutomationController
from modules.screen_capture import ScreenCapture

CONFIG_FILE = 'config.yaml'

def main():
    print("\n=== Calibrador de Regiões OCR ===\n")
    
    # Carregar config
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)
    
    black_market_ui = config.get('black_market_ui', {})
    qty_hover = black_market_ui.get('quantity_hover', [1163, 548])
    
    screen = ScreenCapture(region=config.get('screenshot_region'))
    controller = AutomationController(config.get('automation', {}))
    
    # 1. Clicar no primeiro item
    print("1. Clicando no primeiro item...")
    first_x, first_y = black_market_ui.get('item_list_first', [1046, 363])
    controller.click(first_x, first_y)
    time.sleep(1.0)
    
    # 2. Abrir tier e encantamento
    print("2. Selecionando T5 .0...")
    tier_dropdown = black_market_ui.get('tier_dropdown', {})
    if tier_dropdown and tier_dropdown.get('open'):
        controller.click(tier_dropdown['open'][0], tier_dropdown['open'][1])
        time.sleep(0.3)
        if tier_dropdown.get('options', {}).get('T5'):
            controller.click(tier_dropdown['options']['T5'][0], tier_dropdown['options']['T5'][1])
        time.sleep(0.3)
    
    enchant_dropdown = black_market_ui.get('enchant_dropdown', {})
    if enchant_dropdown and enchant_dropdown.get('open'):
        controller.click(enchant_dropdown['open'][0], enchant_dropdown['open'][1])
        time.sleep(0.3)
        if enchant_dropdown.get('options', {}).get('.0'):
            controller.click(enchant_dropdown['options']['.0'][0], enchant_dropdown['options']['.0'][1])
        time.sleep(0.3)
    
    # 3. Hover na quantidade
    print("3. Hovering na quantidade...")
    controller.move_mouse(qty_hover[0], qty_hover[1], duration=0.5)
    time.sleep(1.0)
    
    # 4. Capturar screenshot
    print("4. Capturando screenshot...")
    screenshot = screen.capture()
    if not screenshot:
        print("Erro ao capturar!")
        return
    
    screenshot.save('calibrar_ocr_screenshot.png')
    print("   Salvo: calibrar_ocr_screenshot.png")
    
    # 5. Deixar o usuário marcar as regiões
    print("\n5. Agora você vai marcar as regiões onde PREÇO e QUANTIDADE aparecem")
    print("   Na janela que vai abrir:")
    print("   - Clique 1 vez no canto SUPERIOR ESQUERDO do PREÇO")
    print("   - Clique 1 vez no canto INFERIOR DIREITO do PREÇO")
    print("   - Depois faça o mesmo para a QUANTIDADE")
    print("   - Faça 4 cliques no jogo: preço TL, preço BR, quantidade TL, quantidade BR")
    print("   - Use ESC para cancelar")

    time.sleep(2)

    marked_regions = mark_regions_interactive(screenshot)
    
    if marked_regions:
        print("\n✓ Regiões marcadas:")
        price_region = marked_regions.get('price_region')
        quantity_region = marked_regions.get('quantity_region')
        
        if price_region:
            print(f"  Preço: {price_region}")
        if quantity_region:
            print(f"  Quantidade: {quantity_region}")

        if price_region:
            config['price_region'] = list(price_region)
        if quantity_region:
            config['quantity_region'] = list(quantity_region)

        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        print("✅ Salvo automaticamente em config.yaml")
    else:
        print("Nenhuma região marcada")


def mark_regions_interactive(screenshot):
    """Captura 4 cliques globais: preço TL/BR e quantidade TL/BR."""
    print("\nJanela de captura global ativa.")
    print("Clique no jogo nos seguintes pontos, nesta ordem:")
    print("  1. Canto superior esquerdo do PREÇO")
    print("  2. Canto inferior direito do PREÇO")
    print("  3. Canto superior esquerdo da QUANTIDADE")
    print("  4. Canto inferior direito da QUANTIDADE")
    print("Pressione ESC para cancelar.")

    points = []
    done = threading.Event()
    cancelled = threading.Event()

    def on_click(x, y, button, pressed):
        if cancelled.is_set() or done.is_set():
            return False
        if pressed and button == mouse.Button.left:
            points.append((int(x), int(y)))
            step_labels = [
                'preço (canto superior esquerdo)',
                'preço (canto inferior direito)',
                'quantidade (canto superior esquerdo)',
                'quantidade (canto inferior direito)',
            ]
            current_step = len(points)
            if current_step <= len(step_labels):
                print(f"  {current_step}/4 capturado: {points[-1]} -> {step_labels[current_step - 1]}")
            if len(points) >= 4:
                done.set()
                return False

    def on_press(key):
        if key == keyboard.Key.esc:
            cancelled.set()
            done.set()
            return False

    mouse_listener = mouse.Listener(on_click=on_click)
    keyboard_listener = keyboard.Listener(on_press=on_press)

    mouse_listener.start()
    keyboard_listener.start()

    while not done.is_set():
        time.sleep(0.05)

    mouse_listener.stop()
    keyboard_listener.stop()

    if cancelled.is_set() or len(points) < 4:
        print("Captura cancelada ou incompleta.")
        return None

    price_region = (
        min(points[0][0], points[1][0]),
        min(points[0][1], points[1][1]),
        max(points[0][0], points[1][0]),
        max(points[0][1], points[1][1]),
    )
    quantity_region = (
        min(points[2][0], points[3][0]),
        min(points[2][1], points[3][1]),
        max(points[2][0], points[3][0]),
        max(points[2][1], points[3][1]),
    )

    preview = screenshot.copy()
    from PIL import ImageDraw
    draw = ImageDraw.Draw(preview)
    draw.rectangle(price_region, outline='red', width=3)
    draw.rectangle(quantity_region, outline='blue', width=3)
    preview.save('calibrar_ocr_preview.png')

    return {
        'price_region': price_region,
        'quantity_region': quantity_region,
    }


if __name__ == '__main__':
    main()
