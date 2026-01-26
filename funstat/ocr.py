import re
import os
import io
import asyncio
import tempfile
from PIL import Image, ImageEnhance, ImageFilter, ImageStat, ImageOps

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

OCR_AVAILABLE = False
EASYOCR_AVAILABLE = False

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    pass

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    pass

from .utils import safe_print
from .utils import get_tesseract_path

if OCR_AVAILABLE:
    tesseract_path = get_tesseract_path()
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path


def normalize_ocr_text(text):
    if not text:
        return text

    text = ' '.join(text.split())

    text = re.sub(r'[^\w\s]', '', text)

    replacements = {
        'α': 'а', 'Α': 'А', 'a': 'а', 'A': 'А',
        'π': 'п', 'Π': 'П', 'p': 'р', 'P': 'Р',
        'κ': 'к', 'Κ': 'К', 'k': 'к', 'K': 'К',
        'γ': 'г', 'Γ': 'Г',
        'ο': 'о', 'Ο': 'О', 'o': 'о', 'O': 'О',
        'e': 'е', 'E': 'Е',
        'c': 'с', 'C': 'С',
        'y': 'у', 'Y': 'У',
        'x': 'х', 'X': 'Х',
        'm': 'м', 'M': 'М',
        'н': 'н', 'H': 'Н', 'h': 'н',
        'i': 'и', 'I': 'И',
        'l': 'л', 'L': 'Л',
        'w': 'ш', 'W': 'Ш',
        'v': 'в', 'V': 'В',
        'u': 'у', 'U': 'У',
        't': 'т', 'T': 'Т',
        's': 'с', 'S': 'С',
        'r': 'р', 'R': 'Р',
        'n': 'н', 'N': 'Н',
        'd': 'д', 'D': 'Д',
        'b': 'б', 'B': 'Б',
        'g': 'г', 'G': 'Г',
        'z': 'з', 'Z': 'З',
        'j': 'й', 'J': 'Й',
        'q': 'к', 'Q': 'К',
        '0': 'О', '0': 'о',
        'pogot': 'робот',
    }

    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)

    common_fixes = {
        'звезла': 'звезда', 'звезл': 'звезда', 'звез': 'звезда',
        'мишка': 'мишка', 'ми': 'мишка', 'миш': 'мишка',
        'робот': 'робот', 'собака': 'собака',
        'звезда': 'звезда',
        'мишк': 'мишка',
        'мишкa': 'мишка',
        'обезьяна': 'обезьяна', 'обезьян': 'обезьяна', 'обезья': 'обезьяна',
        'обезь': 'обезьяна', 'обез': 'обезьяна', 'безьяна': 'обезьяна',
        'обезьна': 'обезьяна', 'обезян': 'обезьяна',
    }

    text_lower = text.lower()
    for wrong, correct in common_fixes.items():
        if wrong.lower() in text_lower or text_lower.startswith(wrong.lower()):
            text = correct
            break

    return text.strip()


def preprocess_image(image, method='auto'):
    try:
        if image.mode != 'RGB':
            image = image.convert('RGB')

        original_size = image.size
        width, height = original_size

        min_width, min_height = 1200, 1000
        if width < min_width or height < min_height:
            scale = max(min_width / width, min_height / height) * 4.0
            new_size = (int(width * scale), int(height * scale))
            image = image.resize(new_size, Image.LANCZOS)
            safe_print(f"[OCR] Увеличен размер: {width}x{height} -> {new_size[0]}x{new_size[1]} (scale={scale:.2f})")

        if method == 'binary' or method == 'auto':
            gray = image.convert('L')

            if NUMPY_AVAILABLE:
                import numpy as np
                from PIL import ImageOps
                img_array = np.array(gray)

                mean_brightness = np.mean(img_array)
                safe_print(f"[OCR] Средняя яркость: {mean_brightness:.1f}")

                if mean_brightness > 160:
                    gray_enhanced = ImageOps.autocontrast(gray, cutoff=10)
                    img_array = np.array(gray_enhanced)
                    safe_print(f"[OCR] Применен autocontrast для светлого изображения")

                try:
                    import cv2
                    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
                    img_array = clahe.apply(img_array)
                    safe_print(f"[OCR] CLAHE применен для улучшения контраста")
                except:
                    pass

                hist, bins = np.histogram(img_array.flatten(), 256, [0, 256])
                cdf = hist.cumsum()
                cdf_normalized = cdf * float(hist.max()) / cdf.max()

                threshold_candidates = np.where(cdf_normalized > cdf_normalized.max() * 0.1)[0]
                if len(threshold_candidates) > 0:
                    threshold = int(np.median(threshold_candidates))
                else:
                    threshold = 127

                if mean_brightness > 180:
                    threshold = min(threshold, 120)
                    safe_print(f"[OCR] ОЧЕНЬ светлое изображение, агрессивный порог: {threshold}")
                elif mean_brightness > 160:
                    threshold = min(threshold, 130)
                    safe_print(f"[OCR] Светлое изображение, порог: {threshold}")

                binary = np.where(img_array > threshold, 255, 0).astype(np.uint8)
                image = Image.fromarray(binary).convert('RGB')
                safe_print(f"[OCR] Бинаризация (порог={threshold})")
            else:
                from PIL import ImageOps
                image = ImageOps.autocontrast(gray, cutoff=10)
                image = image.convert('RGB')

        if method == 'deskew' or method == 'auto':
            try:
                from PIL import ImageStat
                best_angle = 0
                best_score = 0

                angles_to_try = list(range(-20, 21, 2))

                for angle in angles_to_try:
                    rotated = image.rotate(angle, expand=False, fillcolor='white')
                    stat = ImageStat.Stat(rotated.convert('L'))

                    contrast_score = sum(stat.stddev) + (stat.mean[0] * 0.1)
                    if contrast_score > best_score:
                        best_score = contrast_score
                        best_angle = angle

                if abs(best_angle) > 0.5:
                    image = image.rotate(best_angle, expand=False, fillcolor='white', resample=Image.BICUBIC)
                    safe_print(f"[OCR] Выровнено изображение: поворот на {best_angle:.1f}° (score={best_score:.1f})")
            except Exception as e:
                safe_print(f"[OCR] Ошибка выравнивания: {e}")

        if method == 'enhance' or method == 'auto':
            gray_for_analysis = image.convert('L')
            stat = ImageStat.Stat(gray_for_analysis)
            mean_brightness = stat.mean[0]
            std_dev = stat.stddev[0] if stat.stddev else 0

            if mean_brightness < 100:
                enhancer = ImageEnhance.Brightness(image)
                image = enhancer.enhance(1.8)
                safe_print(f"[OCR] Увеличена яркость (было темно: {mean_brightness:.0f})")
            elif mean_brightness > 200:
                enhancer = ImageEnhance.Brightness(image)
                image = enhancer.enhance(0.7)
                safe_print(f"[OCR] Уменьшена яркость (было светло: {mean_brightness:.0f})")

            if mean_brightness > 170:
                if NUMPY_AVAILABLE:
                    import numpy as np
                    img_array = np.array(image.convert('L'))
                    dark_pixels = np.sum(img_array < 128)
                    total_pixels = img_array.size
                    dark_ratio = dark_pixels / total_pixels
                    if dark_ratio < 0.35:
                        img_array = 255 - img_array
                        image = Image.fromarray(img_array).convert('RGB')
                        safe_print(f"[OCR] ИНВЕРСИЯ! Темный текст на светлом (ratio={dark_ratio:.2f})")

            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(3.8)

            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(3.2)

            image = image.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=2))
            safe_print(f"[OCR] Применен UnsharpMask для рукописного текста")

        if method == 'denoise' or method == 'auto':
            image = image.filter(ImageFilter.MedianFilter(size=3))
            image = image.filter(ImageFilter.SMOOTH_MORE)

        if method == 'auto':
            gray_final = image.convert('L')
            stat_final = ImageStat.Stat(gray_final)
            if stat_final.mean[0] > 150:
                from PIL import ImageOps
                pass

        return image
    except Exception as e:
        safe_print(f"[OCR] Ошибка предобработки ({method}): {e}")
        return image


async def extract_text_from_image(image_data):
    if not image_data:
        return None

    try:
        original_image = Image.open(io.BytesIO(image_data))

        preprocess_methods = ['auto', 'binary', 'enhance', 'deskew', 'denoise']
        all_results = []

        if OCR_AVAILABLE:
            try:
                languages_to_try = ['rus', 'rus+eng', 'eng']
                configs = [
                    r'--oem 3 --psm 7',
                    r'--oem 3 --psm 8',
                    r'--oem 1 --psm 7',
                    r'--oem 1 --psm 8',
                    r'--oem 3 --psm 13',
                    r'--oem 3 --psm 6',
                    r'--oem 3 --psm 11',
                    r'--oem 3 --psm 10',
                    r'--oem 3 --psm 3',
                    r'--oem 3 --psm 4',
                ]

                best_text = None
                best_score = 0
                best_method = None

                for method in preprocess_methods:
                    try:
                        image_processed = preprocess_image(original_image.copy(), method=method)

                        for lang in languages_to_try:
                            for config in configs:
                                try:
                                    text = pytesseract.image_to_string(image_processed, lang=lang, config=config)
                                    text = text.strip()

                                    if text and len(text) >= 2:
                                        clean_text = re.sub(r'[^\w\s]', '', text)
                                        if not clean_text:
                                            continue

                                        cyrillic_count = sum(1 for c in clean_text if 'А' <= c <= 'Я' or 'а' <= c <= 'я' or c == 'ё' or c == 'Ё')
                                        latin_count = sum(1 for c in clean_text if 'A' <= c <= 'Z' or 'a' <= c <= 'z')
                                        digit_count = sum(1 for c in clean_text if c.isdigit())

                                        score = cyrillic_count * 5 + latin_count * 2 - digit_count * 2

                                        if 3 <= len(clean_text) <= 15:
                                            score += len(clean_text) * 0.5

                                        if all(c.isalnum() or c.isspace() for c in clean_text):
                                            score += 3

                                        safe_print(f"[OCR] Tesseract (method={method}, lang={lang}, config={config}): '{text}' (score={score:.1f})")

                                        if cyrillic_count >= 1 or (latin_count >= 2 and len(clean_text) >= 3):
                                            if score > best_score:
                                                best_text = text
                                                best_score = score
                                                best_method = f"{method}/{lang}/{config}"
                                                safe_print(f"[OCR] ⭐ Лучший результат: '{text}' (score={score:.1f}, method={best_method})")

                                        if score > 5:
                                            all_results.append((text, score, f"{method}/{lang}/{config}"))
                                except Exception as e:
                                    error_str = str(e).lower()
                                    if 'rus' in lang and ('language data file' in error_str or 'language' in error_str):
                                        break
                                    continue
                    except Exception as e:
                        safe_print(f"[OCR] Ошибка предобработки ({method}): {e}")
                        continue

                if best_text and best_score > 3:
                    text = normalize_ocr_text(best_text)
                    safe_print(f"[OCR] ✅ Финальный результат Tesseract: '{text}' (score={best_score:.1f}, method={best_method})")
                    return text

                if all_results and best_score <= 3:
                    all_results.sort(key=lambda x: x[1], reverse=True)
                    for text, score, method_info in all_results[:3]:
                        normalized = normalize_ocr_text(text)
                        if normalized and len(normalized) >= 2:
                            safe_print(f"[OCR] Пробую альтернативный результат: '{normalized}' (score={score:.1f})")
                            return normalized
            except Exception as e:
                safe_print(f"[OCR] Tesseract ошибка: {e}")

        if EASYOCR_AVAILABLE:
            try:
                if not hasattr(extract_text_from_image, 'reader'):
                    safe_print("[OCR] Инициализирую EasyOCR reader...")
                    import ssl
                    ssl._create_default_https_context = ssl._create_unverified_context
                    extract_text_from_image.reader = easyocr.Reader(['ru', 'en'], gpu=False)

                easyocr_results = []

                for method in ['auto', 'binary']:
                    try:
                        img_processed = preprocess_image(original_image.copy(), method=method)

                        if NUMPY_AVAILABLE:
                            img_array = np.array(img_processed)
                            results = extract_text_from_image.reader.readtext(img_array)
                        else:
                            import tempfile
                            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                                img_processed.save(tmp_file.name)
                                tmp_path = tmp_file.name
                            try:
                                results = extract_text_from_image.reader.readtext(tmp_path)
                            finally:
                                try:
                                    os.unlink(tmp_path)
                                except:
                                    pass

                        if results:
                            for result in results:
                                if len(result) >= 2:
                                    text = result[1]
                                    confidence = result[2] if len(result) > 2 else 0
                                    clean_text = re.sub(r'[^\w\s]', '', text)

                                    if clean_text and len(clean_text) >= 2:
                                        cyrillic_count = sum(1 for c in clean_text if 'А' <= c <= 'Я' or 'а' <= c <= 'я' or c == 'ё' or c == 'Ё')
                                        latin_count = sum(1 for c in clean_text if 'A' <= c <= 'Z' or 'a' <= c <= 'z')

                                        score = confidence * 100 + cyrillic_count * 10 + latin_count * 5

                                        easyocr_results.append((text, score, confidence, method))
                                        safe_print(f"[OCR] EasyOCR (method={method}): '{text}' (confidence={confidence:.2f}, score={score:.1f})")
                    except Exception as e:
                        safe_print(f"[OCR] EasyOCR ошибка с методом {method}: {e}")
                        continue

                if easyocr_results:
                    easyocr_results.sort(key=lambda x: x[1], reverse=True)
                    best_easyocr = easyocr_results[0]
                    text = best_easyocr[0]
                    normalized = normalize_ocr_text(text)

                    if normalized and len(normalized) >= 2:
                        safe_print(f"[OCR] ✅ Финальный результат EasyOCR: '{normalized}' (confidence={best_easyocr[2]:.2f}, score={best_easyocr[1]:.1f})")
                        return normalized
            except Exception as e:
                safe_print(f"[OCR] EasyOCR критическая ошибка: {e}")

        safe_print("[OCR] ❌ Не удалось распознать текст ни одним методом")
        return None
    except Exception as e:
        safe_print(f"[OCR] Ошибка обработки изображения: {e}")
        return None


def extract_word_from_captcha(text, image_data=None):
    if not text:
        return None, None, 0

    emoji_to_words = {
        '👻': ['призрак', 'ghost', 'привидение', 'дух', 'phantom', 'призр', 'приз', 'nризрак', 'пρизρак'],
        '🐶': ['собака', 'dog', 'пес', 'пёс', 'собак', 'песик', 'собакa', 'соба', 'coбака', 'сoбака'],
        '🐰': ['кролик', 'заяц', 'rabbit', 'bunny', 'зайчик', 'крол', 'кроли', 'кρолик', 'кρоли'],
        '🐇': ['кролик', 'заяц', 'rabbit', 'bunny', 'зайчик', 'крол', 'кроли', 'кρолик', 'кρоли'],
        '🦊': ['лиса', 'fox', 'лис', 'лисa', 'лисица', 'лиска', 'лисок', 'лисо', 'nиса', 'лиса', 'nuca', 'лисы'],
        '⭐': ['звезда', 'star', 'звезд', 'звездочка', 'звезла', 'звезл', 'звез', 'звёзд', 'везда', 'звeзда'],
        '🌟': ['звезда', 'star', 'звезд', 'звездочка', 'звезла', 'звезл', 'звез', 'звёзд', 'везда', 'звeзда'],
        '💫': ['звезда', 'star', 'звезд', 'звездочка', 'звезла', 'звезл', 'звез', 'звёзд', 'везда', 'звeзда'],
        '✨': ['звезда', 'star', 'звезд', 'звездочка', 'звезла', 'звезл', 'звез', 'звёзд', 'везда', 'звeзда'],
        '🐻': ['мишка', 'bear', 'медведь', 'медвежонок', 'мишк', 'миш', 'ми', 'мишка', 'мuшка'],
        '🤖': ['робот', 'robot', 'pogot', 'роб', 'робо', 'ρобот', 'poбот', 'робот', 'рoбoт', 'робoт', '00000', 'pooor'],
        '🐵': ['обезьяна', 'monkey', 'обезьян', 'обезья', 'обезь', 'обез', 'мартышка', 'ape', 'обeзьяна', 'обeзь'],
        '🐒': ['обезьяна', 'monkey', 'обезьян', 'обезья', 'обезь', 'обез', 'мартышка', 'ape', 'обeзьяна', 'обeзь'],
    }

    text_lower = text.lower().replace(' ', '').replace('\n', '')
    text_normalized = normalize_ocr_text(text)
    text_normalized_lower = text_normalized.lower().replace(' ', '').replace('\n', '')

    safe_print(f"[DEBUG extract_word] Ищу слово в тексте: '{text[:200] if len(text) > 200 else text}' (normalized: '{text_normalized_lower[:200] if len(text_normalized_lower) > 200 else text_normalized_lower}')")

    for emoji, words in emoji_to_words.items():
        for word in words:
            if len(word) < 2:
                continue
            pattern = r'\b' + re.escape(word) + r'\b'
            if re.search(pattern, text_lower) or re.search(pattern, text_normalized_lower):
                safe_print(f"[✓ HIGH] Найдено точное совпадение: '{word}' -> {emoji}")
                return word, emoji, 100

    for emoji, words in emoji_to_words.items():
        for word in words:
            if len(word) < 3:
                continue
            pattern = r'\b' + re.escape(word) + r'\w*\b'
            if re.search(pattern, text_lower) or re.search(pattern, text_normalized_lower):
                safe_print(f"[✓ GOOD] Найдено частичное совпадение (слово): '{word}' -> {emoji}")
                return word, emoji, 85

    text_clean = text_normalized_lower.strip()
    text_clean_letters = re.sub(r'[^\w]', '', text_clean)

    short_word_matches = {
        'а': None,
        'аа': None,
        'о': None,
        'оо': None,
        'и': None,
        'к': None,
        'м': None,
        'п': None,
        'г': None,
        'е': None,
        'ы': None,
        'на': None,
        'ть': None,
        'бо': None,
        'ры': None,
        'т': None,
        '.': None,
        ',': None,
        '=': None,

        'ми': 'мишка',
        'му': 'мишка',
        'миш': 'мишка',
        'мкь': 'мишка',

        'лис': 'лиса',
        'иса': 'лиса',
        'мса': 'лиса',
        'ус': 'лиса',

        'роб': 'робот',
        'бот': 'робот',

        'соб': 'собака',
        'бака': 'собака',
        'сак': 'собака',
        'ака': 'собака',

        'звез': 'звезда',
        'зве': 'звезда',
        'везд': 'звезда',
        'веда': 'звезда',
        'звеа': 'звезда',

        'приз': 'призрак',
        'призр': 'призрак',
        'пиг': 'призрак',
        'прак': 'призрак',

        'обез': 'обезьяна',
        'без': 'обезьяна',
        'езь': 'обезьяна',
        'яна': 'обезьяна',
        'обо': 'обезьяна',

        'крол': 'кролик',
        'кро': 'кролик',
        'рол': 'кролик',
        'олик': 'кролик',
    }

    ocr_error_fixes = {
        'призр': 'призрак',
        'приз': 'призрак',
        'призра': 'призрак',
        'позврак': 'призрак',
        'поз': 'призрак',
        'пига': 'призрак',
        'прак': 'призрак',
        'прзрак': 'призрак',
        'бизоак': 'призрак',
        'впрзрак': 'призрак',
        'пророк': 'призрак',
        'бьиаыак': 'призрак',
        'иаыак': 'призрак',
        'правак': 'призрак',
        'пнзрак': 'призрак',
        'пвизрак': 'призрак',
        'зрак': 'призрак',
        'соб': 'собака',
        'соба': 'собака',
        'собак': 'собака',
        'бака': 'собака',
        'ака': 'собака',
        'обыка': 'собака',
        'быка': 'собака',
        'крол': 'кролик',
        'кроли': 'кролик',
        'кролик': 'кролик',
        'кролих': 'кролик',
        'ротик': 'кролик',
        'отик': 'кролик',
        'ролик': 'кролик',
        'колик': 'кролик',
        'колмк': 'кролик',
        'радик': 'кролик',
        'коолмх': 'кролик',
        'оолмх': 'кролик',
        'зая': 'заяц',
        'зай': 'заяц',
        'заяц': 'заяц',
        'лис': 'лиса',
        'лиса': 'лиса',
        'лисо': 'лиса',
        'лисы': 'лиса',
        'лиска': 'лиса',
        'nиса': 'лиса',
        'лuса': 'лиса',
        'nuca': 'лиса',
        'nusa': 'лиса',
        'иса': 'лиса',
        'мса': 'лиса',
        'лиа': 'лиса',
        'амса': 'лиса',
        'лмсв': 'лиса',
        'ус': 'лиса',
        'пис': 'лиса',
        'лиха': 'лиса',
        'риса': 'лиса',
        'писа': 'лиса',
        'паса': 'лиса',
        'звез': 'звезда',
        'везда': 'звезда',
        'везд': 'звезда',
        'звезд': 'звезда',
        'звезл': 'звезда',
        'звезла': 'звезда',
        'звезаз': 'звезда',
        'зве': 'звезда',
        'веда': 'звезда',
        'звеа': 'звезда',
        'звеза': 'звезда',
        'ззезла': 'звезда',
        'ззезд': 'звезда',
        'ми': 'мишка',
        'миш': 'мишка',
        'мишк': 'мишка',
        'мi': 'мишка',
        'мицка': 'мишка',
        'мицика': 'мишка',
        'умка': 'мишка',
        'му': 'мишка',
        'мммка': 'мишка',
        'мкь': 'мишка',
        'роб': 'робот',
        'робо': 'робот',
        'робот': 'робот',
        'робoт': 'робот',
        'рoбот': 'робот',
        'рoбoт': 'робот',
        'ρобот': 'робот',
        'poбот': 'робот',
        'роборт': 'робот',
        'pobor': 'робот',
        'pooot': 'робот',
        'аабол': 'робот',
        'работ': 'робот',
        'рабо': 'робот',
        'рзбот': 'робот',
        'збот': 'робот',
        'зобот': 'робот',
        'работе': 'робот',
        'обез': 'обезьяна',
        'обезь': 'обезьяна',
        'обезья': 'обезьяна',
        'обезьян': 'обезьяна',
        'обезьянз': 'обезьяна',
        'обезьяна': 'обезьяна',
        'безьяна': 'обезьяна',
        'безяна': 'обезьяна',
        'езьяна': 'обезьяна',
        'зьяна': 'обезьяна',
        'обезьна': 'обезьяна',
        'обезян': 'обезьяна',
        'ооянна': 'обезьяна',
        'ооеъана': 'обезьяна',
        'оеъана': 'обезьяна',
        'обо': 'обезьяна',
        'обаьвыь': 'обезьяна',
        'обе5ь': 'обезьяна',
        'ббещине': 'обезьяна',
        'бещине': 'обезьяна',
        'обеывна': 'обезьяна',
        'еывна': 'обезьяна',
        'эбезьнна': 'обезьяна',
        'эбезьана': 'обезьяна',
        'эбезь': 'обезьяна',
        'оозак': None,
        'зама': None,
        'ан': None,
        'м': None,
        'г': None,
        'е': None,
        'на': None,
        'ры': None,
        'т': None,
        'ть': None,
        'бо': None,
        'ищи': None,
        'нee': None,
        'hee': None,
        'ioe': None,
        'а': None,
        'аа': None,
        'ааа': None,
        'и': None,
        'о': None,
        'оо': None,
        'к': None,
        '.': None,
        ',': None,
        'о.': None,
        'а.': None,
        'м.': None,
        'ом.': None,
    }

    text_original_clean = re.sub(r'[^\w]', '', text_lower).lower()

    if text_original_clean in short_word_matches:
        fix_word = short_word_matches[text_original_clean]
        if fix_word is None:
            safe_print(f"[SKIP] Пропускаю короткий мусор: '{text_original_clean}'")
        else:
            for emoji, words in emoji_to_words.items():
                if fix_word in words:
                    safe_print(f"[✓ SHORT] Короткое слово '{text_original_clean}' -> '{fix_word}' -> {emoji}")
                    return fix_word, emoji, 70

    if text_original_clean in ocr_error_fixes:
        fix_word = ocr_error_fixes[text_original_clean]
        if fix_word is None:
            safe_print(f"[SKIP] Пропускаю неправильное OCR распознавание: '{text_original_clean}'")
        else:
            for emoji, words in emoji_to_words.items():
                if fix_word in words:
                    safe_print(f"[✓ FIXED] Исправление OCR (оригинал) '{text_original_clean}' -> '{fix_word}' -> {emoji}")
                    return fix_word, emoji, 75

    text_clean_check = text_clean_letters.lower()

    if text_clean_check in short_word_matches:
        fix_word = short_word_matches[text_clean_check]
        if fix_word is None:
            safe_print(f"[SKIP] Пропускаю мусор: '{text_clean_check}'")
        else:
            for emoji, words in emoji_to_words.items():
                if fix_word in words:
                    safe_print(f"[✓ SHORT] '{text_clean_check}' -> '{fix_word}' -> {emoji}")
                    return fix_word, emoji, 65

    if text_clean_check in ocr_error_fixes:
        fix_word = ocr_error_fixes[text_clean_check]
        if fix_word is None:
            safe_print(f"[SKIP] Пропускаю неправильное OCR распознавание: '{text_clean_check}'")
        else:
            for emoji, words in emoji_to_words.items():
                if fix_word in words:
                    safe_print(f"[✓ FIXED] Исправление OCR '{text_clean_check}' -> '{fix_word}' -> {emoji}")
                    return fix_word, emoji, 75

    if len(text_clean_letters) >= 2 and len(text_clean_letters) <= 15:
        for emoji, words in emoji_to_words.items():
            for word in words:
                if len(word) < 3:
                    continue
                word_lower = word.lower()

                if word_lower.startswith(text_clean_letters):
                    safe_print(f"[~ MEDIUM] Найдено по началу слова: '{text_clean_letters}' -> '{word}' -> {emoji}")
                    return word, emoji, 60

                if word_lower.endswith(text_clean_letters) and len(text_clean_letters) >= 4:
                    safe_print(f"[~ MEDIUM] Найдено по окончанию слова: '{text_clean_letters}' -> '{word}' -> {emoji}")
                    return word, emoji, 55

                if len(text_clean_letters) >= 4 and len(word_lower) >= 4:
                    word_end = word_lower[-len(text_clean_letters):] if len(text_clean_letters) <= len(word_lower) else word_lower
                    text_end = text_clean_letters[-len(word_end):] if len(word_end) <= len(text_clean_letters) else text_clean_letters
                    if word_end == text_end and len(word_end) >= 3:
                        safe_print(f"[~ MEDIUM] Найдено по совпадению окончания: '{text_clean_letters}' -> '{word}' -> {emoji}")
                        return word, emoji, 55

                if text_clean_letters in word_lower and len(text_clean_letters) >= 5:
                    match_start = word_lower.find(text_clean_letters)
                    if match_start >= len(word_lower) - len(text_clean_letters) - 1:
                        safe_print(f"[~ LOW] Найдено как часть слова (в конце): '{text_clean_letters}' -> '{word}' -> {emoji}")
                        return word, emoji, 45

                if len(text_clean_letters) >= 2 and len(word) >= 2:
                    min_len = min(len(text_clean_letters), len(word), 3)
                    if text_clean_letters[:min_len] == word_lower[:min_len]:
                        safe_print(f"[~ LOW] Найдено по первым {min_len} буквам: '{text_clean_letters}' -> '{word}' -> {emoji}")
                        return word, emoji, 40

    if len(text_clean) >= 3 and len(text_clean) <= 6:
        safe_print(f"[?] Пробую найти похожее слово для короткого текста: '{text_clean}'")

        ocr_error_fixes_short = {
            'aga': ['собака', 'обезьяна'],
            'обез': 'обезьяна',
            'обезь': 'обезьяна',
            'безья': 'обезьяна',
            'езьян': 'обезьяна',
            'зьяна': 'обезьяна',
            'обезьн': 'обезьяна',
        }

        if text_clean in ocr_error_fixes_short:
            fix_word_or_list = ocr_error_fixes_short[text_clean]
            fix_words = fix_word_or_list if isinstance(fix_word_or_list, list) else [fix_word_or_list]
            for fix_word in fix_words:
                for emoji, words in emoji_to_words.items():
                    if fix_word in words:
                        safe_print(f"[~ LOW] Исправление OCR '{text_clean}' -> '{fix_word}' -> {emoji}")
                        return fix_word, emoji, 30

        if text_clean not in ocr_error_fixes_short:
            for emoji, words in emoji_to_words.items():
                for word in words:
                    if len(word) >= 3 and text_clean[0] == word[0]:
                        if len(text_clean) >= 2 and len(word) >= 2:
                            min_match = min(3, len(text_clean), len(word))
                            if text_clean[:min_match] == word[:min_match]:
                                safe_print(f"[! VERY LOW] Найдено по похожести: '{text_clean}' -> '{word}' -> {emoji}")
                                return word, emoji, 20

    safe_print(f"[✗ FAIL] Не найдено соответствие для текста: '{text}'")
    return None, None, 0


def find_matching_button(buttons, target_emoji):
    if not buttons or not target_emoji:
        safe_print(f"[DEBUG find_matching_button] buttons={buttons}, target_emoji={target_emoji}")
        return None

    emoji_synonyms = {
        '🐰': ['🐇'],
        '🐇': ['🐰'],
        '🐵': ['🐒'],
        '🐒': ['🐵'],
        '⭐': ['🌟', '💫', '✨'],
        '🌟': ['⭐', '💫', '✨'],
        '💫': ['⭐', '🌟', '✨'],
        '✨': ['⭐', '🌟', '💫'],
    }

    target_emojis = [target_emoji]
    if target_emoji in emoji_synonyms:
        target_emojis.extend(emoji_synonyms[target_emoji])
        safe_print(f"[DEBUG find_matching_button] Синонимы эмодзи '{target_emoji}': {emoji_synonyms[target_emoji]}")

    invisible_chars = ['ㅤ', '\u200B', '\u200C', '\u200D', '\uFEFF', '\u00A0', '\u3164']

    def clean_button_text(text):
        if not text:
            return text
        original = text
        for char in invisible_chars:
            text = text.replace(char, '')
        cleaned = text.strip()
        if original != cleaned:
            safe_print(f"[DEBUG find_matching_button] Очистка текста: '{repr(original)}' -> '{repr(cleaned)}'")
        return cleaned

    safe_print(f"[DEBUG find_matching_button] Ищу эмодзи '{target_emoji}' (и синонимы: {[e for e in target_emojis if e != target_emoji]}) в кнопках...")
    safe_print(f"[DEBUG find_matching_button] Всего строк кнопок: {len(buttons)}")

    target_emoji_unicodes = [ord(e) for e in target_emojis]
    safe_print(f"[DEBUG find_matching_button] Unicode коды: {[f'U+{code:04X}' for code in target_emoji_unicodes]}")

    for row_idx, row in enumerate(buttons):
        safe_print(f"[DEBUG find_matching_button] Строка {row_idx}: {len(row)} кнопок")
        for btn_idx, btn in enumerate(row):
            btn_text_raw = btn.text if btn.text else ""
            btn_text_clean = clean_button_text(btn_text_raw)

            safe_print(f"[DEBUG find_matching_button]   Кнопка [{row_idx}][{btn_idx}]: raw='{repr(btn_text_raw)}', clean='{repr(btn_text_clean)}'")

            for check_emoji in target_emojis:
                if check_emoji in btn_text_raw or check_emoji in btn_text_clean:
                    if check_emoji == target_emoji:
                        safe_print(f"[DEBUG find_matching_button] ✅ НАЙДЕНО точное совпадение в кнопке [{row_idx}][{btn_idx}]")
                    else:
                        safe_print(f"[DEBUG find_matching_button] ✅ НАЙДЕНО синоним эмодзи '{check_emoji}' (вместо '{target_emoji}') в кнопке [{row_idx}][{btn_idx}]")
                return btn

            if btn_text_raw:
                for char in btn_text_raw:
                    char_unicode = ord(char)
                    if char_unicode in target_emoji_unicodes:
                        found_index = target_emoji_unicodes.index(char_unicode)
                        found_emoji = target_emojis[found_index]
                        if found_emoji == target_emoji:
                            safe_print(f"[DEBUG find_matching_button] ✅ НАЙДЕНО по Unicode коду в кнопке [{row_idx}][{btn_idx}]")
                        else:
                            safe_print(f"[DEBUG find_matching_button] ✅ НАЙДЕНО синоним эмодзи '{found_emoji}' (вместо '{target_emoji}') по Unicode коду в кнопке [{row_idx}][{btn_idx}]")
                        return btn

            try:
                import unicodedata
                normalized_btn = unicodedata.normalize('NFKD', btn_text_raw)
                for check_emoji in target_emojis:
                    normalized_target = unicodedata.normalize('NFKD', check_emoji)
                    if normalized_target in normalized_btn:
                        if check_emoji == target_emoji:
                            safe_print(f"[DEBUG find_matching_button] ✅ НАЙДЕНО по нормализованному эмодзи в кнопке [{row_idx}][{btn_idx}]")
                        else:
                            safe_print(f"[DEBUG find_matching_button] ✅ НАЙДЕНО синоним эмодзи '{check_emoji}' (вместо '{target_emoji}') по нормализованному эмодзи в кнопке [{row_idx}][{btn_idx}]")
                        return btn
            except:
                pass

    synonyms_list = [e for e in target_emojis if e != target_emoji]
    if synonyms_list:
        safe_print(f"[DEBUG find_matching_button] ❌ Кнопка с эмодзи '{target_emoji}' или его синонимами {synonyms_list} не найдена")
    else:
        safe_print(f"[DEBUG find_matching_button] ❌ Кнопка с эмодзи '{target_emoji}' не найдена")
    return None
