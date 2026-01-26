from .utils import safe_print


def check_captcha(text, has_media=False, has_buttons=False):
    if not text:
        if has_media and has_buttons:
            return True
        return False
    
    text_lower_quick = text.lower()
    solved_phrases = [
        'капча решена', 'капча пройдена', 'kаπча ρeшeна', 'kаπча решена',
        'kаπчα решена', 'kаπчα реш℮нα', 'kаπчα реш℮на', 'kаπчα решена',
        'добро пожаловать', 'добро пожαловать', 'добро пожαлoвαть', 'welcome',
        'решен', 'решена', 'реш℮нα', 'реш℮на', 'пройден', 'пройдена'
    ]
    for phrase in solved_phrases:
        if phrase in text_lower_quick:
            return False
    
    invisible_chars = ['ㅤ', '\u200B', '\u200C', '\u200D', '\uFEFF', '\u00A0', '\u3164']
    text_cleaned = text
    for char in invisible_chars:
        text_cleaned = text_cleaned.replace(char, ' ')
    text_cleaned = text_cleaned.strip()
    text_cleaned = ' '.join(text_cleaned.split())
    
    text_lower_quick = text_cleaned.lower()
    profile_indicators = [
        'id=', 'id:', 'username', 'имена', 'профиль', 'статистик', 'сообщени', 
        'групп', 'канал', 'репутаци', 'знаком', 'реакци', 'подарк', 'частот',
        'анализ', 'следовать', 'поделиться', 'профиль', 'статистики нет',
        'не замечен в чатах', 'замечен в чатах', 'userηαmеs', 'именα',
        't.me/', 'moviesasylumm', 'кракен', 'майнкρафт', 'сезон', 'смотреть'
    ]
    
    if 't.me/' in text_cleaned:
        has_profile_content = any(indicator in text_lower_quick for indicator in profile_indicators)
        if has_profile_content:
            safe_print(f"[DEBUG check_captcha] Сообщение со ссылкой t.me/ и признаками профиля - НЕ капча")
            return False
    
    if '[WARN]' in text_cleaned or '[WARN' in text_cleaned:
        has_profile_content = any(indicator in text_lower_quick for indicator in profile_indicators)
        if has_profile_content:
            safe_print(f"[DEBUG check_captcha] [WARN] найдено, но это сообщение о профиле/статистике - НЕ капча")
            return False
    
    if '⚠' in text or '⚠️' in text:
        original_lower_before_norm = text_cleaned.lower()
        
        captcha_variants = [
            'капча', 'kаπча', 'kαπча', 'kаπчα', 'kαπчα', 'kапча', 'kαпча',
            'капчα', 'kапчα', 'kαпчα', 'каπча', 'каπчα', 'kаπча', 'kαπча'
        ]
        
        has_captcha_word = any(variant in original_lower_before_norm for variant in captcha_variants)
        
        instruction_phrases = [
            'нажми', 'нажми', 'кнопк', 'кнопку', 'кноπkу', 'kнoπkγ', 'kноπку',
            'знаком', 'значком', 'знαчқοм', 'значком', 'значком',
            'картинк', 'картинку', 'kαρтинкγ', 'қαртинқγ', 'картинку',
            'похож', 'похожим', 'πоxoжим', 'похожим', 'нα', 'на'
        ]
        
        has_instruction = any(phrase in original_lower_before_norm for phrase in instruction_phrases)
        
        safe_print(f"[DEBUG check_captcha] Найдено ⚠️ в тексте")
        safe_print(f"[DEBUG check_captcha] has_captcha_word={has_captcha_word}, has_instruction={has_instruction}, has_media={has_media}, has_buttons={has_buttons}")
        safe_print(f"[DEBUG check_captcha] original_lower_before_norm: {original_lower_before_norm[:100]}")
        
        if has_captcha_word or has_instruction:
            safe_print(f"[DEBUG check_captcha] Найдено ⚠️ + капча/инструкция - ЭТО КАПЧА!")
            return True
            
        if has_media or has_buttons:
            has_profile_content = any(indicator in text_lower_quick for indicator in profile_indicators)
            if has_profile_content:
                safe_print(f"[DEBUG check_captcha] Найдено ⚠️ + медиа/кнопки, но это сообщение о профиле - НЕ капча")
                return False
            safe_print(f"[DEBUG check_captcha] Найдено ⚠️ + медиа/кнопки - ЭТО КАПЧА!")
            return True
    
    replacements = {
        'α': 'а', 'Α': 'А', 'π': 'п', 'Π': 'П', 'κ': 'к', 'Κ': 'К',
        'γ': 'г', 'Γ': 'Г', 'k': 'к', 'K': 'К', 'c': 'с', 'C': 'С',
        'o': 'о', 'O': 'О', 'x': 'х', 'X': 'Х', 'a': 'а', 'A': 'А',
        'e': 'е', 'E': 'Е', 'p': 'р', 'P': 'Р', 'y': 'у', 'Y': 'У',
        'm': 'м', 'M': 'М', 'h': 'н', 'H': 'Н', 'қ': 'к', 'ο': 'о',
        'ρ': 'р', 'Ρ': 'Р',
    }
    
    text_normalized = text_cleaned
    for old_char, new_char in replacements.items():
        text_normalized = text_normalized.replace(old_char, new_char)
    
    text_lower = text_normalized.lower()
    original_lower = text_cleaned.lower()
    text_for_check = text_lower
    
    if 't.me/' in text_cleaned or 'http' in text_cleaned or 'https' in text_cleaned:
        has_profile_content = any(indicator in text_lower_quick for indicator in profile_indicators)
        if has_profile_content:
            safe_print(f"[DEBUG check_captcha] Сообщение со ссылкой и признаками профиля - НЕ капча")
            return False
        if '⚠' in text_cleaned or '⚠️' in text_cleaned:
            return True
        return False
    
    if '[WARN]' in text_cleaned or '[WARN' in text_cleaned:
        profile_indicators = [
            'id=', 'id:', 'username', 'имена', 'профиль', 'статистик', 'сообщени', 
            'групп', 'канал', 'репутаци', 'знаком', 'реакци', 'подарк', 'частот',
            'анализ', 'следовать', 'поделиться', 'профиль', 'статистики нет',
            'не замечен в чатах', 'знаешь где этот пользователь'
        ]
        
        has_profile_content = any(indicator in text_for_check for indicator in profile_indicators)
        
        if has_profile_content:
            safe_print(f"[DEBUG check_captcha] [WARN] найдено, но это сообщение о профиле - НЕ капча")
            return False
        
        if ('капча' in text_for_check or 
            any(phrase in text_for_check for phrase in ['нажми', 'кнопк', 'кнопку', 'знаком', 'картинк', 'похожим на'])):
            return True
        
        if has_media:
            return True
        
        if has_buttons:
            pass
    
    if ('капча' in text_for_check or 
        'kαπча' in original_lower or 'kαπчα' in original_lower or
        'captcha' in text_lower):
        if any(phrase in text_for_check for phrase in ['нажми', 'кнопк', 'кнопку', 'знаком', 'картинк']):
            return True
        if has_media or has_buttons:
            return True
    
    if has_media and has_buttons:
        if len(text_cleaned) < 100 and 't.me/' not in text_cleaned:
            return True
    
    return False
