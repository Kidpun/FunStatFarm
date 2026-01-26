import sys
import os
import time
import math
import threading
import colorsys
from collections import deque
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.align import Align
from rich.live import Live
from rich.layout import Layout
from rich.progress import Progress, BarColumn, TextColumn
from rich import box

console = Console()
log_buffer = deque(maxlen=10)

class DisplayManager:
    def __init__(self):
        self.banner_phase = 0.0
        self.banner_running = False
        self.live_instance = None
        self.layout_instance = None
        self.input_mode = threading.Event()
        self.phase_lock = threading.Lock()
        self.animation_thread = None
        self.live_thread = None
    
    def get_purple_hex(self, phase):
        sine = math.sin(phase)
        normalized = (sine + 1) / 2
        r = int(75 + (200 - 75) * normalized)
        g = int(0 + (50 - 0) * normalized)
        b = int(130 + (255 - 130) * normalized)
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def create_animated_banner(self, phase):
        purple1 = self.get_purple_hex(phase)
        purple2 = self.get_purple_hex(phase + math.pi / 3)
        purple3 = self.get_purple_hex(phase + 2 * math.pi / 3)
        
        banner = Text()
        banner.append("FunStat Farm", style=f"bold {purple1}")
        banner.append("\n")
        banner.append("Automated Telegram Bot Manager", style=f"{purple2}")
        banner.append("\n")
        banner.append("Created by @pentawork", style=f"{purple3}")
        
        panel = Panel(
            Align.center(banner, vertical="middle"),
            box=box.DOUBLE_EDGE,
            border_style=f"{purple1}",
            padding=(1, 2)
        )
        return panel
    
    def update_display(self):
        if self.layout_instance is None:
            return
        
        try:
            if not log_buffer:
                logs_text = Text(" ")
            else:
                logs_text = Text()
                for i, log_line in enumerate(log_buffer):
                    try:
                        rendered = console.render_str(log_line)
                        if isinstance(rendered, Text):
                            logs_text.append(rendered)
                        else:
                            logs_text.append(str(log_line))
                    except:
                        logs_text.append(str(log_line))
                    if i < len(log_buffer) - 1:
                        logs_text.append("\n")
            
            self.layout_instance["logs"].update(logs_text)
            
            with self.phase_lock:
                phase = self.banner_phase
            self.layout_instance["banner"].update(self.create_animated_banner(phase))
        except Exception:
            pass
    
    def banner_animation_loop(self):
        start_time = time.time()
        while self.banner_running:
            try:
                if not self.input_mode.is_set():
                    elapsed = time.time() - start_time
                    phase = elapsed * 2
                    
                    with self.phase_lock:
                        self.banner_phase = phase
                    
                    if self.layout_instance:
                        self.update_display()
                
                time.sleep(0.05)
            except Exception:
                pass
    
    def live_updater_loop(self):
        layout = Layout()
        layout.split_column(
            Layout(name="banner", size=7),
            Layout(name="logs", ratio=1)
        )
        
        self.layout_instance = layout
        self.live_instance = Live(layout, refresh_per_second=20, console=console, screen=False)
        
        try:
            with self.live_instance:
                while self.banner_running:
                    time.sleep(0.1)
        except Exception:
            pass
        finally:
            self.layout_instance = None
            self.live_instance = None
    
    def start_display(self):
        if self.banner_running:
            return
        
        self.banner_running = True
        self.input_mode.clear()
        
        self.live_thread = threading.Thread(target=self.live_updater_loop, daemon=True)
        self.live_thread.start()
        time.sleep(0.3)
        
        self.animation_thread = threading.Thread(target=self.banner_animation_loop, daemon=True)
        self.animation_thread.start()
        time.sleep(0.2)
    
    def stop_display(self):
        if self.live_instance:
            try:
                self.live_instance.stop()
            except:
                pass
        time.sleep(0.2)
    
    def pause_for_input(self):
        self.input_mode.set()
        self.stop_display()
        time.sleep(0.1)
    
    def resume_after_input(self):
        self.input_mode.clear()
        if self.live_instance:
            try:
                self.live_instance.start()
            except:
                pass
    
    def show_loading_screen(self, duration=5.0):
        self.banner_running = True
        self.input_mode.clear()
        
        layout = Layout()
        layout.split_column(
            Layout(name="banner", size=7),
            Layout(name="progress", size=3)
        )
        
        self.layout_instance = layout
        self.live_instance = Live(layout, refresh_per_second=30, console=console, screen=False)
        
        try:
            self.live_instance.start()
        except:
            return
        
        start_time = time.time()
        progress_phase = 0.0
        
        self.animation_thread = threading.Thread(target=self.banner_animation_loop, daemon=True)
        self.animation_thread.start()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed >= duration:
                break
            
            progress = elapsed / duration
            
            progress_text = Text()
            progress_text.append("Загрузка... ", style="bold white")
            
            bar_width = 50
            filled = int(bar_width * progress)
            
            for i in range(bar_width):
                hue = ((progress_phase + i * 0.1) * 360) % 360
                r, g, b = colorsys.hsv_to_rgb(hue / 360, 1.0, 1.0)
                color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
                
                if i < filled:
                    progress_text.append("█", style=color)
                else:
                    progress_text.append("░", style="dim white")
            
            progress_text.append(f" {int(progress * 100)}%", style="bold white")
            
            progress_panel = Panel(
                Align.center(progress_text, vertical="middle"),
                box=box.ROUNDED,
                border_style="white",
                padding=(0, 1)
            )
            
            layout["progress"].update(progress_panel)
            
            with self.phase_lock:
                phase = self.banner_phase
            layout["banner"].update(self.create_animated_banner(phase))
            
            progress_phase += 0.1
            time.sleep(0.03)
        
        self.stop_display()
        self.banner_running = False
        time.sleep(0.2)

display_manager = DisplayManager()

def show_loading_screen():
    display_manager.show_loading_screen()

def print_banner():
    display_manager.start_display()

def print_success(message):
    log_buffer.append(f"[bold green]✓[/bold green] {message}")
    display_manager.update_display()

def print_error(message):
    log_buffer.append(f"[bold red]✗[/bold red] {message}")
    display_manager.update_display()

def print_warning(message):
    log_buffer.append(f"[bold yellow]⚠[/bold yellow] {message}")
    display_manager.update_display()

def print_info(message):
    log_buffer.append(f"[bold blue]ℹ[/bold blue] {message}")
    display_manager.update_display()

def print_step(message):
    log_buffer.append(f"[bold cyan]→[/bold cyan] {message}")
    display_manager.update_display()

def safe_print(*args, **kwargs):
    text = ' '.join(str(arg) for arg in args)
    replacements = {
        '🔥': '[START]', '📱': '[TELEGRAM]', '📁': '[FILE]', '⏳': '[WAIT]',
        '❌': '[ERROR]', '✅': '[OK]', '🔐': '[AUTH]', '📞': '[PHONE]',
        '🔑': '[PASSWORD]', '🚨': '[IMPORTANT]', '💬': '[MESSAGE]',
        '🔍': '[SEARCH]', '📥': '[SOURCE]', '📤': '[TARGET]', '⏱': '[INTERVAL]',
        '⚡': '[AUTO]', '🚀': '[FARM]', '📢': '[INFO]', '🔄': '[CYCLE]',
        '📭': '[NO_MSG]', '🎯': '[BUTTON]', '🛑': '[STOP]', '⚠️': '[WARN]'
    }
    for emoji, replacement in replacements.items():
        text = text.replace(emoji, replacement)
    
    log_buffer.append(text)
    display_manager.update_display()

def wait_for_keypress(prompt="Нажмите любую клавишу для продолжения..."):
    log_buffer.append(f"\n[dim]{prompt}[/dim]")
    display_manager.update_display()
    if sys.platform != 'win32':
        try:
            import tty
            import termios
            old_settings = termios.tcgetattr(sys.stdin)
            try:
                tty.setraw(sys.stdin.fileno())
                sys.stdin.read(1)
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        except Exception:
            input()
    else:
        try:
            import msvcrt
            msvcrt.getch()
        except ImportError:
            input()

def get_tesseract_path():
    if sys.platform == 'darwin':
        possible_paths = [
            '/opt/homebrew/bin/tesseract',
            '/usr/local/bin/tesseract',
            '/opt/homebrew/opt/tesseract/bin/tesseract',
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
    elif sys.platform == 'win32':
        possible_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
    return None

input_mode = display_manager.input_mode
live_instance = display_manager
