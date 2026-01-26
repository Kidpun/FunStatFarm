# FunStat Farm

<div align="center">

**Automated Telegram Bot Manager**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Telethon](https://img.shields.io/badge/Telethon-1.24+-green.svg)](https://github.com/LonamiWebs/Telethon)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 📝 Описание

FunStat Farm - автоматизированный бот для работы с Telegram. 

**Возможности:**
- 🔄 Автоматическая пересылка сообщений между ботами
- 🤖 Автоматическое решение капчи (OCR)
- ⏱️ Управление лимитами и кулдаунами
- 🔐 Безопасная работа с API (credentials в `.env`)
- 🎨 Красивый CLI интерфейс с анимацией

## 🚀 Быстрый старт

### 1. Установка

```bash
# Клонируйте репозиторий
git clone https://github.com/Kidpun/FunStatFarm.git
cd FunStatFarm

# Установите зависимости
pip install -r requirements.txt

# Установите Tesseract OCR
# macOS:
brew install tesseract tesseract-lang

# Ubuntu/Debian:
sudo apt-get install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng

# Windows:
# Скачайте с https://github.com/UB-Mannheim/tesseract/wiki
```

### 2. Получите API credentials

1. Зайдите на https://my.telegram.org
2. Войдите в аккаунт
3. Перейдите в "API development tools"
4. Создайте приложение → получите `API_ID` и `API_HASH`

### 3. Запуск

```bash
python3 main.py
```

При первом запуске:
1. ⏳ Загрузочный экран (5 сек)
2. 🔑 Введите `API_ID` и `API_HASH`
3. 📱 Введите номер телефона
4. 💬 Введите код из Telegram
5. 🔐 Введите пароль 2FA (если включен)
6. ✅ Готово! Бот запустится автоматически

## ⚙️ Настройка

Отредактируйте `funstat/config.py`:

```python
SOURCE_BOT = "@en_SearchBot"      # Источник сообщений
CAPTCHA_BOT = 8345627795          # ID бота капчи
TARGET_BOT = "@Funstat_robotibot" # Куда пересылать
INTERVAL = 5                       # Интервал между циклами (сек)
COOLDOWN_HOURS = 24                # Кулдаун при лимите (часы)
```

## 🐛 Решение проблем

### Tesseract не найден

```bash
# macOS
brew install tesseract

# Linux
sudo apt-get install tesseract-ocr

# Windows - установите из https://github.com/UB-Mannheim/tesseract/wiki
```

### EasyOCR ошибка установки

```bash
pip install --upgrade pip
pip install torch torchvision
pip install easyocr
```

### Ошибка авторизации

```bash
# Удалите сессию и попробуйте снова
rm user.session user.session-journal
python3 main.py
```

### Credentials не сохраняются

1. Проверьте права на запись в папку
2. Удалите `.env` и введите credentials заново
3. Убедитесь что антивирус не блокирует файл

## 🔒 Безопасность

⚠️ **ВАЖНО:**
- **НЕ** публикуйте ваши `API_ID` и `API_HASH`
- **НЕ** загружайте `.env` файл в git
- **НЕ** делитесь файлом `user.session`
- `.gitignore` уже настроен для защиты

## 📁 Структура

```
FunStatFarm/
├── main.py              # Запуск
├── requirements.txt     # Зависимости
├── .env                # API credentials (создается автоматически)
└── funstat/
    ├── config.py       # Настройки
    ├── farm.py         # Основная логика
    ├── ocr.py          # Распознавание капчи
    ├── utils.py        # UI и утилиты
    ├── captcha.py      # Детекция капчи
    └── limit.py        # Управление лимитами
```

## ❓ FAQ

**Q: Нужен ли Telegram Premium?**  
A: Нет, работает с обычным аккаунтом.

**Q: Можно ли использовать на сервере?**  
A: Да, но при первом запуске нужен интерактивный терминал для ввода кода.

**Q: Бот банит за использование?**  
A: Соблюдайте правила Telegram, не спамьте. Используйте на свой риск.

**Q: Не работает на Windows?**  
A: Работает, но нужно установить Tesseract отдельно.

## 📄 Лицензия

MIT License - используйте свободно, но на свой риск.

## 🔗 Ссылки

- **Repository:** [github.com/Kidpun/FunStatFarm](https://github.com/Kidpun/FunStatFarm)
- **Issues:** [github.com/Kidpun/FunStatFarm/issues](https://github.com/Kidpun/FunStatFarm/issues)
- **Telegram:** [@pentawork](https://t.me/pentawork)

---

<div align="center">

**⚠️ Disclaimer**

Этот инструмент создан в образовательных целях.  
Используйте в соответствии с правилами Telegram и местным законодательством.  
Авторы не несут ответственности за неправильное использование.

Made with ❤️ by @pentawork

</div>
