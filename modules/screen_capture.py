"""Captura de tela usada pelo coletor e calibradores."""

import logging

import pyautogui

logger = logging.getLogger(__name__)


class ScreenCapture:
    def __init__(self, region=None):
        self.region = region
        pyautogui.FAILSAFE = True

    def capture(self, save_path=None):
        try:
            if self.region:
                x1, y1, x2, y2 = self.region
                screenshot = pyautogui.screenshot(region=(x1, y1, x2 - x1, y2 - y1))
            else:
                screenshot = pyautogui.screenshot()

            if save_path:
                screenshot.save(save_path)
                logger.info(f"Screenshot salvo em {save_path}")

            return screenshot
        except Exception as e:
            logger.error(f"Erro ao capturar screenshot: {e}")
            return None
