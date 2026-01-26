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
        
        min_width, min_height = 1000, 800
        if width < min_width or height < min_height:
            scale = max(min_width / width, min_height / height) * 3.0
            new_size = (int(width * scale), int(height * scale))
            image = image.resize(new_size, Image.BICUBIC)
            safe_print(f"[OCR] Увеличен размер: {width}x{height} -> {new_size[0]}x{new_size[1]} (scale={scale:.2f})")
        
        if method == 'binary' or method == 'auto':
            gray = image.convert('L')
            
            if NUMPY_AVAILABLE:
                import numpy as np
                img_array = np.array(gray)
                
                hist, bins = np.histogram(img_array.flatten(), 256, [0, 256])
                cdf = hist.cumsum()
                cdf_normalized = cdf * float(hist.max()) / cdf.max()
                
                threshold_candidates = np.where(cdf_normalized > cdf_normalized.max() * 0.1)[0]
                if len(threshold_candidates) > 0:
                    threshold = int(np.median(threshold_candidates))
                else:
                    threshold = 127
                
                mean_brightness = np.mean(img_array)
                if mean_brightness > 180:
                    threshold = min(threshold, 140)
                    safe_print(f"[OCR] Светлое изображение обнаружено, скорректирован порог: {threshold}")
                
                binary = np.where(img_array > threshold, 255, 0).astype(np.uint8)
                image = Image.fromarray(binary).convert('RGB')
                safe_print(f"[OCR] Бинаризация применена (порог={threshold})")
            else:
                from PIL import ImageOps
                image = ImageOps.autocontrast(gray, cutoff=5)
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
                image = enhancer.enhance(0.8)
                safe_print(f"[OCR] Уменьшена яркость (было светло: {mean_brightness:.0f})")
            
            if mean_brightness > 180 and std_dev < 40:
                if NUMPY_AVAILABLE:
                    import numpy as np
                    img_array = np.array(image.convert('L'))
                    dark_pixels = np.sum(img_array < 128)
                    total_pixels = img_array.size
                    if dark_pixels < total_pixels * 0.3:
                        img_array = 255 - img_array
                        image = Image.fromarray(img_array).convert('RGB')
                        safe_print(f"[OCR] Инвертировано изображение для темного текста на светлом фоне")
            
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(4.0)
        
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(4.5)
        
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
        
        preprocess_methods = ['auto', 'binary', 'deskew', 'enhance']
        all_results = []
        
        if OCR_AVAILABLE:
            try:
                languages_to_try = ['rus+eng', 'rus', 'eng']
                configs = [
                    r'--oem 3 --psm 8',
                    r'--oem 3 --psm 7',
                    r'--oem 3 --psm 6',
                    r'--oem 3 --psm 13',
                    r'--oem 3 --psm 11',
                    r'--oem 3 --psm 12',
                    r'--oem 3 --psm 10',
                ]
                
                best_text = None
                best_score = 0
                best_method = None
                
                for method in preprocess_methods[:2]:
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
        return None, None
    
    emoji_to_words = {
        '👻': ['призрак', 'ghost', 'привидение', 'дух', 'phantom', 'призр', 'приз'],
        '🐶': ['собака', 'dog', 'пес', 'пёс', 'собак', 'песик', 'собакa', 'соба'],
        '🐰': ['кролик', 'заяц', 'rabbit', 'bunny', 'зайчик', 'крол', 'кроли'],
        '🐇': ['кролик', 'заяц', 'rabbit', 'bunny', 'зайчик', 'крол', 'кроли'],
        '🦊': ['лиса', 'fox', 'лис', 'лисa', 'ли'],
        '⭐': ['звезда', 'star', 'звезд', 'звездочка', 'звезла', 'звезл', 'звез', 'звёзд', 'везда'],
        '🌟': ['звезда', 'star', 'звезд', 'звездочка', 'звезла', 'звезл', 'звез', 'звёзд', 'везда'],
        '💫': ['звезда', 'star', 'звезд', 'звездочка', 'звезла', 'звезл', 'звез', 'звёзд', 'везда'],
        '✨': ['звезда', 'star', 'звезд', 'звездочка', 'звезла', 'звезл', 'звез', 'звёзд', 'везда'],
        '🐻': ['мишка', 'bear', 'медведь', 'медвежонок', 'мишк', 'миш', 'ми'],
        '🤖': ['робот', 'robot', 'робот', 'pogot', 'роб', 'робо'],
        '🐵': ['обезьяна', 'monkey', 'обезьян', 'обезья', 'обезь', 'обез', 'мартышка', 'ape'],
        '🐒': ['обезьяна', 'monkey', 'обезьян', 'обезья', 'обезь', 'обез', 'мартышка', 'ape'],
    }
    
    text_lower = text.lower()
    text_normalized = normalize_ocr_text(text)
    text_normalized_lower = text_normalized.lower()
    
    safe_print(f"[DEBUG extract_word] Ищу слово в тексте: '{text[:200] if len(text) > 200 else text}' (normalized: '{text_normalized_lower[:200] if len(text_normalized_lower) > 200 else text_normalized_lower}')")
    
    for emoji, words in emoji_to_words.items():
        for word in words:
            if len(word) < 2:
                continue
            pattern = r'\b' + re.escape(word) + r'\b'
            if re.search(pattern, text_lower) or re.search(pattern, text_normalized_lower):
                safe_print(f"[DEBUG extract_word] Найдено точное совпадение: '{word}' -> {emoji}")
                return word, emoji
    
    for emoji, words in emoji_to_words.items():
        for word in words:
            if len(word) < 3:
                continue
            pattern = r'\b' + re.escape(word) + r'\w*\b'
            if re.search(pattern, text_lower) or re.search(pattern, text_normalized_lower):
                safe_print(f"[DEBUG extract_word] Найдено частичное совпадение (слово): '{word}' -> {emoji}")
                return word, emoji
    
    text_clean = text_normalized_lower.strip()
    text_clean_letters = re.sub(r'[^\w]', '', text_clean)
    
    ocr_error_fixes = {
        'призр': 'призрак',
        'приз': 'призрак',
        'призра': 'призрак',
        'соб': 'собака',
        'соба': 'собака',
        'собак': 'собака',
        'крол': 'кролик',
        'кроли': 'кролик',
        'кролик': 'кролик',
        'ротик': 'кролик',
        'отик': 'кролик',
        'ролик': 'кролик',
        'зая': 'заяц',
        'зай': 'заяц',
        'заяц': 'заяц',
        'лис': 'лиса',
        'ли': 'лиса',
        'звез': 'звезда',
        'везда': 'звезда',
        'везд': 'звезда',
        'звезд': 'звезда',
        'звезл': 'звезда',
        'звезла': 'звезда',
        'ми': 'мишка',
        'миш': 'мишка',
        'мишк': 'мишка',
        'мi': 'мишка',
        'ми': 'мишка',
        'роб': 'робот',
        'робо': 'робот',
        'обез': 'обезьяна',
        'обезь': 'обезьяна',
        'обезь': 'обезьяна',
        'обезья': 'обезьяна',
        'обезьян': 'обезьяна',
        'обезьяна': 'обезьяна',
        'безьяна': 'обезьяна',
        'езьяна': 'обезьяна',
        'зьяна': 'обезьяна',
        'обезьна': 'обезьяна',
        'обезья': 'обезьяна',
        'обезьян': 'обезьяна',
        'обезян': 'обезьяна',
        'зама': None,
        'ан': None,
        'м': None,
        'нee': None,
        'hee': None,
        'ioe': None,
    }
    
    text_original_clean = re.sub(r'[^\w]', '', text_lower).lower()
    if text_original_clean in ocr_error_fixes:
        fix_word = ocr_error_fixes[text_original_clean]
        if fix_word is None:
            safe_print(f"[DEBUG extract_word] Пропускаю неправильное OCR распознавание: '{text_original_clean}'")
        else:
            for emoji, words in emoji_to_words.items():
                if fix_word in words:
                    safe_print(f"[DEBUG extract_word] Исправление OCR (оригинал) '{text_original_clean}' -> '{fix_word}' -> {emoji}")
                    return fix_word, emoji
    
    text_clean_check = text_clean_letters.lower()
    if text_clean_check in ocr_error_fixes:
        fix_word = ocr_error_fixes[text_clean_check]
        if fix_word is None:
            safe_print(f"[DEBUG extract_word] Пропускаю неправильное OCR распознавание: '{text_clean_check}'")
        else:
            for emoji, words in emoji_to_words.items():
                if fix_word in words:
                    safe_print(f"[DEBUG extract_word] Исправление OCR '{text_clean_check}' -> '{fix_word}' -> {emoji}")
                    return fix_word, emoji
    
    if len(text_clean_letters) >= 2 and len(text_clean_letters) <= 15:
        for emoji, words in emoji_to_words.items():
            for word in words:
                if len(word) < 3:
                    continue
                word_lower = word.lower()
                
                if word_lower.startswith(text_clean_letters):
                    safe_print(f"[DEBUG extract_word] Найдено по началу слова: '{text_clean_letters}' -> '{word}' -> {emoji}")
                    return word, emoji
                
                if word_lower.endswith(text_clean_letters) and len(text_clean_letters) >= 4:
                    safe_print(f"[DEBUG extract_word] Найдено по окончанию слова: '{text_clean_letters}' -> '{word}' -> {emoji}")
                    return word, emoji
                
                if len(text_clean_letters) >= 4 and len(word_lower) >= 4:
                    word_end = word_lower[-len(text_clean_letters):] if len(text_clean_letters) <= len(word_lower) else word_lower
                    text_end = text_clean_letters[-len(word_end):] if len(word_end) <= len(text_clean_letters) else text_clean_letters
                    if word_end == text_end and len(word_end) >= 3:
                        safe_print(f"[DEBUG extract_word] Найдено по совпадению окончания: '{text_clean_letters}' -> '{word}' -> {emoji}")
                        return word, emoji
                
                if text_clean_letters in word_lower and len(text_clean_letters) >= 5:
                    match_start = word_lower.find(text_clean_letters)
                    if match_start >= len(word_lower) - len(text_clean_letters) - 1:
                        safe_print(f"[DEBUG extract_word] Найдено как часть слова (в конце): '{text_clean_letters}' -> '{word}' -> {emoji}")
                        return word, emoji
                
                if len(text_clean_letters) >= 2 and len(word) >= 2:
                    min_len = min(len(text_clean_letters), len(word), 3)
                    if text_clean_letters[:min_len] == word_lower[:min_len]:
                        safe_print(f"[DEBUG extract_word] Найдено по первым {min_len} буквам: '{text_clean_letters}' -> '{word}' -> {emoji}")
                        return word, emoji
    
    if len(text_clean) >= 3 and len(text_clean) <= 6:
        safe_print(f"[DEBUG extract_word] Пробую найти похожее слово для короткого текста: '{text_clean}'")
        
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
                        safe_print(f"[DEBUG extract_word] Исправление OCR '{text_clean}' -> '{fix_word}' -> {emoji}")
                        return fix_word, emoji
        
        if text_clean not in ocr_error_fixes_short:
            for emoji, words in emoji_to_words.items():
                for word in words:
                    if len(word) >= 3 and text_clean[0] == word[0]:
                        if len(text_clean) >= 2 and len(word) >= 2:
                            min_match = min(3, len(text_clean), len(word))
                            if text_clean[:min_match] == word[:min_match]:
                                safe_print(f"[DEBUG extract_word] Найдено по похожести: '{text_clean}' -> '{word}' -> {emoji}")
                                return word, emoji
    
    safe_print(f"[DEBUG extract_word] Не найдено соответствие для текста: '{text}'")
    return None, None


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
