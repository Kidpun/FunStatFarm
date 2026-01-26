import os
from datetime import datetime, timedelta
from .config import LIMIT_COOLDOWN_FILE, COOLDOWN_HOURS
from .utils import safe_print


def check_limit_message(text):
    if not text:
        return False

    normalized_text = text
    replacements = {
        'τ': 't',
        'η': 'n',
        'ρ': 'r',
        'е': 'e',
        'қ': 'k',
        'к': 'k',
        '℮': 'e',
        'γ': 'y',
        'ⅼ': 'l',
        'ѕ': 's',
        'ł': 'l',
        'α': 'a',
    }
    for greek, latin in replacements.items():
        normalized_text = normalized_text.replace(greek, latin)

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


    if 'limit' in text_lower or 'limi' in text_lower:
        if '250' in text:
            if ('link' in text_lower or 'per day' in text_lower or 'per da' in text_lower):
                return True

    if 'лимит' in original_lower:
        if ('250' in text or
            'достигнут' in original_lower or
            'превышен' in original_lower or
            'достиг' in original_lower):
            return True

    if '250' in text:
        if ('link' in text_lower or 'ссылок' in original_lower):
            if ('per day' in text_lower or 'в день' in original_lower or 'per da' in text_lower):
                return True

    return False


def save_limit_cooldown():
    try:
        with open(LIMIT_COOLDOWN_FILE, 'w') as f:
            f.write(datetime.now().isoformat())
        safe_print(f"[LIMIT] Время кулдауна сохранено")
    except Exception as e:
        safe_print(f"[LIMIT] Ошибка сохранения кулдауна: {e}")


def get_remaining_cooldown():
    try:
        if not os.path.exists(LIMIT_COOLDOWN_FILE):
            return 0

        with open(LIMIT_COOLDOWN_FILE, 'r') as f:
            cooldown_start_str = f.read().strip()

        cooldown_start = datetime.fromisoformat(cooldown_start_str)
        cooldown_end = cooldown_start + timedelta(hours=COOLDOWN_HOURS)
        now = datetime.now()

        if now >= cooldown_end:
            os.remove(LIMIT_COOLDOWN_FILE)
            return 0

        remaining = (cooldown_end - now).total_seconds()
        return remaining
    except Exception as e:
        safe_print(f"[LIMIT] Ошибка чтения кулдауна: {e}")
        return 0


async def wait_for_cooldown():
    import asyncio

    remaining = get_remaining_cooldown()

    if remaining <= 0:
        return

    safe_print("\n" + "=" * 60)
    safe_print("[LIMIT] ⏸ КУЛДАУН АКТИВЕН")
    safe_print("=" * 60)
    safe_print(f"[LIMIT] Ожидание {COOLDOWN_HOURS} часов...")
    safe_print("=" * 60)

    while remaining > 0:
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        secs = int(remaining % 60)

        safe_print(f"\r[LIMIT] Осталось: {hours:02d}:{minutes:02d}:{secs:02d} (ч:м:с)", end="")

        await asyncio.sleep(1)
        remaining = get_remaining_cooldown()

    safe_print("\n[LIMIT] ✅ Кулдаун закончился! Продолжаю работу...")
    safe_print("=" * 60 + "\n")
