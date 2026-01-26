import asyncio
import os
import io
import sys
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, FloodWaitError
from PIL import Image

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

from . import config
from .utils import safe_print, wait_for_keypress, print_info, print_success, print_error, print_warning, console, display_manager
from .limit import (
    check_limit_message, save_limit_cooldown,
    get_remaining_cooldown, wait_for_cooldown
)
from .captcha import check_captcha
from .ocr import (
    extract_text_from_image, extract_word_from_captcha,
    find_matching_button, normalize_ocr_text, preprocess_image,
    NUMPY_AVAILABLE
)
try:
    import numpy as np
except ImportError:
    np = None

class FunStatFarm:
    def __init__(self):
        self.client = None
        self.running = False
        self.source_bot = config.SOURCE_BOT
        self.captcha_bot = config.CAPTCHA_BOT
        self.target_bot = config.TARGET_BOT
        self.interval = config.INTERVAL
        self.paused = False
        self.limit_reached = False

    async def start(self):
        self.client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
        
        session_file = f"{config.SESSION_NAME}"
        session_exists = os.path.exists(session_file)
        
        safe_print("[TELEGRAM] Подключение к Telegram...")
        
        need_auth = False
        
        if session_exists:
            safe_print(f"[FILE] Найден файл сессии: {session_file}")
            safe_print("[WAIT] Пытаюсь подключиться используя существующую сессию...")
            
            try:
                await self.client.connect()
                
                if await self.client.is_user_authorized():
                    safe_print("[OK] Успешное подключение по существующей сессии!")
                    safe_print("=" * 50)
                    need_auth = False
                else:
                    safe_print("[ERROR] Сессия недействительна или устарела")
                    await self.client.disconnect()
                    need_auth = True
            except Exception as e:
                safe_print(f"[ERROR] Ошибка при подключении: {e}")
                safe_print("[AUTH] Потребуется новая авторизация")
                need_auth = True
        else:
            safe_print(f"[FILE] Файл сессии не найден: {session_file}")
            safe_print("[AUTH] Потребуется новая авторизация")
            need_auth = True
        
        if need_auth:
            await asyncio.sleep(1)
            await self._perform_auth()
        
        from .utils import print_banner, print_info, print_success
        print_banner()
        
        print_info("Проверка OCR библиотек...")
        try:
            import pytesseract
            try:
                version = pytesseract.get_tesseract_version()
                print_success(f"Tesseract доступен (версия: {version})")
            except Exception as e:
                error_msg = str(e).lower()
                if 'tesseract not found' in error_msg or 'not found' in error_msg:
                    print_info("Tesseract не найден в PATH")
                else:
                    print_info(f"Tesseract не работает: {e}")
        except ImportError:
            print_info("pytesseract не установлен")
        
        try:
            import easyocr
            print_success("EasyOCR доступен")
        except ImportError:
            print_info("EasyOCR не установлен")
        
        safe_print("=" * 50)
        safe_print("[START] FunStat Farm - ОБЪЕДИНЕННАЯ ВЕРСИЯ")
        safe_print(f"[SOURCE] Источник: {self.source_bot}")
        safe_print(f"[TARGET] Цель: {self.target_bot}")
        safe_print(f"[INTERVAL] Интервал: {self.interval} сек")
        safe_print("=" * 50)
        safe_print("[AUTO] АВТОЗАПУСК...")
        safe_print("=" * 50)

        remaining = get_remaining_cooldown()
        if remaining > 0:
            safe_print(f"[LIMIT] Обнаружен активный кулдаун")
            await wait_for_cooldown()

        await asyncio.sleep(2)
        await self.start_farm()

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await self.stop_farm()
            await self.client.disconnect()
            safe_print("\n[STOP] Остановлено")

    async def _perform_auth(self):
        try:
            if not self.client.is_connected():
                await self.client.connect()
        except:
            await self.client.connect()
        
        display_manager.pause_for_input()
        os.system('clear' if os.name != 'nt' else 'cls')
        sys.stdout.flush()
        
        print("\n" + "="*75)
        print("                     FunStat Farm")
        print("="*75)
        print("\n[!] ТРЕБУЕТСЯ АВТОРИЗАЦИЯ")
        print("="*75 + "\n")
        sys.stdout.flush()
        
        phone = None
        while not phone or not phone.strip():
            try:
                phone = input("Введите номер телефона (формат: +1234567890): ").strip()
                if not phone:
                    print("\n[!] Ошибка: номер телефона не может быть пустым\n")
                    sys.stdout.flush()
            except (EOFError, KeyboardInterrupt):
                display_manager.resume_after_input()
                raise
        
        print("\n[WAIT] Отправляю запрос на код...\n")
        sys.stdout.flush()
        
        try:
            sent_code = await self.client.send_code_request(phone)
            
            code_type = str(sent_code.type)
            print(f"[OK] Код отправлен! Метод доставки: {code_type}\n")
            
            if "App" in code_type:
                print("[IMPORTANT] ВАЖНО: Код придет через Telegram приложение на вашем телефоне!")
                print("[TELEGRAM] Откройте Telegram на телефоне и найдите уведомление с кодом")
                print("[MESSAGE] Код придет как сообщение от Telegram или как push-уведомление")
                print("[SEARCH] Проверьте список чатов в Telegram - там должно быть сообщение с кодом\n")
            else:
                print("[TELEGRAM] Код должен прийти по SMS на телефон\n")
            
            print("[WAIT] Ожидаю код... (проверьте Telegram на телефоне)")
            print("=" * 50 + "\n")
            sys.stdout.flush()
            
            code = None
            while not code or not code.strip():
                try:
                    code = input("Введите код подтверждения (5 цифр): ").strip()
                    if not code:
                        print("\n[!] Ошибка: код не может быть пустым\n")
                        sys.stdout.flush()
                except (EOFError, KeyboardInterrupt):
                    display_manager.resume_after_input()
                    raise
            
            try:
                await self.client.sign_in(phone, code)
                print("\n[OK] Авторизация успешна!\n")
                sys.stdout.flush()
                await asyncio.sleep(1)
                
                display_manager.resume_after_input()
                from funstat.utils import print_banner
                print_banner()
                await asyncio.sleep(0.3)
            except SessionPasswordNeededError:
                print("\n[!] Требуется пароль 2FA\n")
                sys.stdout.flush()
                
                password = None
                while not password or not password.strip():
                    try:
                        password = input("Введите пароль двухфакторной аутентификации: ").strip()
                        if not password:
                            print("\n[!] Ошибка: пароль не может быть пустым\n")
                            sys.stdout.flush()
                    except (EOFError, KeyboardInterrupt):
                        display_manager.resume_after_input()
                        raise
                
                await self.client.sign_in(password=password)
                print("\n[OK] Авторизация успешна!\n")
                sys.stdout.flush()
                await asyncio.sleep(1)
                
                display_manager.resume_after_input()
                from funstat.utils import print_banner
                print_banner()
                await asyncio.sleep(0.3)
            except PhoneCodeInvalidError:
                print("\n[ERROR] Неверный код! Попробуйте еще раз.\n")
                sys.stdout.flush()
                display_manager.resume_after_input()
                raise
            except Exception as e:
                print(f"\n[ERROR] Ошибка при вводе кода: {e}\n")
                sys.stdout.flush()
                display_manager.resume_after_input()
                raise
                
        except FloodWaitError as e:
            print(f"\n[ERROR] Слишком много попыток. Подождите {e.seconds} секунд.\n")
            sys.stdout.flush()
            display_manager.resume_after_input()
            raise
        except Exception as e:
            print(f"\n[ERROR] Ошибка авторизации: {e}\n")
            sys.stdout.flush()
            display_manager.resume_after_input()
            raise

    async def start_farm(self):
        if self.running:
            return

        self.running = True

        safe_print("\n[FARM] ФАРМ ЗАПУЩЕН!")
        safe_print("=" * 50)
        safe_print("[INFO] КАЖДЫЙ ЦИКЛ: Пересылает сообщение + нажимает кнопку 'change'")
        safe_print("=" * 50)

        asyncio.create_task(self.farm_loop())

    async def stop_farm(self):
        if not self.running:
            return

        self.running = False
        safe_print("\n[STOP] ФАРМ ОСТАНОВЛЕН")

    async def copy_to_target(self, msg):
        try:
            if msg.media:
                await self.client.send_file(
                    self.target_bot,
                    file=msg.media,
                    caption=msg.text or ""
                )
                return True
            elif msg.text:
                await self.client.send_message(
                    self.target_bot,
                    message=msg.text
                )
                return True
        except Exception as e:
            safe_print(f"[ERROR] Ошибка: {e}")
            return False

    async def solve_captcha(self, msg):
        if not msg.buttons:
            safe_print("[CAPTCHA] Нет кнопок в сообщении")
            return False
        
        safe_print("[CAPTCHA] Пытаюсь автоматически решить капчу...")
        
        image_data = None
        if msg.media:
            try:
                safe_print("[CAPTCHA] Загружаю изображение капчи...")
                image_data = await self.client.download_media(msg.media, file=bytes)
                if image_data:
                    safe_print(f"[CAPTCHA] Изображение загружено ({len(image_data)} байт)")
            except Exception as e:
                safe_print(f"[CAPTCHA] Ошибка загрузки изображения: {e}")
        
        if image_data:
            word, target_emoji = await self._extract_word_from_captcha(None, image_data)
        else:
            word, target_emoji = await self._extract_word_from_captcha(msg.text, None)
        
        safe_print(f"[CAPTCHA] Результат: слово='{word}', эмодзи='{target_emoji}'")
        
        if not word or not target_emoji and image_data:
            safe_print("[CAPTCHA] Первая попытка OCR не удалась, пробую еще раз с другими настройками...")
            try:
                image_orig = Image.open(io.BytesIO(image_data))
                if OCR_AVAILABLE:
                    for lang in ['rus', 'eng', 'rus+eng']:
                        for psm in [8, 7, 6, 10, 13]:
                            try:
                                config = f'--oem 3 --psm {psm}'
                                ocr_text_retry = pytesseract.image_to_string(image_orig, lang=lang, config=config)
                                ocr_text_retry = ocr_text_retry.strip()
                                if ocr_text_retry and len(ocr_text_retry) >= 2:
                                    safe_print(f"[CAPTCHA] Повторная попытка OCR (lang={lang}, psm={psm}): '{ocr_text_retry}'")
                                    ocr_text_retry = normalize_ocr_text(ocr_text_retry)
                                    word_retry, emoji_retry = extract_word_from_captcha(ocr_text_retry, None)
                                    if word_retry and emoji_retry:
                                        safe_print(f"[CAPTCHA] Повторная попытка успешна: '{word_retry}' -> {emoji_retry}")
                                        word, target_emoji = word_retry, emoji_retry
                                        break
                            except:
                                continue
                        if word and target_emoji:
                            break
            except Exception as e:
                safe_print(f"[CAPTCHA] Ошибка повторной попытки OCR: {e}")
        
        if not word or not target_emoji:
            safe_print("[CAPTCHA] Не удалось определить слово из капчи")
            safe_print("[CAPTCHA] Показываю доступные кнопки:")
            for row_idx, row in enumerate(msg.buttons):
                for btn_idx, btn in enumerate(row):
                    safe_print(f"[CAPTCHA]   [{row_idx}][{btn_idx}]: {btn.text}")
            
            try:
                display_manager.pause_for_input()
                
                console.print("\n")
                user_input = input("Введите слово или номер кнопки: ").strip()
                
                display_manager.resume_after_input()
                
                if ' ' in user_input and user_input.replace(' ', '').isdigit():
                    row_idx, btn_idx = map(int, user_input.split())
                    await msg.click(row_idx, btn_idx)
                    safe_print(f"[CAPTCHA] Кнопка [{row_idx}][{btn_idx}] нажата!")
                    await asyncio.sleep(2)
                    return True
                elif user_input:
                    word, target_emoji = extract_word_from_captcha(user_input)
                    if not word or not target_emoji:
                        safe_print("[CAPTCHA] Слово не найдено в словаре")
                        return False
                else:
                    return False
            except Exception as e:
                display_manager.resume_after_input()
                safe_print(f"[CAPTCHA] Ошибка ручного ввода: {e}")
                return False
        
        safe_print(f"[CAPTCHA] Ищу кнопку с эмодзи '{target_emoji}' среди {len(msg.buttons)} строк кнопок...")
        matching_button = find_matching_button(msg.buttons, target_emoji)
        
        if not matching_button:
            safe_print(f"[CAPTCHA] Кнопка с эмодзи '{target_emoji}' не найдена")
            safe_print("[CAPTCHA] Показываю все доступные кнопки для отладки:")
            for row_idx, row in enumerate(msg.buttons):
                for btn_idx, btn in enumerate(row):
                    btn_text_repr = repr(btn.text) if btn.text else "''"
                    btn_text_hex = ' '.join(f'U+{ord(c):04X}' for c in (btn.text or ''))
                    safe_print(f"[CAPTCHA]   [{row_idx}][{btn_idx}]: {btn_text_repr} (Unicode: {btn_text_hex})")
            return False
        
        matching_row = None
        matching_col = None
        for row_idx, row in enumerate(msg.buttons):
            for btn_idx, btn in enumerate(row):
                if btn == matching_button:
                    matching_row = row_idx
                    matching_col = btn_idx
                    break
            if matching_row is not None:
                break
        
        try:
            await msg.click(matching_row, matching_col)
            safe_print(f"[CAPTCHA] Кнопка нажата [{matching_row}][{matching_col}]")
            await asyncio.sleep(2)
            return True
        except Exception as e:
            safe_print(f"[CAPTCHA] Ошибка при нажатии кнопки: {e}")
            return False

    async def _extract_word_from_captcha(self, text, image_data=None):
        if image_data:
            safe_print("[CAPTCHA] Распознаю текст с изображения капчи...")
            ocr_text = await extract_text_from_image(image_data)
            if ocr_text:
                safe_print(f"[CAPTCHA] OCR распознал: '{ocr_text}'")
                word, emoji = extract_word_from_captcha(ocr_text, None)
                
                if not word and EASYOCR_AVAILABLE:
                    safe_print("[CAPTCHA] Tesseract не распознал правильно, пробую EasyOCR...")
                    try:
                        if not hasattr(extract_text_from_image, 'reader'):
                            safe_print("[OCR] Инициализирую EasyOCR reader...")
                            import ssl
                            ssl._create_default_https_context = ssl._create_unverified_context
                            extract_text_from_image.reader = easyocr.Reader(['ru', 'en'], gpu=False)
                        
                        image = Image.open(io.BytesIO(image_data))
                        image_processed = preprocess_image(image)
                        
                        if NUMPY_AVAILABLE:
                            img_array = np.array(image_processed)
                            results = extract_text_from_image.reader.readtext(img_array)
                        else:
                            import tempfile
                            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                                image_processed.save(tmp_file.name)
                                tmp_path = tmp_file.name
                            try:
                                results = extract_text_from_image.reader.readtext(tmp_path)
                            finally:
                                try:
                                    os.unlink(tmp_path)
                                except:
                                    pass
                        
                        if results:
                            for result in sorted(results, key=lambda x: x[2] if len(x) > 2 else 0, reverse=True):
                                easyocr_text = normalize_ocr_text(result[1])
                                safe_print(f"[CAPTCHA] EasyOCR распознал: '{easyocr_text}' (уверенность: {result[2] if len(result) > 2 else 0:.2f})")
                                word, emoji = extract_word_from_captcha(easyocr_text, None)
                                if word and emoji:
                                    safe_print(f"[CAPTCHA] EasyOCR успешно распознал: '{word}' -> {emoji}")
                                    return word, emoji
                    except Exception as e:
                        safe_print(f"[CAPTCHA] EasyOCR ошибка: {e}")
                
                return word, emoji
        
        if text:
            text_lower = text.lower()
            menu_words = ['старт', 'start', 'меню', 'menu', 'поиск', 'search', 'скрыться', 'hide']
            if any(word in text_lower for word in menu_words) and not image_data:
                return None, None
            return extract_word_from_captcha(text, None)
        
        return None, None

    async def handle_captcha(self, msg):
        safe_print("\n" + "=" * 60)
        safe_print("[CAPTCHA] !!! ОБНАРУЖЕНА КАПЧА !!!")
        safe_print("=" * 60)
        safe_print(f"[CAPTCHA] Текст сообщения: {msg.text[:200] if msg.text else 'Нет текста'}")
        
        if msg.text:
            text_lower = msg.text.lower()
            text_normalized_check = text_lower
            quick_replacements = {'k': 'к', 'α': 'а', 'π': 'п', 'ρ': 'р', 'e': 'е', 'o': 'о', '℮': 'е', 'ο': 'о'}
            for old, new in quick_replacements.items():
                text_normalized_check = text_normalized_check.replace(old, new)
            
            solved_phrases = [
                'капча решена', 'капча пройдена', 'kаπча ρeшeна', 'kаπча решена',
                'kаπчα решена', 'kаπчα реш℮нα', 'kаπчα реш℮на',
                'добро пожаловать', 'добро пожαловать', 'добро пожαлoвαть', 'welcome'
            ]
            if any(phrase in text_lower for phrase in solved_phrases) or \
               any(phrase in text_normalized_check for phrase in ['капча решена', 'капча пройдена', 'добро пожаловать']):
                safe_print("[CAPTCHA] ⚠️ Это сообщение о РЕШЕНИИ капчи, а не сама капча!")
                safe_print("[CAPTCHA] Продолжаю работу автоматически...")
                safe_print("=" * 60 + "\n")
                return
        
        solved = await self.solve_captcha(msg)
        
        if solved:
            safe_print("[CAPTCHA] Автоматическое решение успешно!")
            safe_print("=" * 60 + "\n")
            return
        
        self.paused = True
        safe_print("[CAPTCHA] Автоматическое решение не удалось.")
        safe_print("[CAPTCHA] Скрипт приостановлен.")
        safe_print("[CAPTCHA] Пожалуйста, пройдите капчу в Telegram вручную.")
        safe_print("=" * 60)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, wait_for_keypress, 
                                   "[CAPTCHA] После прохождения капчи нажмите любую клавишу для продолжения...")
        
        safe_print("[CAPTCHA] Продолжаю работу...")
        safe_print("=" * 60 + "\n")
        self.paused = False

    async def farm_loop(self):
        safe_print("[WAIT] Начинаю...")

        counter = 0

        while self.running:
            try:
                if self.paused:
                    await asyncio.sleep(1)
                    continue
                
                counter += 1
                safe_print(f"\n[CYCLE] ЦИКЛ #{counter}")

                try:
                    captcha_messages = await self.client.get_messages(self.captcha_bot, limit=10)
                    if captcha_messages:
                        for captcha_msg in captcha_messages:
                            has_media_captcha = captcha_msg.media is not None
                            has_buttons_captcha = captcha_msg.buttons is not None and len(captcha_msg.buttons) > 0
                            
                            if captcha_msg.text and check_captcha(captcha_msg.text, has_media_captcha, has_buttons_captcha):
                                safe_print("[CAPTCHA] !!! ОБНАРУЖЕНА КАПЧА ОТ БОТА КАПЧИ !!!")
                                await self.handle_captcha(captcha_msg)
                                continue
                            
                            if not captcha_msg.text and has_media_captcha and has_buttons_captcha:
                                animal_emojis = ['🐶', '🐱', '🐰', '👻', '🤖', '🐻', '🐷', '🐸', '🐵', 
                                                '🐔', '🐧', '🐦', '🦆', '🦅', '🦉', '🐴', '🦄', '🐝', 
                                                '🦋', '🐞', '🐛', '🦗', '🐜', '🐢', '🐍', '🦎', '🐟',
                                                '⭐', '🌟', '💫', '✨', '🐒', '🦊']
                                has_emoji_buttons = any(
                                    any(any(emoji in btn.text for emoji in animal_emojis) for btn in row)
                                    for row in captcha_msg.buttons
                                )
                                if has_emoji_buttons:
                                    safe_print("[CAPTCHA] !!! ОБНАРУЖЕНА КАПЧА ПО ЭМОДЗИ !!!")
                                    await self.handle_captcha(captcha_msg)
                                    continue
                except Exception as e:
                    safe_print(f"[ERROR] Ошибка проверки капчи: {e}")

                messages = await self.client.get_messages(self.source_bot, limit=1)

                if not messages:
                    safe_print("[NO_MSG] Нет сообщений, отправляю /rand...")
                    await self.client.send_message(self.source_bot, "/rand")
                    await asyncio.sleep(3)
                    continue

                msg = messages[0]

                has_media = msg.media is not None
                has_buttons = msg.buttons is not None and len(msg.buttons) > 0
                
                if msg.text and check_captcha(msg.text, has_media, has_buttons):
                    safe_print("[CAPTCHA] !!! ОБНАРУЖЕНА КАПЧА !!!")
                    await self.handle_captcha(msg)
                    continue
                
                if not msg.text and has_media and has_buttons:
                    animal_emojis = ['🐶', '🐱', '🐰', '👻', '🤖', '🐻', '🐷', '🐸', '🐵', 
                                    '🐔', '🐧', '🐦', '🦆', '🦅', '🦉', '🐴', '🦄', '🐝', 
                                    '🦋', '🐞', '🐛', '🦗', '🐜', '🐢', '🐍', '🦎', '🐟',
                                    '⭐', '🌟', '💫', '✨', '🐒', '🦊']
                    has_emoji_buttons = any(
                        any(any(emoji in btn.text for emoji in animal_emojis) for btn in row)
                        for row in msg.buttons
                    )
                    if has_emoji_buttons:
                        safe_print("[CAPTCHA] !!! ОБНАРУЖЕНА КАПЧА ПО МЕДИА + ЭМОДЗИ !!!")
                        await self.handle_captcha(msg)
                        continue

                if msg.text and check_limit_message(msg.text):
                    safe_print("\n" + "=" * 60)
                    safe_print("[LIMIT] !!! ДОСТИГНУТ ЛИМИТ !!!")
                    safe_print("=" * 60)
                    safe_print(f"[LIMIT] Сообщение: {msg.text[:200]}")
                    safe_print(f"[LIMIT] Лимит: 250 ссылок в день")
                    safe_print(f"[LIMIT] Скрипт переходит в режим ожидания на {config.COOLDOWN_HOURS} часов")
                    safe_print("=" * 60)
                    
                    save_limit_cooldown()
                    await self.stop_farm()
                    self.limit_reached = True
                    await wait_for_cooldown()
                    
                    safe_print("[LIMIT] Перезапускаю фарм...")
                    await asyncio.sleep(2)
                    await self.start_farm()
                    continue

                safe_print(f"[TARGET] Пересылаю ID {msg.id}...")
                if await self.copy_to_target(msg):
                    safe_print("[OK] Переслано!")
                else:
                    safe_print("[ERROR] Не удалось переслать")

                if msg.buttons:
                    change_button_found = False
                    change_row = None
                    change_col = None
                    
                    for row_idx, row in enumerate(msg.buttons):
                        for btn_idx, btn in enumerate(row):
                            if 'change' in btn.text.lower():
                                change_button_found = True
                                change_row = row_idx
                                change_col = btn_idx
                                safe_print(f"[BUTTON] Найдена кнопка 'change': {btn.text} (row={row_idx}, col={btn_idx})")
                                break
                        if change_button_found:
                            break
                    
                    if change_button_found:
                        try:
                            await msg.click(change_row, change_col)
                            safe_print("[OK] Кнопка 'change' нажата")
                        except Exception as e:
                            safe_print(f"[ERROR] Ошибка нажатия: {e}")
                    else:
                        safe_print("[INFO] Кнопка 'change' не найдена")

                for i in range(self.interval, 0, -1):
                    if not self.running:
                        return
                    if self.paused:
                        break
                    safe_print(f"\r[WAIT] Следующий цикл через {i} сек...", end="")
                    await asyncio.sleep(1)
                safe_print()

            except Exception as e:
                safe_print(f"\n[WARN] Ошибка: {e}")
                await asyncio.sleep(5)
