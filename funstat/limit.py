import asyncio
import re
import unicodedata
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

from .utils import safe_print

MOSCOW_TZ = 'Europe/Moscow'


def normalize_unicode_text(text):
    if not text:
        return ""
    
    text = unicodedata.normalize('NFKD', text)
    
    replacements = {
        'τ': 't', 'Τ': 'T',
        'η': 'n', 'Η': 'N',
        'ρ': 'p', 'Ρ': 'P',
        'е': 'e', 'Е': 'E',
        'қ': 'k', 'Қ': 'K',
        'к': 'k', 'К': 'K',
        '℮': 'e', 'ℇ': 'E',
        'γ': 'y', 'Γ': 'Y',
        'ⅼ': 'l', 'Ⅼ': 'L',
        'ѕ': 's', 'Ѕ': 'S',
        'ł': 'l', 'Ł': 'L',
        'α': 'a', 'Α': 'A',
        'ⅰ': 'i', 'Ⅰ': 'I',
        'ⅽ': 'c', 'Ⅽ': 'C',
        'ⅾ': 'd', 'Ⅾ': 'D',
        'ⅿ': 'm', 'Ⅿ': 'M',
        'ⅴ': 'v', 'Ⅴ': 'V',
        'ⅹ': 'x', 'Ⅹ': 'X',
    }
    
    for unicode_char, latin_char in replacements.items():
        text = text.replace(unicode_char, latin_char)
    
    text = re.sub(r'[\u200B-\u200D\uFEFF\u00A0\u2000-\u200A\u202F\u205F\u3164\u1160\u115F\u180E\u2060-\u206F\u034F\u200C\u200D]', '', text)
    
    text = re.sub(r'[ㅤ\u200B-\u200D\uFEFF\u3164\u1160\u115F\u180E\u2060-\u206F\u034F\u200C\u200D]', '', text)
    
    text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C' or char in '\n\r\t')
    
    text = text.strip()
    
    return text


def check_limit_message(text):
    if not text:
        return False
    
    normalized_text = normalize_unicode_text(text)
    text_lower = normalized_text.lower()
    original_lower = text.lower()
    
    if 't.me/' in text or 'http' in text or 'https' in text:
        if ('limit' in text_lower or 'лимит' in original_lower) and '250' in text:
            return True
        return False
    
    if any(word in original_lower for word in ['подписчик', 'канал', 'чат']):
        if ('limit' in text_lower or 'лимит' in original_lower) and '250' in text:
            return True
        return False
    
    limit_patterns = [
        r'limit.*250.*link',
        r'limit.*250.*per.*day',
        r'limit.*250.*per.*da',
        r'250.*link.*per.*day',
        r'250.*link.*per.*da',
        r'limi.*250.*link',
        r'limi.*250.*per.*day',
        r'limi.*250.*per.*da',
        r'limi.*250.*lin',
        r'limi.*250.*liη',
        r'limi.*250.*liк',
        r'250.*lin.*per',
        r'250.*liη.*per',
        r'250.*liк.*per',
    ]
    
    for pattern in limit_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL):
            return True
    
    if 'limit' in text_lower or 'limi' in text_lower:
        if '250' in text:
            if ('link' in text_lower or 'per day' in text_lower or 'per da' in text_lower or 'links' in text_lower):
                return True
    
    if 'лимит' in original_lower:
        if ('250' in text or 
            'достигнут' in original_lower or 
            'превышен' in original_lower or
            'достиг' in original_lower):
            return True
    
    if '250' in text:
        if ('link' in text_lower or 'links' in text_lower or 'ссылок' in original_lower):
            if ('per day' in text_lower or 'в день' in original_lower or 'per da' in text_lower):
                return True
    
    if '250' in normalized_text and ('link' in text_lower or 'links' in text_lower):
        if 'per' in text_lower and ('day' in text_lower or 'da' in text_lower):
            return True
    
    if '250' in text and ('limit' in text_lower or 'limi' in text_lower):
        return True
    
    if '250' in normalized_text and ('limit' in text_lower or 'limi' in text_lower):
        return True
    
    if '250' in text:
        normalized_lower = normalized_text.lower()
        if ('limit' in normalized_lower or 'limi' in normalized_lower):
            if ('link' in normalized_lower or 'lin' in normalized_lower or 'per' in normalized_lower):
                return True
    
    return False


def get_seconds_until_midnight_moscow():
    """Секунд до следующего 00:00 по Москве."""
    if ZoneInfo is None:
        return 0
    tz = ZoneInfo(MOSCOW_TZ)
    now = datetime.now(tz)
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if now >= today_midnight:
        next_midnight = today_midnight + timedelta(days=1)
    else:
        next_midnight = today_midnight
    return max(0, (next_midnight - now).total_seconds())


async def wait_until_midnight_moscow():
    """Ждёт до 00:00 по Москве, показывает обратный отсчёт."""
    remaining = get_seconds_until_midnight_moscow()
    if remaining <= 0:
        return
    safe_print("\n" + "=" * 60)
    safe_print("[LIMIT] ⏸ ОЖИДАНИЕ 00:00 МОСКВА")
    safe_print("=" * 60)
    safe_print("[LIMIT] Лимит сбрасывается каждый день в 00:00 по Москве")
    safe_print("=" * 60)
    while remaining > 0:
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        secs = int(remaining % 60)
        safe_print(f"\r[LIMIT] До 00:00 МСК: {hours:02d}:{minutes:02d}:{secs:02d} (ч:м:с)", end="")
        await asyncio.sleep(1)
        remaining = get_seconds_until_midnight_moscow()
    safe_print("\n[LIMIT] ✅ 00:00 МСК — продолжаю...")
    safe_print("=" * 60 + "\n")
