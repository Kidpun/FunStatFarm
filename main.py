import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from funstat.utils import print_banner, print_info, print_error, print_success, console, display_manager, show_loading_screen
from funstat.farm import FunStatFarm
from funstat.config import initialize_config, save_credentials

def setup_api_credentials():
    import time
    
    display_manager.pause_for_input()
    
    os.system('clear' if os.name != 'nt' else 'cls')
    sys.stdout.flush()
    
    print("\n" + "="*75)
    print("                     FunStat Farm")
    print("="*75)
    print("\n[!] Настройка API credentials")
    print("\nПолучите API_ID и API_HASH на https://my.telegram.org")
    print("Введите данные ниже:\n")
    print("="*75 + "\n")
    sys.stdout.flush()
    
    while True:
        try:
            api_id = input("API ID: ").strip()
            if not api_id or not api_id.isdigit():
                print("\n[✗] API ID должен быть числом\n")
                sys.stdout.flush()
                continue
            
            api_hash = input("API Hash: ").strip()
            if not api_hash:
                print("\n[✗] API Hash не может быть пустым\n")
                sys.stdout.flush()
                continue
            
            if save_credentials(api_id, api_hash):
                print("\n[✓] Credentials сохранены!\n")
                sys.stdout.flush()
                time.sleep(0.5)
                display_manager.resume_after_input()
                return
            else:
                print("\n[✗] Ошибка при сохранении credentials\n")
                sys.stdout.flush()
        except KeyboardInterrupt:
            display_manager.resume_after_input()
            print("\n[!] Отменено пользователем\n")
            sys.stdout.flush()
            sys.exit(0)
        except Exception as e:
            print(f"\n[✗] Ошибка: {e}\n")
            sys.stdout.flush()

def check_ocr():
    try:
        import pytesseract
        try:
            version = pytesseract.get_tesseract_version()
            print_success(f"Tesseract доступен (версия: {version})")
        except Exception as e:
            error_msg = str(e).lower()
            if 'tesseract not found' in error_msg or 'not found' in error_msg:
                print_info("Tesseract не найден в PATH")
                if sys.platform == 'darwin':
                    print_info("Установите: brew install tesseract tesseract-lang")
                elif sys.platform == 'win32':
                    print_info("Установите: https://github.com/UB-Mannheim/tesseract/wiki")
                else:
                    print_info("Установите: sudo apt-get install tesseract-ocr tesseract-ocr-rus")
            else:
                print_info(f"Tesseract не работает: {e}")
    except ImportError:
        print_info("pytesseract не установлен (pip install pytesseract)")

    try:
        import easyocr
        print_success("EasyOCR доступен")
    except ImportError:
        print_info("EasyOCR не установлен (pip install easyocr)")

async def main():
    show_loading_screen()
    
    initialize_config()
    
    import funstat.config
    if funstat.config.API_ID is None or funstat.config.API_HASH is None:
        setup_api_credentials()
    
    if funstat.config.API_ID is None or funstat.config.API_HASH is None:
        print_error("Ошибка: API credentials не настроены. Выход.")
        sys.exit(1)
    
    farm = FunStatFarm()
    await farm.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n\n[bold yellow]Программа остановлена пользователем[/bold yellow]")
    except Exception as e:
        console.print(f"\n[bold red]Критическая ошибка: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)
