"""Controle simples de mouse e teclado para navegar na loja sem OCR."""

import logging
import time

import pyautogui

logger = logging.getLogger(__name__)


class AutomationController:
    def __init__(self, config=None):
        config = config or {}
        self.click_delay = float(config.get("click_delay", 0.35))
        pyautogui.FAILSAFE = True

    def click(self, x, y, button="left"):
        pyautogui.click(int(x), int(y), button=button)
        time.sleep(self.click_delay)
        logger.debug(f"Clique em ({x}, {y})")

    def type_text(self, text, interval=0.03):
        pyautogui.write(str(text), interval=interval)
        logger.debug(f"Texto digitado: {text}")

    def press_key(self, key):
        pyautogui.press(key)
        time.sleep(self.click_delay)
        logger.debug(f"Tecla pressionada: {key}")

    def hotkey(self, *keys):
        pyautogui.hotkey(*keys)
        time.sleep(self.click_delay)
        logger.debug(f"Hotkey: {'+'.join(keys)}")

    def move_mouse(self, x, y, duration=0.05):
        pyautogui.moveTo(int(x), int(y), duration=duration)
        logger.debug(f"Mouse movido para ({x}, {y})")

    def drag_from_to(self, start_x, start_y, end_x, end_y, duration=0.35):
        pyautogui.moveTo(int(start_x), int(start_y), duration=0.03)
        pyautogui.dragTo(int(end_x), int(end_y), duration=duration, button="left")
        time.sleep(self.click_delay)
        logger.debug(f"Arrasto de ({start_x}, {start_y}) para ({end_x}, {end_y})")

    def scroll(self, clicks):
        pyautogui.scroll(int(clicks))
        time.sleep(self.click_delay)
        logger.debug(f"Scroll executado: {clicks}")
