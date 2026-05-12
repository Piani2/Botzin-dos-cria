"""Controle minimo de mouse e teclado usado pelo coletor."""

import logging
import time

import pyautogui

logger = logging.getLogger(__name__)


class AutomationController:
    def __init__(self, config):
        self.click_delay = config.get("click_delay", 0.5)
        pyautogui.FAILSAFE = True

    def click(self, x, y, button="left"):
        try:
            pyautogui.click(x, y, button=button)
            time.sleep(self.click_delay)
            logger.debug(f"Clique em ({x}, {y})")
        except Exception as e:
            logger.error(f"Erro ao clicar: {e}")

    def type_text(self, text, interval=0.05):
        try:
            pyautogui.typewrite(text, interval=interval)
            logger.debug(f"Texto digitado: {text}")
        except Exception as e:
            logger.error(f"Erro ao digitar texto: {e}")

    def press_key(self, key):
        try:
            pyautogui.press(key)
            time.sleep(self.click_delay)
            logger.debug(f"Tecla pressionada: {key}")
        except Exception as e:
            logger.error(f"Erro ao pressionar tecla: {e}")

    def hotkey(self, *keys):
        try:
            pyautogui.hotkey(*keys)
            time.sleep(self.click_delay)
            logger.debug(f"Hotkey: {'+'.join(keys)}")
        except Exception as e:
            logger.error(f"Erro ao usar hotkey: {e}")

    def move_mouse(self, x, y, duration=0.5):
        try:
            pyautogui.moveTo(x, y, duration=duration)
            logger.debug(f"Mouse movido para ({x}, {y})")
        except Exception as e:
            logger.error(f"Erro ao mover mouse: {e}")

    def drag_from_to(self, start_x, start_y, end_x, end_y, duration=0.35):
        try:
            pyautogui.moveTo(start_x, start_y, duration=0.03)
            pyautogui.dragTo(end_x, end_y, duration=duration, button="left")
            time.sleep(self.click_delay)
        except Exception as e:
            logger.error(f"Erro ao arrastar: {e}")

    def scroll(self, clicks):
        try:
            pyautogui.scroll(clicks)
            time.sleep(self.click_delay)
            logger.debug(f"Scroll executado: {clicks}")
        except Exception as e:
            logger.error(f"Erro ao rolar mouse: {e}")
