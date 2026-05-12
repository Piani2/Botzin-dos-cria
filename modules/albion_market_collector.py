"""
Módulo para coleta coordenada de dados do Albion Market
"""

import logging
import time
import unicodedata
from modules.screen_capture import ScreenCapture
from modules.albion_market_ocr import AlbionMarketOCR
from modules.market_data import MarketData, repair_mojibake
from modules.automation_controller import AutomationController

logger = logging.getLogger(__name__)

class AlbionMarketCollector:
    """Coordena coleta de dados do mercado"""
    
    def __init__(self, config):
        """
        Inicializa coletor
        
        Args:
            config: dicionário com configurações
        """
        self.config = config
        self.screen = ScreenCapture(region=config.get('screenshot_region'))
        self.ocr = AlbionMarketOCR(config.get('price_recognition', {}))
        self.market_data = MarketData()
        self.controller = AutomationController(config.get('automation', {}))
        self.wait_for_continue = None
        self.market_mode = config.get('market_mode', 'black_market_auto')
        self.black_market_ui = config.get('black_market_ui', {})
        self.screenshot_region = config.get('screenshot_region')
        
        # Configuração
        automation_config = config.get('automation', {})
        self.screenshot_delay = automation_config.get('screenshot_delay', 1.0)
        self.click_delay = automation_config.get('click_delay', 0.5)
        self.dropdown_open_delay = automation_config.get('dropdown_open_delay', self.click_delay + 0.20)
        self.dropdown_select_delay = automation_config.get('dropdown_select_delay', self.click_delay + 0.12)
        self.filter_settle_delay = automation_config.get('filter_settle_delay', self.click_delay + 0.05)
        self.item_select_delay = automation_config.get('item_select_delay', self.click_delay)
        self.post_read_delay = automation_config.get('post_read_delay', self.screenshot_delay)
        self.tooltip_delay = automation_config.get('tooltip_delay', max(0.6, self.screenshot_delay))
        self.max_quantity_sold = int(config.get('ocr', {}).get('max_quantity_sold', 100000))
        self.price_change_factor_limit = float(config.get('ocr', {}).get('price_change_factor_limit', 4.0))
        self.price_recheck_delay = float(config.get('ocr', {}).get('price_recheck_delay', 0.12))
        self.current_item_page = None
        self.active_item_paging = None
        self.active_item_paging_profile = None
        
        # Coleta permanece em T5-T8; apenas o mapeamento de clique pode variar por item.
        self.default_tiers = config.get('tiers', ['T5', 'T6', 'T7', 'T8'])
        self.item_tier_groups = config.get('item_tier_groups', {})
        self.enchantments = ['.0', '.1', '.2', '.3']

    def _save_failure_screenshot(self, screenshot, label):
        """Salva screenshot que falhou na extração para diagnóstico."""
        try:
            import os
            from datetime import datetime

            failures_dir = os.path.join('screenshots', 'failures')
            os.makedirs(failures_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"fail_{label}_{ts}.png"
            path = os.path.join(failures_dir, filename)
            # screenshot é um PIL Image
            screenshot.save(path)
            logger.info(f"Screenshot de falha salvo em {path}")
        except Exception as e:
            logger.error(f"Erro ao salvar screenshot de falha: {e}")

    def set_wait_for_continue(self, wait_fn):
        """Define função de espera externa (ex.: Enter global)."""
        self.wait_for_continue = wait_fn
    
    def collect_item_data(self, item_name, item_index=None):
        """
        Coleta dados de um item específico em todos os tiers e encantamentos
        
        Args:
            item_name: nome do item
            
        Returns:
            bool indicando sucesso
        """
        try:
            logger.debug(f"Coletando dados do item: {item_name}")
            item_tiers = self.default_tiers
            mapping_profile = self._get_tier_mapping_profile_for_item(item_name)
            logger.debug(f"Perfil de mapeamento para {item_name}: {mapping_profile}")

            if self.market_mode == 'black_market_auto':
                success = self._collect_item_black_market_auto(
                    item_name,
                    item_index,
                    item_tiers,
                    mapping_profile,
                )
                self._close_item_after_collection(item_name)
                return success
            
            for tier in item_tiers:
                for enchantment in self.enchantments:
                    # 1. Navegar para o item específico
                    self._navigate_to_item(item_name, tier, enchantment, item_index)
                    
                    # 2. Aguardar tooltip aparecer (após hover)
                    time.sleep(1.0)
                    
                    # 3. Capturar screenshot
                    screenshot = self.screen.capture()
                    if not screenshot:
                        logger.warning(f"Falha ao capturar screenshot para {item_name} {tier}{enchantment}")
                        continue
                    
                    # 4. Extrair informações
                    price, quantity_sold = self._extract_tooltip_values(screenshot)

                    if price is None or quantity_sold is None:
                        logger.debug("Tooltip OCR incompleto, usando recortes separados como fallback")
                        if price is None:
                            price = self._extract_price_consensus(screenshot)
                        if quantity_sold is None:
                            quantity_sold = self._extract_quantity_sold(screenshot)
                    
                    if price is not None and quantity_sold is not None:
                        quantity_sold = self._validate_quantity_sold(quantity_sold)
                        price = self._validate_price_reading(item_name, tier, enchantment, price)

                    if price is not None and quantity_sold is not None:
                        # 5. Armazenar dados
                        self.market_data.add_item(
                            item_name, 
                            tier, 
                            enchantment, 
                            price, 
                            quantity_sold
                        )
                        logger.info(f"{item_name} {tier.replace('T', '')}{enchantment}\nPreco: {price} Vendidos: {quantity_sold}")
                    else:
                        logger.warning(f"[ERRO] Não foi possível extrair dados de {item_name} {tier}{enchantment}")
                        try:
                            self._save_failure_screenshot(screenshot, f"{item_name}_{tier}{enchantment}")
                        except Exception:
                            pass
                    
                    # Delay entre capturas
                    time.sleep(self.post_read_delay)
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao coletar dados de {item_name}: {e}")
            return False

    def _collect_item_black_market_auto(self, item_name, item_index, item_tiers, mapping_profile):
        """Fluxo determinístico: item fixo -> tiers em ordem -> enchants em ordem."""
        try:
            self._select_black_market_item(item_index)
            time.sleep(self.item_select_delay)

            for tier_idx, tier in enumerate(item_tiers):
                # Regra importante de UI: tiers podem mudar de posição quando enchant != .0.
                # Portanto, sempre voltamos para .0 antes de selecionar o próximo tier.
                logger.debug(f"Resetando enchant para .0 antes de selecionar {tier}")
                self._select_tier_and_enchantment(
                    tier=None,
                    enchantment='.0',
                    tier_profile=mapping_profile,
                )
                time.sleep(self.filter_settle_delay)

                logger.debug(f"Selecionando {tier}")
                self._select_tier_and_enchantment(tier=tier, enchantment=None, tier_profile=mapping_profile)
                time.sleep(self.filter_settle_delay)

                for ench_idx, enchantment in enumerate(self.enchantments):
                    logger.debug(f"{tier} -> enchantment {ench_idx}: {enchantment}")

                    # .0 já foi aplicado antes da seleção do tier nesta iteração.
                    if enchantment != '.0':
                        self._select_tier_and_enchantment(
                            tier=None,
                            enchantment=enchantment,
                            tier_profile=mapping_profile,
                        )

                    # Hover para tooltip de quantidade
                    qty_hover = self.black_market_ui.get('quantity_hover')
                    if qty_hover:
                        self.controller.move_mouse(qty_hover[0], qty_hover[1], duration=0.06)
                    time.sleep(self.tooltip_delay)

                    screenshot = self.screen.capture()
                    if not screenshot:
                        logger.warning(f"Falha ao capturar screenshot para {item_name} {tier}{enchantment}")
                        continue

                    price, quantity_sold = self._extract_tooltip_values(screenshot)

                    if price is None or quantity_sold is None:
                        if price is None:
                            price = self._extract_price_consensus(screenshot)
                        if quantity_sold is None:
                            quantity_sold = self._extract_quantity_sold(screenshot)

                    if price is not None and quantity_sold is not None:
                        quantity_sold = self._validate_quantity_sold(quantity_sold)
                        price = self._validate_price_reading(item_name, tier, enchantment, price)

                    if price is not None and quantity_sold is not None:
                        self.market_data.add_item(item_name, tier, enchantment, price, quantity_sold)
                        logger.info(f"{item_name} {tier.replace('T', '')}{enchantment}\nPreco: {price} Vendidos: {quantity_sold}")
                    else:
                        logger.warning(f"[ERRO] Não foi possível extrair dados de {item_name} {tier}{enchantment}")
                        try:
                            self._save_failure_screenshot(screenshot, f"{item_name}_{tier}{enchantment}")
                        except Exception:
                            pass

                    time.sleep(self.post_read_delay)
                
                # Delay entre iterações de tier para resetar estado da UI
                time.sleep(self.filter_settle_delay)

            logger.debug("Iteracao de tiers concluida com sucesso.")
            return True

        except Exception as e:
            logger.error(f"Erro no fluxo black_market_auto de {item_name}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _validate_quantity_sold(self, quantity):
        """Descarta leituras de quantidade que claramente misturaram preco/grafico."""
        if quantity is None:
            return None

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return None

        if quantity < 0 or quantity > self.max_quantity_sold:
            logger.warning(
                f"Quantidade vendida fora do limite plausivel ({quantity}); ignorando leitura."
            )
            return None

        return quantity

    def _validate_price_reading(self, item_name, tier, enchantment, price):
        """Evita sobrescrever preço antigo com OCR claramente fora da curva."""
        if price is None:
            return None

        try:
            price = int(price)
        except (TypeError, ValueError):
            return None

        previous_price = self._get_previous_price(item_name, tier, enchantment)
        if not previous_price:
            return price

        if not self._is_price_outlier(price, previous_price):
            return price

        logger.warning(
            f"Preço suspeito para {item_name} {tier}{enchantment}: "
            f"lido={price}, anterior={previous_price}. Tentando confirmar..."
        )

        rechecked_price = self._recheck_price_once()
        if rechecked_price is not None and not self._is_price_outlier(rechecked_price, previous_price):
            logger.info(
                f"Preço corrigido na releitura de {item_name} {tier}{enchantment}: "
                f"{price} -> {rechecked_price}"
            )
            return rechecked_price

        logger.warning(
            f"Preço descartado para {item_name} {tier}{enchantment}; mantendo valor anterior no relatório."
        )
        return None

    def _get_previous_price(self, item_name, tier, enchantment):
        item_key = repair_mojibake(item_name)
        try:
            return int(self.market_data.get_all_items()[item_key][tier][enchantment]['price'])
        except (KeyError, TypeError, ValueError):
            return None

    def _is_price_outlier(self, price, reference_price):
        if not price or not reference_price:
            return False
        return (
            price >= reference_price * self.price_change_factor_limit
            or price <= reference_price / self.price_change_factor_limit
        )

    def _recheck_price_once(self):
        try:
            time.sleep(self.price_recheck_delay)
            screenshot = self.screen.capture()
            if not screenshot:
                return None
            return self._extract_price(screenshot)
        except Exception as e:
            logger.warning(f"Falha ao revalidar preço suspeito: {e}")
            return None

    def _close_item_after_collection(self, item_name):
        """Fecha a aba/detalhe do item após concluir a leitura de todos os tiers/enchants."""
        try:
            close_coord = self.black_market_ui.get('item_tab_close')
            if isinstance(close_coord, (list, tuple)) and len(close_coord) == 2:
                x, y = int(close_coord[0]), int(close_coord[1])
                logger.debug(f"Fechando aba do item {item_name} por coordenada: ({x}, {y})")
                self.controller.click(x, y)
                time.sleep(self.click_delay)
                return

            logger.warning(
                "item_tab_close não configurado em black_market_ui; aba do item não foi fechada."
            )
        except Exception as e:
            logger.warning(f"Não foi possível fechar aba do item {item_name}: {e}")

    def _normalize_item_name(self, item_name):
        """Normaliza nome para comparação robusta (sem acento e case-insensitive)."""
        if not item_name:
            return ''

        normalized = unicodedata.normalize('NFD', item_name)
        normalized = ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')
        return normalized.strip().lower()

    def _get_tier_mapping_profile_for_item(self, item_name):
        """Retorna o perfil de mapeamento de clique com base no grupo do item."""
        normalized_item = self._normalize_item_name(item_name)

        group_items = {
            group_name: {
                self._normalize_item_name(name)
                for name in items
                if isinstance(name, str)
            }
            for group_name, items in self.item_tier_groups.items()
            if isinstance(items, list)
        }

        for group_name, items in group_items.items():
            if normalized_item in items:
                return group_name

        return 'default'

    def _get_tier_dropdown_for_profile(self, tier_profile):
        """Busca dropdown por perfil; fallback para configuração legada de tier_dropdown."""
        tier_profiles = self.black_market_ui.get('tier_dropdown_profiles', {})
        if isinstance(tier_profiles, dict) and tier_profiles:
            if tier_profile in tier_profiles:
                return tier_profiles.get(tier_profile, {})
            if 'default' in tier_profiles:
                return tier_profiles.get('default', {})

        return self.black_market_ui.get('tier_dropdown', {})

    def _get_item_paging_for_collection(self, total_items, profile_name=None):
        """Busca paginacao calibrada pelo tipo da coleta ou pela quantidade total."""
        profiles = self.black_market_ui.get('item_paging_profiles') or {}
        if isinstance(profiles, dict):
            if profile_name:
                profile = profiles.get(str(profile_name).lower())
                if isinstance(profile, dict):
                    logger.debug(f"Usando perfil de scroll '{profile_name}'.")
                    return profile

            profile = profiles.get(str(total_items))
            if isinstance(profile, dict):
                logger.debug(f"Usando perfil de scroll para {total_items} itens.")
                return profile

        return self.black_market_ui.get('item_paging', {})
    
    def collect_multiple_items(self, item_names, paging_profile=None):
        """
        Coleta dados de múltiplos itens
        
        Args:
            item_names: lista com nomes dos itens
        """
        try:
            total_items = len(item_names)
            logger.info(f"Iniciando coleta de {total_items} itens.")
            self.current_item_page = None
            self.active_item_paging_profile = paging_profile
            self.active_item_paging = self._get_item_paging_for_collection(total_items, paging_profile)
            
            for index, item_name in enumerate(item_names, 1):
                logger.info(f"\n[{index}/{total_items}] {item_name}")
                self.collect_item_data(item_name, item_index=index - 1)
            
            logger.info("Coleta completa.")
            return True
            
        except Exception as e:
            logger.error(f"Erro durante coleta múltipla: {e}")
            return False
    
    def _navigate_to_item(self, item_name, tier, enchantment, item_index=None):
        """
        Navega até um item específico no mercado
        
        Nota: Esta função deve ser customizada baseada na interface real do Albion
        
        Args:
            item_name: nome do item
            tier: tier do item
            enchantment: encantamento
        """
        try:
            if self.market_mode == 'black_market_auto':
                self._select_black_market_item(item_index)
                self._select_tier_and_enchantment(tier, enchantment)
                time.sleep(self.click_delay)
                return

            if self.market_mode == 'black_market_manual':
                message = (
                    f"\nNo jogo, selecione {item_name} {tier}{enchantment} no Mercado Negro "
                    "e pressione ENTER para capturar."
                )
                if self.wait_for_continue:
                    self.wait_for_continue(message)
                else:
                    print(message)
                    input()
                return

            # 1. Abrir mercado se não estiver aberto
            self.controller.press_key('m')
            time.sleep(self.click_delay)
            
            # 2. Procurar por item na barra de busca
            # Pressionar Ctrl+F para busca
            self.controller.hotkey('ctrl', 'f')
            time.sleep(self.click_delay)
            
            # 3. Digitar nome do item com tier e encantamento
            search_term = f"{item_name} {tier}{enchantment}"
            self.controller.type_text(search_term, interval=0.02)
            time.sleep(self.click_delay)
            
            # 4. Pressionar Enter para buscar
            self.controller.press_key('enter')
            time.sleep(self.screenshot_delay)
            
        except Exception as e:
            logger.error(f"Erro ao navegar para item: {e}")

    def _select_black_market_item(self, item_index):
        """Seleciona item da lista do Mercado Negro por índice usando coordenadas."""
        if item_index is None:
            return

        paging = self.active_item_paging or self.black_market_ui.get('item_paging', {})
        if paging.get('enabled'):
            self._select_black_market_item_paged(item_index, paging)
            return

        first_x, first_y = self.black_market_ui.get('item_list_first', [360, 320])
        focus_coord = self.black_market_ui.get('item_list_focus')
        row_step = self.black_market_ui.get('item_list_row_step', 34)
        visible_rows = max(1, self.black_market_ui.get('item_list_visible_rows', 12))
        scroll_per_row = self.black_market_ui.get('item_list_scroll_per_row', -120)

        target_page = item_index // visible_rows
        target_row = item_index % visible_rows

        # Só foca por clique se houver ponto neutro explicitamente calibrado.
        if isinstance(focus_coord, (list, tuple)) and len(focus_coord) == 2:
            self.controller.click(int(focus_coord[0]), int(focus_coord[1]))
            time.sleep(0.08)

        self.controller.press_key('home')
        time.sleep(self.click_delay)

        rows_to_scroll = target_page * visible_rows
        if rows_to_scroll > 0:
            self.controller.scroll(scroll_per_row * rows_to_scroll)
            time.sleep(self.click_delay)

        click_x = first_x
        click_y = first_y + (target_row * row_step)
        self.controller.click(click_x, click_y)
        logger.debug(f"Item automático selecionado na lista: idx={item_index}, ({click_x}, {click_y})")

    def _select_black_market_item_paged(self, item_index, paging):
        """Seleciona item em paginas fixas da lista; cada pagina mostra poucos itens."""
        page_size = max(1, int(paging.get('page_size', 5)))
        target_page = item_index // page_size
        target_row = item_index % page_size

        if self.current_item_page is None or target_page < self.current_item_page:
            reset_key = paging.get('reset_key', 'home')
            if reset_key:
                self.controller.press_key(reset_key)
            self.current_item_page = 0
            time.sleep(self.item_select_delay)

        while self.current_item_page < target_page:
            self._scroll_black_market_item_page(paging, self.current_item_page)
            self.current_item_page += 1
            time.sleep(self.item_select_delay)

        page_row_positions = paging.get('page_row_positions') or {}
        row_positions = page_row_positions.get(str(target_page)) or paging.get('row_positions') or []
        if target_row < len(row_positions):
            click_x, click_y = row_positions[target_row]
        else:
            first_x, first_y = self.black_market_ui.get('item_list_first', [360, 320])
            row_step = self.black_market_ui.get('item_list_row_step', 34)
            click_x = first_x
            click_y = first_y + (target_row * row_step)

        self.controller.click(int(click_x), int(click_y))
        time.sleep(self.item_select_delay)
        logger.debug(
            f"Item selecionado: idx={item_index}, page={target_page}, row={target_row}, ({click_x}, {click_y})"
        )

    def _scroll_black_market_item_page(self, paging, page_index):
        """Desce uma pagina da lista de itens por roda ou por arrasto calibrado."""
        method = paging.get('method', 'wheel')
        if method == 'drag':
            drag_steps = paging.get('drag_steps') or []
            if page_index < len(drag_steps):
                step = drag_steps[page_index]
                start = step.get('start')
                end = step.get('end')
            else:
                start = paging.get('drag_start')
                end = paging.get('drag_end')

            if start and end and len(start) == 2 and len(end) == 2:
                self.controller.drag_from_to(
                    int(start[0]),
                    int(start[1]),
                    int(end[0]),
                    int(end[1]),
                    duration=float(paging.get('drag_duration', 0.35)),
                )
                return

        self.controller.scroll(int(paging.get('scroll_per_page', -600)))

    def _select_tier_and_enchantment(self, tier=None, enchantment=None, tier_profile='default'):
        """Seleciona tier e encantamento por coordenadas, se configurado."""
        # Prefer dropdown-based selection if available
        tier_dropdown = self._get_tier_dropdown_for_profile(tier_profile)
        enchant_dropdown = self.black_market_ui.get('enchant_dropdown')

        if tier is not None and tier_dropdown:
            open_coord = tier_dropdown.get('open')
            option = tier_dropdown.get('options', {}).get(tier)
            self._click_dropdown_option(open_coord, option, f"tier {tier}")
        elif tier is not None:
            # Fallback para coordenadas diretas
            tier_coords = self.black_market_ui.get('tier_coords', {})
            if tier in tier_coords:
                x, y = tier_coords[tier]
                self.controller.click(x, y)
                time.sleep(self.click_delay)

        if enchantment is not None and enchant_dropdown:
            open_coord = enchant_dropdown.get('open')
            option = enchant_dropdown.get('options', {}).get(enchantment)
            self._click_dropdown_option(open_coord, option, f"enchant {enchantment}")
        elif enchantment is not None:
            enchant_coords = self.black_market_ui.get('enchant_coords', {})
            if enchantment in enchant_coords:
                x, y = enchant_coords[enchantment]
                self.controller.click(x, y)
                time.sleep(self.click_delay)

        # Mantém pequena pausa após seleção de filtro para estabilizar UI.
        time.sleep(self.filter_settle_delay)

    def _click_dropdown_option(self, open_coord, option_coord, label):
        """Clica em dropdown com sequência única e estável."""
        if not open_coord or not option_coord:
            logger.debug(f"Dropdown sem coordenadas para {label}")
            return

        logger.debug(f"Abrindo {label}: open={open_coord}")
        self.controller.click(open_coord[0], open_coord[1])
        time.sleep(self.dropdown_open_delay)
        
        logger.debug(f"Clicando opcao {label}: option={option_coord}")
        self.controller.move_mouse(option_coord[0], option_coord[1], duration=0.03)
        self.controller.click(option_coord[0], option_coord[1])
        time.sleep(self.dropdown_select_delay)
        logger.debug(f"Seleção {label}: open={open_coord} option={option_coord}")

    def _extract_price_consensus(self, base_screenshot):
        """Extrai preço direto sem consenso para otimizar velocidade."""
        price = self._extract_price(base_screenshot)
        if price is not None:
            logger.debug(f"Preço extraído: {price}")
            return price
        return None
    
    def _extract_price(self, screenshot):
        """
        Extrai preço do screenshot
        
        Nota: Coordenadas devem ser ajustadas baseado na interface real
        
        Args:
            screenshot: PIL Image
            
        Returns:
            int com preço ou None
        """
        try:
            price_region_coords = self._get_ocr_region('price_region', 'price')
            logger.debug(f"Região de preço usada: {price_region_coords}")
            
            region = screenshot.crop(price_region_coords)
            price = self.ocr.extract_price_from_region(region)

            if price is None:
                x1, y1, x2, y2 = price_region_coords
                expanded_region = (
                    max(0, x1 - 60),
                    max(0, y1 - 30),
                    x2 + 80,
                    y2 + 40,
                )
                logger.debug(f"Fallback de preço com região ampliada: {expanded_region}")
                expanded_crop = screenshot.crop(expanded_region)
                price = self.ocr.extract_price_from_region(expanded_crop, trim_left=True)
            
            return price
            
        except Exception as e:
            logger.error(f"Erro ao extrair preço: {e}")
            return None
    
    def _extract_quantity_sold(self, screenshot):
        """
        Extrai quantidade vendida do screenshot
        
        Nota: Coordenadas devem ser ajustadas baseado na interface real
        
        Args:
            screenshot: PIL Image
            
        Returns:
            int com quantidade ou None
        """
        try:
            qty_region_coords = self._get_ocr_region('quantity_region', 'quantity')
            logger.debug(f"Região de quantidade usada: {qty_region_coords}")
            
            region = screenshot.crop(qty_region_coords)
            quantity = self.ocr.extract_quantity_from_region(region)
            
            return quantity
            
        except Exception as e:
            logger.error(f"Erro ao extrair quantidade vendida: {e}")
            return None

    def _extract_tooltip_values(self, screenshot):
        """Tenta ler preço e quantidade de um único tooltip recortado em volta do hover."""
        try:
            qty_hover = self.black_market_ui.get('quantity_hover')
            if not qty_hover:
                return None, None

            x, y = self._to_capture_point(qty_hover[0], qty_hover[1])
            configured_region = self.black_market_ui.get('quantity_tooltip_region')
            if configured_region and len(configured_region) == 4:
                tooltip_region = self._to_capture_region(configured_region)
            else:
                # O tooltip de "Vendido" aparece ancorado perto do mouse; manter
                # esse recorte curto evita misturar tabela de pedidos, grafico e preco medio.
                tooltip_region = (
                    max(0, x - 150),
                    max(0, y - 58),
                    x + 45,
                    y + 14,
                )

            region = screenshot.crop(tooltip_region)
            _, quantity = self.ocr.extract_price_and_quantity_from_region(region)

            if quantity is None:
                logger.debug(f"Tooltip OCR vazio na região {tooltip_region}")

            # Preço no tooltip tende a capturar "preço médio" do gráfico.
            # Mantemos o tooltip apenas para quantidade e extraímos preço por `price_region`.
            return None, quantity

        except Exception as e:
            logger.error(f"Erro ao extrair tooltip completo: {e}")
            return None, None

    def _get_ocr_region(self, config_key, label):
        """Retorna a região calibrada com uma pequena margem de segurança."""
        region = self.config.get(config_key)

        if not region:
            qty_hover = self.black_market_ui.get('quantity_hover', [1163, 548])
            logger.warning(
                f"Região '{config_key}' não configurada. Usando fallback perto do hover de quantidade; a extração pode ficar imprecisa."
            )
            if label == 'price':
                region = (
                    max(0, qty_hover[0] - 150),
                    max(0, qty_hover[1] - 100),
                    qty_hover[0] + 250,
                    qty_hover[1] + 80,
                )
            else:
                region = (
                    max(0, qty_hover[0] - 150),
                    qty_hover[1] + 60,
                    qty_hover[0] + 250,
                    qty_hover[1] + 180,
                )

        x1, y1, x2, y2 = region
        default_padding = 2 if label == 'price' else 0
        padding = int(self.config.get('ocr', {}).get(f'{label}_region_padding', default_padding))
        padded_region = (
            max(0, x1 - padding),
            max(0, y1 - padding),
            x2 + padding,
            y2 + padding,
        )
        return self._to_capture_region(padded_region)

    def _to_capture_point(self, x, y):
        """Converte ponto absoluto da tela para coordenada relativa ao screenshot capturado."""
        if not self.screenshot_region:
            return x, y

        sx1, sy1, _, _ = self.screenshot_region
        return x - sx1, y - sy1

    def _to_capture_region(self, region):
        """Converte região absoluta da tela para região relativa ao screenshot capturado."""
        x1, y1, x2, y2 = region

        rx1, ry1 = self._to_capture_point(x1, y1)
        rx2, ry2 = self._to_capture_point(x2, y2)

        return (
            max(0, min(rx1, rx2)),
            max(0, min(ry1, ry2)),
            max(rx1, rx2),
            max(ry1, ry2),
        )
    
    def get_collected_data(self):
        """Retorna dados coletados"""
        return self.market_data
