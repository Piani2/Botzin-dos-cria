"""
Módulo especializado para captura de dados do Mercado do Albion
"""

import pytesseract
from pytesseract import Output
from PIL import Image, ImageEnhance, ImageFilter
import re
import logging
import numpy as np

# Configurar caminho do Tesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

logger = logging.getLogger(__name__)

class AlbionMarketOCR:
    """OCR especializado para interface de mercado do Albion"""
    
    def __init__(self, config=None):
        """Inicializa OCR"""
        if not isinstance(config, dict):
            config = {}

        self.language = 'por+eng'  # Português + Inglês
        self.confidence = 0.5
        self.price_recognition = config
        self.price_direct_psms = tuple(config.get('price_direct_psms', [7]))
        self.tooltip_fast_psms = tuple(config.get('tooltip_fast_psms', [6]))

    
    def preprocess_image(self, img, enhance_contrast=True, enhance_sharpness=True):
        """
        Pré-processa imagem para melhor OCR
        
        Args:
            img: PIL Image
            enhance_contrast: aplicar aumento de contraste
            enhance_sharpness: aplicar aumento de nitidez
            
        Returns:
            imagem processada
        """
        try:
            # Converter para escala de cinza
            img = img.convert('L')
            
            if enhance_contrast:
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(2.5)
            
            if enhance_sharpness:
                enhancer = ImageEnhance.Sharpness(img)
                img = enhancer.enhance(2)
            
            # Aplicar threshold para melhorar legibilidade
            img = Image.eval(img, lambda x: 255 if x > 150 else 0)
            
            return img
            
        except Exception as e:
            logger.error(f"Erro ao pré-processar imagem: {e}")
            return img

    def _trim_left_margin(self, image_region):
        """Remove margem esquerda com ícone/moeda para evitar ruído no OCR."""
        try:
            if isinstance(image_region, Image.Image):
                img_array = np.array(image_region.convert('L'))
            else:
                img_array = np.asarray(image_region, dtype=np.uint8)
                if img_array.ndim == 3:
                    # converter para grayscale
                    img_array = np.dot(img_array[...,:3], [0.2989, 0.5870, 0.1140]).astype(np.uint8)

            if img_array.size == 0:
                return image_region

            col_activity = np.sum(img_array < 180, axis=0)
            if col_activity.size == 0 or np.max(col_activity) == 0:
                return image_region

            threshold = np.max(col_activity) * 0.25
            active_cols = np.where(col_activity > threshold)[0]
            if len(active_cols) == 0:
                return image_region

            first_active_col = int(active_cols[0])
            trim_col = max(0, first_active_col - 1)

            groups = []
            group_start = int(active_cols[0])
            previous_col = int(active_cols[0])
            for col in active_cols[1:]:
                col = int(col)
                if col > previous_col + 1:
                    groups.append((group_start, previous_col))
                    group_start = col
                previous_col = col
            groups.append((group_start, previous_col))

            image_width = img_array.shape[1]
            icon_gap = max(4, int(image_width * 0.045))
            left_limit = int(image_width * 0.35)
            best_gap = 0
            best_trim_col = trim_col
            for idx in range(len(groups) - 1):
                current_end = groups[idx][1]
                next_start = groups[idx + 1][0]
                gap = next_start - current_end
                if current_end <= left_limit and gap >= icon_gap and gap > best_gap:
                    best_gap = gap
                    best_trim_col = max(0, next_start - 1)

            trim_col = best_trim_col

            if isinstance(image_region, Image.Image):
                width, height = image_region.size
                if trim_col >= width:
                    return image_region
                return image_region.crop((trim_col, 0, width, height))
            else:
                if trim_col >= img_array.shape[1]:
                    return image_region
                return img_array[:, trim_col:]

        except Exception as e:
            logger.debug(f"_trim_left_margin falhou: {e}")
            return image_region

    def _prepare_ocr_variants(self, image_region, trim_left=True):
        """Gera variações de OCR com binarização adaptativa para melhor precisão."""
        variants = []

        try:
            # Remover margem esquerda com ícone antes de criar variantes
            source = self._trim_left_margin(image_region) if trim_left else image_region
            if not isinstance(source, Image.Image):
                source = Image.fromarray(np.asarray(source))
            # Variante 1: Básica com Tesseract padrão
            base = source.convert('L')
            variants.append(('base', base))

            # Variante 2: Upscale 2x para melhor OCR
            resized = base.resize((base.width * 2, base.height * 2), Image.Resampling.LANCZOS)
            variants.append(('upscale_2x', resized))

            # Variante 3: Upscale 3x para texto muito pequeno
            resized_3x = base.resize((base.width * 3, base.height * 3), Image.Resampling.LANCZOS)
            variants.append(('upscale_3x', resized_3x))

            # Variante 4: Contraste máximo + threshold fixo
            processed = self.preprocess_image(source, enhance_contrast=True, enhance_sharpness=True)
            processed = Image.eval(processed, lambda x: 255 if x > 160 else 0)
            variants.append(('high_contrast', processed))

            inverted = Image.eval(processed, lambda x: 255 - x)
            variants.append(('high_contrast_inverted', inverted))

            # Variante 5: Contraste máximo + upscale
            processed_upscaled = processed.resize((processed.width * 2, processed.height * 2), Image.Resampling.LANCZOS)
            variants.append(('high_contrast_2x', processed_upscaled))

            inverted_upscaled = inverted.resize((inverted.width * 2, inverted.height * 2), Image.Resampling.LANCZOS)
            variants.append(('high_contrast_inverted_2x', inverted_upscaled))

        except Exception as e:
            logger.warning(f"Erro ao gerar variantes OCR: {e}")

        return variants

    def _collect_numeric_candidates(self, image_region, trim_left=True):
        """Extrai candidatos numéricos com confiança OCR."""
        candidates = []

        for variant_name, variant in self._prepare_ocr_variants(image_region, trim_left=trim_left):
            for psm in (6, 7, 8, 11):
                try:
                    data = pytesseract.image_to_data(
                        variant,
                        lang='eng',
                        config=f'--psm {psm} --oem 3',
                        output_type=Output.DICT,
                    )
                except Exception as e:
                    logger.debug(f"OCR data falhou em psm={psm}: {e}")
                    continue

                for idx, raw_text in enumerate(data.get('text', [])):
                    text = (raw_text or '').strip()
                    if not text:
                        continue

                    digits = re.sub(r'\D', '', text)
                    if not digits:
                        continue

                    # Filtrar tokens muito ruidosos: aceitar apenas tamanhos típicos de preço (3-9 dígitos)
                    if len(digits) < 3 or len(digits) > 9:
                        # Ignorar tokens com muitos separadores (muitos números encaixados)
                        if text.count(',') + text.count('.') > 2:
                            continue
                        # permitir casos longos raros, mas preferir ignorar
                        if len(digits) > 9:
                            continue

                    try:
                        confidence = float(data.get('conf', ['-1'])[idx])
                    except Exception:
                        confidence = -1.0

                    candidates.append(
                        {
                            'value': int(digits),
                            'digits': digits,
                            'confidence': confidence,
                            'psm': psm,
                            'variant': variant_name,
                            'raw': text,
                        }
                    )

        return candidates

    def _choose_candidate(self, candidates, prefer='largest'):
        """Seleciona o candidato numérico mais plausível."""
        if not candidates:
            return None

        # Remove duplicados mantendo a melhor confiança por valor
        dedup = {}
        for candidate in candidates:
            key = candidate['digits']
            current = dedup.get(key)
            if current is None or candidate['confidence'] > current['confidence']:
                dedup[key] = candidate

        items = list(dedup.values())

        def sort_key(candidate):
            length = len(candidate['digits'])
            confidence = candidate['confidence'] if candidate['confidence'] >= 0 else -1.0
            value = candidate['value']

            if prefer == 'smallest':
                return (length, -confidence, value)

            return (-length, -confidence, -value)

        items.sort(key=sort_key)
        return items[0]

    def _normalize_price_value(self, value, reference_values):
        """Corrige ruído SEVERO de OCR no preço (ex.: 827000 -> 27000 quando OCR injeta 8)."""
        s = str(value)

        # APENAS para ruído muito óbvio: 6-8 dígitos começando com 6, 8, 9 que reduzem para 4-5 dígitos válidos.
        # Isso evita remover primeiro dígito válido de preços normais.
        if len(s) >= 7 and s[0] in ('6', '8', '9'):
            trimmed = int(s[1:])
            # Só aceita se resultar em 4-5 dígitos (faixa típica de preço) E o valor original for 3x maior (claro ruído).
            if 1000 <= trimmed <= 99999 and value >= trimmed * 2.5:
                return trimmed

        # Fallback: se múltiplos candidatos foram coletados e a versão sem 1º dígito aparece como referência.
        if len(s) >= 6 and len(reference_values) > 1 and s[0] in ('6', '8', '9'):
            trimmed = int(s[1:])
            if trimmed in reference_values and len(str(trimmed)) >= 4:
                return trimmed

        return value

    def _pick_best_voted_price(self, voted_scores):
        """Escolhe melhor preço votado, evitando preferir versões truncadas do mesmo número."""
        if not voted_scores:
            return None

        best_value = max(voted_scores, key=voted_scores.get)
        best_score = voted_scores[best_value]
        best_str = str(best_value)

        for candidate_value, candidate_score in voted_scores.items():
            candidate_str = str(candidate_value)
            if len(candidate_str) <= len(best_str):
                continue

            # Se o melhor atual for prefixo de um candidato mais longo,
            # e o score do maior for competitivo, preferimos o número completo.
            if candidate_str.startswith(best_str) and candidate_score >= best_score * 0.70:
                best_value = candidate_value
                best_score = candidate_score
                best_str = candidate_str

        best_value = self._prefer_final_six_over_eight(voted_scores, best_value)
        return best_value

    def _pick_best_voted_digits(self, voted_digit_scores):
        """Escolhe melhor string de dígitos privilegiando leituras completas e estáveis."""
        if not voted_digit_scores:
            return None

        # Primeiro: detectar e corrigir duplicações óbvias (ex: 354998354998 -> 354998)
        cleaned_scores = {}
        for digits, score in voted_digit_scores.items():
            # Verificar se é uma duplicação exata (X + X)
            if len(digits) % 2 == 0:
                half = len(digits) // 2
                first_half = digits[:half]
                second_half = digits[half:]
                if first_half == second_half and len(first_half) >= 4:
                    # É duplicado, usar apenas a metade
                    cleaned_digits = first_half
                    cleaned_scores[cleaned_digits] = cleaned_scores.get(cleaned_digits, 0) + score
                    continue
            
            cleaned_scores[digits] = score
        
        if not cleaned_scores:
            return None

        best_digits = max(cleaned_scores, key=cleaned_scores.get)
        best_score = cleaned_scores[best_digits]

        for candidate_digits, candidate_score in cleaned_scores.items():
            if len(candidate_digits) <= len(best_digits):
                continue

            # Se o melhor atual parecer truncado (prefixo do maior), aceita maior com score competitivo.
            if candidate_digits.startswith(best_digits) and candidate_score >= best_score * 0.65:
                best_digits = candidate_digits
                best_score = candidate_score

        best_digits = self._prefer_final_six_over_eight(cleaned_scores, best_digits)
        return best_digits

    def _prefer_final_six_over_eight(self, scores, current_best):
        """Corrige empate comum onde o OCR lê o último 6 como 8."""
        if current_best is None:
            return current_best

        best_key = current_best
        best_digits = str(current_best)
        if not best_digits.endswith('8'):
            return current_best

        six_digits = best_digits[:-1] + '6'
        best_score = scores.get(best_key, scores.get(best_digits, 0))

        six_key = None
        if six_digits in scores:
            six_key = six_digits
        else:
            try:
                six_value = int(six_digits)
            except ValueError:
                six_value = None
            if six_value in scores:
                six_key = six_value

        if six_key is None:
            return current_best

        six_score = scores.get(six_key, 0)
        if six_score >= best_score * 0.40:
            return six_key

        return current_best

    def _extract_labeled_values(self, text):
        """Extrai preço e quantidade por rótulos textuais do tooltip."""
        if not text:
            return None, None

        raw_lines = [line.strip().lower() for line in text.splitlines() if line.strip()]
        normalized = " ".join(text.lower().split())

        price = None
        quantity = None

        # Ex.: "Preço médio: 13,870" / "Preco medio 13870"
        price_match = re.search(r'(?:preco|preço)\s*(?:medio|médio)?\s*[:=]?\s*([\d\.,\s]+)', normalized)
        if price_match:
            digits = re.sub(r'\D', '', price_match.group(1))
            if digits:
                price = int(digits)

        # Ex.: "Vendido: 550" / "Quantidade 550".
        # Extrair por linha evita juntar "Vendido: 3" com outro numero do tooltip.
        for line in raw_lines:
            if 'vend' not in line and 'verd' not in line and 'quantidade' not in line:
                continue

            after_label = re.split(r'vend\w*|verd\w*|quantidade', line, maxsplit=1)
            search_area = after_label[-1] if after_label else line
            quantity_match = re.search(r'\d[\d\.,]*', search_area)
            if quantity_match:
                digits = re.sub(r'\D', '', quantity_match.group(0))
                if digits:
                    quantity = int(digits)
                    break

        if quantity is None:
            quantity_match = re.search(r'(?:vend\w*|verd\w*|quantidade)\s*[:=]?\s*([\d\.,]+)', normalized)
            if quantity_match:
                digits = re.sub(r'\D', '', quantity_match.group(1))
                if digits:
                    quantity = int(digits)

        if quantity is None and ('vend' in normalized or 'verd' in normalized):
            numbers = []
            for line in raw_lines:
                if 'vend' in line or 'verd' in line:
                    numbers.extend(re.findall(r'\d[\d\.,]*', line))
            if numbers:
                digits = re.sub(r'\D', '', numbers[-1])
                if digits:
                    quantity = int(digits)

        return price, quantity

    def extract_price_and_quantity_from_region(self, image_region):
        """Extrai preço e quantidade a partir do mesmo recorte do tooltip."""
        try:
            # 1) Primeiro tenta leitura por rótulos do tooltip (mais confiável)
            labeled_price = None
            labeled_quantity = None

            if isinstance(image_region, Image.Image):
                source = image_region
            else:
                source = Image.fromarray(np.asarray(image_region))

            # Caminho rapido: no recorte calibrado do tooltip, o texto rotulado
            # costuma sair corretamente sem gerar todas as variantes pesadas.
            for psm in self.tooltip_fast_psms:
                try:
                    text = pytesseract.image_to_string(
                        source.convert('L'),
                        lang=self.language,
                        config=f'--psm {psm} --oem 3',
                    )
                except Exception:
                    continue

                p, q = self._extract_labeled_values(text)
                if p is not None and labeled_price is None:
                    labeled_price = p
                if q is not None:
                    logger.debug(f"Tooltip OCR rapido: preco={labeled_price} quantidade={q}")
                    return labeled_price, q

            for _, variant in self._prepare_ocr_variants(image_region, trim_left=False):
                for psm in (6, 7, 11):
                    try:
                        text = pytesseract.image_to_string(
                            variant,
                            lang=self.language,
                            config=f'--psm {psm} --oem 3'
                        )
                    except Exception:
                        continue

                    p, q = self._extract_labeled_values(text)
                    if p is not None and labeled_price is None:
                        labeled_price = p
                    if q is not None and labeled_quantity is None:
                        labeled_quantity = q

                    if labeled_price is not None and labeled_quantity is not None:
                        logger.debug(
                            f"Tooltip OCR por rótulo: preco={labeled_price} quantidade={labeled_quantity}"
                        )
                        return labeled_price, labeled_quantity

            if labeled_price is not None or labeled_quantity is not None:
                logger.debug(
                    f"Tooltip OCR por rótulo parcial: preco={labeled_price} quantidade={labeled_quantity}"
                )

            # 2) Fallback numérico se rótulos não forem detectados
            candidates = self._collect_numeric_candidates(image_region, trim_left=False)
            if not candidates:
                return labeled_price, labeled_quantity

            # Dedup por valor, preservando a melhor confiança.
            dedup = {}
            for candidate in candidates:
                key = candidate['digits']
                current = dedup.get(key)
                if current is None or candidate['confidence'] > current['confidence']:
                    dedup[key] = candidate

            items = list(dedup.values())
            if not items:
                return None, None

            # Ordenar por valor descending (preço geralmente é muito maior que quantidade)
            items.sort(key=lambda candidate: (-candidate['value'], -len(candidate['digits']), -candidate['confidence']))
            price_candidate = items[0]

            quantity_candidate = None
            if len(items) > 1:
                # Quantidade é o segundo maior valor (sempre menor que preço)
                quantity_candidate = items[1]

            price = price_candidate['value'] if price_candidate else None
            quantity = quantity_candidate['value'] if quantity_candidate else None

            if labeled_price is not None:
                price = labeled_price
            if labeled_quantity is not None:
                quantity = labeled_quantity

            # Segurança: se quantidade > preço, swap (indicativo de leitura errada)
            if price and quantity and quantity > price:
                logger.debug(f"Swap detectado: quantity {quantity} > price {price}, invertendo")
                price, quantity = quantity, price

            logger.debug(
                "Tooltip OCR candidatos: %s",
                [(candidate['value'], candidate['confidence'], candidate['psm'], candidate['raw']) for candidate in items]
            )
            return price, quantity

        except Exception as e:
            logger.error(f"Erro ao extrair preço/quantidade do tooltip: {e}")
            return None, None
    
    def extract_item_info(self, image_region):
        """
        Extrai informações de um item (nome, preço, quantidade)
        
        Args:
            image_region: PIL Image da região com dados do item
            
        Returns:
            dicionário com {name, price, quantity_sold}
        """
        try:
            # Pré-processar imagem
            processed = self.preprocess_image(image_region)
            
            # Usar Tesseract
            text = pytesseract.image_to_string(
                processed,
                lang=self.language,
                config='--psm 6'
            )
            
            # Parse dos dados
            return self.parse_item_text(text)
            
        except Exception as e:
            logger.error(f"Erro ao extrair info do item: {e}")
            return None
    
    def parse_item_text(self, text):
        """
        Parseia texto OCR do item
        Formato esperado: Nome do Item | Preço | Quantidade Vendida
        
        Args:
            text: texto extraído
            
        Returns:
            dicionário com dados parseados
        """
        try:
            text = text.strip()
            
            # Remover quebras de linha
            text = ' '.join(text.split())
            
            # Padrão: nome do item, seguido de números (preço e quantidade)
            # Exemplo: "Adaga Do 42000 4"
            
            # Tentar encontrar números no final
            numbers = re.findall(r'\d+', text)
            
            if len(numbers) >= 2:
                # Últimos dois números: preço e quantidade
                quantity = int(numbers[-1])
                price = int(numbers[-2])
                
                # Nome = tudo antes dos números
                name_match = re.match(r'(.+?)\s+\d+\s*\d*\s*$', text)
                if name_match:
                    name = name_match.group(1).strip()
                    
                    return {
                        'name': name,
                        'price': price,
                        'quantity_sold': quantity
                    }
            
            logger.warning(f"Não foi possível parsear: {text}")
            return None
            
        except Exception as e:
            logger.error(f"Erro ao parsear texto: {e}")
            return None
    
    def extract_multiple_items(self, image, regions):
        """
        Extrai dados de múltiplos itens
        
        Args:
            image: PIL Image completa da tela
            regions: lista de tuplas (x1, y1, x2, y2) com regiões de cada item
            
        Returns:
            lista de dicionários com dados dos itens
        """
        try:
            items = []
            
            for i, (x1, y1, x2, y2) in enumerate(regions):
                # Recortar região
                region = image.crop((x1, y1, x2, y2))
                
                # Extrair info
                info = self.extract_item_info(region)
                
                if info:
                    items.append(info)
                else:
                    logger.warning(f"Não foi possível extrair info da região {i+1}")
            
            return items
            
        except Exception as e:
            logger.error(f"Erro ao extrair múltiplos itens: {e}")
            return []
    
    def extract_price_from_region(self, image_region, trim_left=False):
        """
        Extrai apenas preço de uma região (versão otimizada com OCR melhorado)
        
        Args:
            image_region: PIL Image
            
        Returns:
            int com preço ou None
        """
        try:
            # Usa votação por posição na primeira linha (rápido)
            source = self._trim_left_margin(image_region) if trim_left else image_region
            if not isinstance(source, Image.Image):
                source = Image.fromarray(np.asarray(source))

            # Caminho mais estavel para regioes ja calibradas: uma unica linha de preco.
            # Evita que variantes agressivas ganhem a votacao com digitos truncados.
            pending_direct_value = None
            for psm in self.price_direct_psms:
                try:
                    text = pytesseract.image_to_string(
                        source.convert('L'),
                        lang='eng',
                        config=f'--psm {psm} --oem 3 -c tessedit_char_whitelist=0123456789,.',
                    )
                except Exception:
                    continue

                digits = re.sub(r'\D', '', text or '')
                if 4 <= len(digits) <= 8:
                    direct_value = int(digits)
                    if 100 <= direct_value <= 99_999_999:
                        if self._needs_trailing_zero_confirmation(direct_value):
                            pending_direct_value = direct_value
                            logger.debug(f"Preco OCR direto suspeito de zero extra: {direct_value} raw={text!r}")
                            break
                        if self._needs_final_six_eight_confirmation(direct_value):
                            pending_direct_value = direct_value
                            logger.debug(f"Preco OCR direto suspeito de 6 como 8 no final: {direct_value} raw={text!r}")
                            break
                        logger.debug(f"Preco OCR direto: {direct_value} raw={text!r}")
                        return direct_value

            voted_scores = {}
            voted_digit_scores = {}

            for variant_name, variant in self._prepare_ocr_variants(image_region, trim_left=trim_left):
                local_tokens = []

                for psm in (6, 7, 8):  # Múltiplos PSMs para robustez
                    try:
                        data = pytesseract.image_to_data(
                            variant,
                            lang='eng',
                            config=f'--psm {psm} --oem 3 -c tessedit_char_whitelist=0123456789,.',
                            output_type=Output.DICT,
                        )
                    except Exception:
                        continue

                    for idx, raw_text in enumerate(data.get('text', [])):
                        text = (raw_text or '').strip()
                        if not text:
                            continue

                        digits = re.sub(r'\D', '', text)
                        if len(digits) < 4:
                            continue

                        try:
                            confidence = float(data.get('conf', ['-1'])[idx])
                        except Exception:
                            confidence = -1.0

                        left = int(data.get('left', [0])[idx])
                        top = int(data.get('top', [0])[idx])
                        width = int(data.get('width', [0])[idx])
                        height = int(data.get('height', [0])[idx])

                        local_tokens.append(
                            {
                                'value': int(digits),
                                'digits': digits,
                                'confidence': confidence,
                                'left': left,
                                'top': top,
                                'width': width,
                                'height': height,
                                'variant': variant_name,
                                'psm': psm,
                            }
                        )

                if not local_tokens:
                    continue

                local_tokens.sort(key=lambda c: (c['top'], c['left'], -c['confidence']))
                top_row = local_tokens[0]['top']
                first_row = [c for c in local_tokens if c['top'] <= top_row + 8]
                ref_values = [c['value'] for c in first_row]

                # Tenta compor o preço completo pela concatenação dos tokens da mesma linha.
                # Isso recupera casos em que o OCR quebrou "272334" em pedaços menores.
                if len(first_row) >= 2:
                    first_row_sorted = sorted(first_row, key=lambda c: c['left'])
                    gaps = [
                        first_row_sorted[i + 1]['left'] - (
                            first_row_sorted[i]['left'] + first_row_sorted[i].get('width', 0)
                        )
                        for i in range(len(first_row_sorted) - 1)
                    ]
                    max_gap = max(gaps) if gaps else 0
                    max_allowed_gap = max(12, int(first_row_sorted[0].get('height', 0) * 1.4))
                    if max_gap <= max_allowed_gap:
                        combined_digits = ''.join(c['digits'] for c in first_row_sorted)
                        if 4 <= len(combined_digits) <= 8:
                            avg_conf = sum(max(c['confidence'], 0.0) for c in first_row_sorted) / len(first_row_sorted)
                            combined_score = (avg_conf + 1.0) * 2.3
                            # Só adicionar se não for idêntico a um único token já adicionado
                            single_digits = [c['digits'] for c in first_row_sorted]
                            if len(single_digits) == 1 and single_digits[0] == combined_digits:
                                # É apenas um token, não duplicar
                                pass
                            else:
                                voted_digit_scores[combined_digits] = (
                                    voted_digit_scores.get(combined_digits, 0.0) + combined_score
                                )

                for candidate in first_row:
                    normalized = self._normalize_price_value(candidate['value'], ref_values)
                    normalized_digits = str(normalized)
                    if len(normalized_digits) > 8:
                        continue

                    conf_weight = max(candidate['confidence'], 0.0) + 1.0
                    # Favorece levemente números mais longos para reduzir truncamento (ex.: 272334 vs 27233).
                    length_bonus = 1.0 + min(max(len(normalized_digits) - 4, 0), 3) * 0.25
                    score = conf_weight * length_bonus
                    voted_scores[normalized] = voted_scores.get(normalized, 0.0) + score

                    raw_digits = candidate['digits']
                    if len(raw_digits) > 8:
                        continue
                    voted_digit_scores[raw_digits] = voted_digit_scores.get(raw_digits, 0.0) + score

            best_digits = self._pick_best_voted_digits(voted_digit_scores)
            if best_digits:
                best_value = int(best_digits)
                if pending_direct_value is not None:
                    resolved_value = self._resolve_pending_direct_value(pending_direct_value, best_value)
                    if resolved_value is not None:
                        logger.debug(f"Preco OCR direto confirmado: {pending_direct_value} -> {resolved_value}")
                        return resolved_value
                    logger.debug(
                        f"Confirmacao OCR divergente ignorada: direto={pending_direct_value} voto={best_value}"
                    )
                    return pending_direct_value
                logger.debug(f"Preço OCR (voto por dígitos): {best_value}")
                return best_value

            if voted_scores:
                best_value = self._pick_best_voted_price(voted_scores)
                if best_value:
                    if pending_direct_value is not None:
                        resolved_value = self._resolve_pending_direct_value(pending_direct_value, best_value)
                        if resolved_value is not None:
                            logger.debug(f"Preco OCR direto confirmado: {pending_direct_value} -> {resolved_value}")
                            return resolved_value
                        logger.debug(
                            f"Confirmacao OCR divergente ignorada: direto={pending_direct_value} voto={best_value}"
                        )
                        return pending_direct_value
                    # Validação simples: range check
                    if best_value >= 100 and best_value <= 99_999_999:
                        logger.debug(f"Preço OCR: {best_value}")
                        return best_value
                    else:
                        logger.debug(f"Preço fora de range: {best_value}")
                        return None

            # Fallback rápido
            candidates = self._collect_numeric_candidates(image_region, trim_left=False)
            chosen = self._choose_candidate(candidates, prefer='largest')
            if chosen:
                if pending_direct_value is not None:
                    resolved_value = self._resolve_pending_direct_value(pending_direct_value, chosen['value'])
                    if resolved_value is not None:
                        logger.debug(f"Preco OCR direto confirmado por fallback: {pending_direct_value} -> {resolved_value}")
                        return resolved_value
                    logger.debug(
                        f"Fallback OCR divergente ignorado: direto={pending_direct_value} fallback={chosen['value']}"
                    )
                    return pending_direct_value
                if 100 <= chosen['value'] <= 99_999_999:
                    return chosen['value']
                logger.debug(f"Fallback de preco fora de range: {chosen['value']}")

            if pending_direct_value is not None:
                return pending_direct_value

            return None
            
        except Exception as e:
            logger.error(f"Erro ao extrair preço: {e}")
            return None

    def _needs_trailing_zero_confirmation(self, value):
        """Confirma leituras que podem ter recebido um zero extra no final."""
        return 100_000 <= value < 500_000 and value % 10 == 0

    def _needs_final_six_eight_confirmation(self, value):
        """Confirma leituras em que o OCR pode ter lido 6 como 8 no fim."""
        return value >= 1_000 and value % 10 == 8

    def _resolve_pending_direct_value(self, original_value, candidate_value):
        if not original_value or not candidate_value:
            return None
        if candidate_value == original_value:
            return candidate_value
        if self._is_without_extra_trailing_zero(original_value, candidate_value):
            return candidate_value
        if self._is_final_eight_as_six(original_value, candidate_value):
            return candidate_value
        return None

    def _is_without_extra_trailing_zero(self, original_value, candidate_value):
        if not original_value or not candidate_value:
            return False
        return original_value % 10 == 0 and original_value // 10 == candidate_value

    def _is_final_eight_as_six(self, original_value, candidate_value):
        original_digits = str(original_value)
        candidate_digits = str(candidate_value)
        return (
            original_digits.endswith('8')
            and candidate_digits.endswith('6')
            and len(original_digits) == len(candidate_digits)
            and original_digits[:-1] == candidate_digits[:-1]
        )

    def extract_quantity_from_region(self, image_region):
        """
        Extrai apenas quantidade vendida de uma região
        
        Args:
            image_region: PIL Image
            
        Returns:
            int com quantidade ou None
        """
        try:
            candidates = self._collect_numeric_candidates(image_region, trim_left=False)
            chosen = self._choose_candidate(candidates, prefer='smallest')

            if chosen:
                logger.debug(
                    f"Qtd OCR escolhida: value={chosen['value']} conf={chosen['confidence']} psm={chosen['psm']} raw={chosen['raw']}"
                )
                return chosen['value']

            processed = self.preprocess_image(image_region, enhance_contrast=True, enhance_sharpness=True)
            text = pytesseract.image_to_string(processed, lang='eng', config='--psm 7 --oem 3')
            numbers = re.findall(r'\d+', text)
            if numbers:
                return int(min(numbers, key=int))

            logger.warning(f"OCR de quantidade vazio: {text!r}")
            return None
            
        except Exception as e:
            logger.error(f"Erro ao extrair quantidade: {e}")
            return None
    
    def extract_item_name(self, image_region):
        """
        Extrai apenas nome do item
        
        Args:
            image_region: PIL Image
            
        Returns:
            string com nome do item
        """
        try:
            processed = self.preprocess_image(image_region)
            
            text = pytesseract.image_to_string(
                processed,
                lang=self.language,
                config='--psm 6'
            )
            
            # Remover números e caracteres especiais
            name = re.sub(r'\d+', '', text).strip()
            
            # Remover caracteres não-alfanuméricos extras
            name = re.sub(r'[^\w\s\-áéíóúâêôãõçÁÉÍÓÚÂÊÔÃÕÇ]', '', name)
            
            return name
            
        except Exception as e:
            logger.error(f"Erro ao extrair nome: {e}")
            return ""
    
    def detect_item_boundaries(self, image, min_height=30, max_height=150):
        """
        Detecta limites de cada item listado (para automatizar extração)
        
        Args:
            image: PIL Image da lista de itens
            min_height: altura mínima de um item em pixels
            max_height: altura máxima de um item em pixels
            
        Returns:
            lista de tuplas (x1, y1, x2, y2) para cada item detectado
        """
        try:
            import numpy as np
            
            # Converter para array
            img_array = np.array(image.convert('L'))
            
            # Encontrar linhas horizontais (separadores de itens)
            rows = np.sum(img_array > 200, axis=1)  # Pixels brancos
            
            # Detectar mudanças
            diff = np.diff(rows)
            
            # Encontrar bordas (onde há mudanças significativas)
            threshold = np.std(diff) * 2
            edges = np.where(np.abs(diff) > threshold)[0]
            
            # Agrupar edges em pares (início e fim)
            boundaries = []
            for i in range(0, len(edges) - 1, 2):
                y1 = edges[i]
                y2 = edges[i + 1]
                
                height = y2 - y1
                if min_height < height < max_height:
                    x1, x2 = 0, image.width
                    boundaries.append((x1, y1, x2, y2))
            
            return boundaries
            
        except Exception as e:
            logger.error(f"Erro ao detectar limites: {e}")
            return []
