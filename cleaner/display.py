import os
import sys
import time
import shutil
import threading

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"
RED = "\033[38;5;203m"
GREEN = "\033[38;5;114m"
YELLOW = "\033[38;5;221m"
CYAN = "\033[38;5;81m"
WHITE = "\033[38;5;255m"
MAGENTA = "\033[38;5;177m"
BLUE = "\033[38;5;75m"
ORANGE = "\033[38;5;209m"
GRAY = "\033[38;5;242m"
DARK = "\033[38;5;236m"
LIME = "\033[38;5;156m"
BG_DARK = "\033[48;5;234m"
BG_CYAN = "\033[48;5;24m"
BG_RED = "\033[48;5;52m"
BG_GREEN = "\033[48;5;22m"

GRADIENT = [
    "\033[38;5;39m",
    "\033[38;5;38m",
    "\033[38;5;44m",
    "\033[38;5;43m",
    "\033[38;5;49m",
    "\033[38;5;48m",
    "\033[38;5;84m",
]

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def _w(text):
    sys.stdout.write(text)
    sys.stdout.flush()


def terminal_width():
    return min(shutil.get_terminal_size((100, 24)).columns, 120)


def _gradient_text(text):
    out = ""
    for i, ch in enumerate(text):
        out += GRADIENT[i % len(GRADIENT)] + ch
    return out + RESET


def _center(text, width, fill=" "):
    visible = len(text.encode("ascii", "ignore").decode())
    raw_len = 0
    in_escape = False
    for ch in text:
        if ch == "\033":
            in_escape = True
        elif in_escape and ch.isalpha():
            in_escape = False
        elif not in_escape:
            raw_len += 1
    pad = max(0, width - raw_len)
    left = pad // 2
    right = pad - left
    return fill * left + text + fill * right


def _visible_len(text):
    length = 0
    in_escape = False
    for ch in text:
        if ch == "\033":
            in_escape = True
        elif in_escape and ch.isalpha():
            in_escape = False
        elif not in_escape:
            length += 1
    return length


def banner():
    w = terminal_width()
    inner = w - 6

    logo_lines = [
        f"{BOLD}{_gradient_text('  ███████╗██╗  ██╗██╗  ██╗██████╗ ██╗  ██╗')}",
        f"{BOLD}{_gradient_text('  ██╔════╝██║  ██║╚██╗██╔╝██╔══██╗██║ ██╔╝')}",
        f"{BOLD}{_gradient_text('  ███████╗███████║ ╚███╔╝ ██████╔╝█████╔╝ ')}",
        f"{BOLD}{_gradient_text('  ╚════██║██╔══██║ ██╔██╗ ██╔══██╗██╔═██╗ ')}",
        f"{BOLD}{_gradient_text('  ███████║██║  ██║██╔╝ ██╗██║  ██║██║  ██╗')}",
        f"{BOLD}{_gradient_text('  ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝')}",
        f"",
        f"{BOLD}{_gradient_text('   ██████╗██╗     ███████╗ █████╗ ███╗   ██╗███████╗██████╗ ')}",
        f"{BOLD}{_gradient_text('  ██╔════╝██║     ██╔════╝██╔══██╗████╗  ██║██╔════╝██╔══██╗')}",
        f"{BOLD}{_gradient_text('  ██║     ██║     █████╗  ███████║██╔██╗ ██║█████╗  ██████╔╝')}",
        f"{BOLD}{_gradient_text('  ██║     ██║     ██╔══╝  ██╔══██║██║╚██╗██║██╔══╝  ██╔══██╗')}",
        f"{BOLD}{_gradient_text('  ╚██████╗███████╗███████╗██║  ██║██║ ╚████║███████╗██║  ██║')}",
        f"{BOLD}{_gradient_text('   ╚═════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝')}",
    ]

    _w(f"\n{DARK}  {'─' * inner}{RESET}\n")
    for line in logo_lines:
        _w(f"  {line}\n")
    _w(f"\n{GRAY}  {'─' * inner}{RESET}\n")

    subtitle = f"{DIM}Windows System Cleaner{RESET}  {DARK}│{RESET}  {CYAN}v1.0.0{RESET}  {DARK}│{RESET}  {DIM}by Shxrk{RESET}"
    _w(f"  {_center(subtitle, inner)}\n")
    _w(f"{GRAY}  {'─' * inner}{RESET}\n\n")


def header(text):
    w = terminal_width()
    inner = w - 6
    _w(f"\n{DARK}  ┌{'─' * inner}┐{RESET}\n")
    padded = _center(f"{BOLD}{CYAN}  ⟫  {text}{RESET}", inner)
    _w(f"{DARK}  │{RESET}{padded}{DARK}│{RESET}\n")
    _w(f"{DARK}  └{'─' * inner}┘{RESET}\n")


def success(text):
    _w(f"  {GREEN}✔{RESET} {WHITE}{text}{RESET}\n")


def warning(text):
    _w(f"  {YELLOW}⚠{RESET} {YELLOW}{text}{RESET}\n")


def error(text):
    _w(f"  {RED}✖{RESET} {RED}{text}{RESET}\n")


def info(text):
    _w(f"  {GRAY}›{RESET} {DIM}{text}{RESET}\n")


def detail(text):
    _w(f"      {DARK}{text}{RESET}\n")


class Spinner:
    def __init__(self, text="Working"):
        self._text = text
        self._running = False
        self._thread = None

    def _animate(self):
        i = 0
        while self._running:
            frame = SPINNER_FRAMES[i % len(SPINNER_FRAMES)]
            _w(f"\r  {CYAN}{frame}{RESET} {DIM}{self._text}{RESET}  ")
            i += 1
            time.sleep(0.08)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def stop(self, final_text=None):
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
        _w(f"\r{' ' * (terminal_width() - 2)}\r")
        if final_text:
            success(final_text)


def progress(current, total, label="", freed=0):
    w = max(terminal_width() - 50, 15)
    pct = current / total if total > 0 else 1.0
    filled = int(w * pct)

    bar_chars = ""
    for i in range(w):
        if i < filled:
            color = GRADIENT[i % len(GRADIENT)]
            bar_chars += f"{color}━{RESET}"
        else:
            bar_chars += f"{DARK}━{RESET}"

    pct_color = GREEN if pct >= 0.8 else (YELLOW if pct >= 0.4 else CYAN)
    freed_str = f" {DARK}│{RESET} {GRAY}{format_size(freed)}{RESET}" if freed else ""
    trunc_label = label[:20].ljust(20)

    _w(f"\r  {bar_chars} {pct_color}{pct * 100:5.1f}%{RESET} {DIM}{trunc_label}{RESET}{freed_str}  ")

    if current >= total:
        _w(f"\r{' ' * (terminal_width() - 2)}\r")


def format_size(size_bytes):
    if size_bytes <= 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024.0:
            if unit == "B":
                return f"{int(size_bytes)} {unit}"
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def summary_table(results, elapsed=0.0):
    w = terminal_width()
    col1 = 36
    col2 = 14
    col3 = 12
    col4 = 10
    inner = col1 + col2 + col3 + col4 + 7

    _w(f"\n{CYAN}  ┌{'─' * (inner)}┐{RESET}\n")
    title = _center(f"{BOLD}{WHITE}RESULTS{RESET}", inner)
    _w(f"{CYAN}  │{RESET}{title}{CYAN}│{RESET}\n")
    _w(f"{CYAN}  ├{'─' * col1}┬{'─' * col2}┬{'─' * col3}┬{'─' * col4}┤{RESET}\n")

    h1 = f"{BOLD}{WHITE}{'Task':<{col1 - 2}}{RESET}"
    h2 = f"{BOLD}{WHITE}{'Freed':>{col2 - 2}}{RESET}"
    h3 = f"{BOLD}{WHITE}{'Files':>{col3 - 2}}{RESET}"
    h4 = f"{BOLD}{WHITE}{'Status':^{col4 - 2}}{RESET}"
    _w(f"{CYAN}  │{RESET} {h1} {CYAN}│{RESET} {h2} {CYAN}│{RESET} {h3} {CYAN}│{RESET} {h4} {CYAN}│{RESET}\n")
    _w(f"{CYAN}  ├{'─' * col1}┼{'─' * col2}┼{'─' * col3}┼{'─' * col4}┤{RESET}\n")

    total_freed = 0
    total_files = 0
    for entry in results:
        name = entry.get("name", "")
        freed = entry.get("freed", 0)
        files = entry.get("files", 0)
        ok = entry.get("ok", False)
        total_freed += freed
        total_files += files

        size_str = format_size(freed)
        files_str = f"{files:,}"
        if ok:
            status = f"{GREEN}{'done':^{col4 - 2}}{RESET}"
        else:
            status = f"{ORANGE}{'partial':^{col4 - 2}}{RESET}"

        size_color = GREEN if freed > 1048576 else (YELLOW if freed > 1024 else GRAY)

        _w(f"{CYAN}  │{RESET} {WHITE}{name:<{col1 - 2}}{RESET} ")
        _w(f"{CYAN}│{RESET} {size_color}{size_str:>{col2 - 2}}{RESET} ")
        _w(f"{CYAN}│{RESET} {GRAY}{files_str:>{col3 - 2}}{RESET} ")
        _w(f"{CYAN}│{RESET} {status} {CYAN}│{RESET}\n")

    _w(f"{CYAN}  ├{'─' * col1}┼{'─' * col2}┼{'─' * col3}┼{'─' * col4}┤{RESET}\n")

    total_size_str = format_size(total_freed)
    total_files_str = f"{total_files:,}"
    size_color = GREEN if total_freed > 1048576 else YELLOW
    _w(f"{CYAN}  │{RESET} {BOLD}{WHITE}{'TOTAL':<{col1 - 2}}{RESET} ")
    _w(f"{CYAN}│{RESET} {BOLD}{size_color}{total_size_str:>{col2 - 2}}{RESET} ")
    _w(f"{CYAN}│{RESET} {BOLD}{WHITE}{total_files_str:>{col3 - 2}}{RESET} ")
    _w(f"{CYAN}│{RESET} {' ' * (col4 - 2)} {CYAN}│{RESET}\n")
    _w(f"{CYAN}  └{'─' * col1}┴{'─' * col2}┴{'─' * col3}┴{'─' * col4}┘{RESET}\n")

    if elapsed > 0:
        _w(f"\n  {GRAY}Completed in {elapsed:.1f}s{RESET}\n")
    _w("\n")


def confirm(prompt):
    _w(f"\n  {YELLOW}?{RESET} {WHITE}{prompt}{RESET} {DARK}[y/N]{RESET} ")
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        _w("\n")
        return False
    return answer in ("y", "yes")


def menu(options):
    w = terminal_width()
    inner = w - 6

    _w(f"\n{DARK}  ┌{'─' * inner}┐{RESET}\n")
    title = _center(f"{BOLD}{WHITE}SELECT OPERATIONS{RESET}", inner)
    _w(f"{DARK}  │{RESET}{title}{DARK}│{RESET}\n")
    _w(f"{DARK}  └{'─' * inner}┘{RESET}\n\n")

    icons = {
        "temp_win": "🗂️ ",
        "temp_user": "📁",
        "prefetch": "⚡",
        "recycle": "🗑️ ",
        "junk": "🧹",
        "browser": "🌐",
        "dns": "🔄",
        "winupdate": "📦",
        "discord": "💬",
        "spotify": "🎵",
        "steam": "🎮",
        "eventlogs": "📋",
        "fontcache": "🔤",
        "nvidia": "🖥️ ",
        "teams": "👥",
        "pip": "🐍",
        "npm": "📗",
        "thumbnails": "🖼️ ",
        "installer": "🔧",
        "recent": "🕐",
        "crashdumps": "💥",
        "vscode": "💻",
        "java": "☕",
        "dxcache": "🎲",
        "delivery": "📡",
        "telegram": "✈️ ",
        "wer": "🐛",
        "epic": "🎮",
        "riot": "🗡️ ",
        "ea": "⚽",
        "battlenet": "⚔️ ",
        "ubisoft": "🦅",
        "whatsapp": "💬",
        "obs": "🎥",
        "gog": "🌌",
    }

    for i, (key, label) in enumerate(options, 1):
        icon = icons.get(key, "  ")
        _w(f"    {CYAN}{BOLD}{i}{RESET}  {icon} {WHITE}{label}{RESET}\n")

    _w(f"\n    {MAGENTA}{BOLD}A{RESET}  🚀 {BOLD}{WHITE}Select all{RESET}\n")
    _w(f"    {RED}{BOLD}Q{RESET}  ✕  {DIM}Quit{RESET}\n")

    _w(f"\n  {GRAY}Enter choices (e.g. 1,3,5 or A):{RESET} ")

    try:
        raw = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        _w("\n")
        return []

    if raw == "q":
        return []
    if raw == "a":
        return [key for key, _ in options]

    selected = []
    for part in raw.replace(" ", "").split(","):
        try:
            idx = int(part) - 1
            if 0 <= idx < len(options):
                selected.append(options[idx][0])
        except ValueError:
            continue
    return selected


def show_selected(labels):
    _w(f"\n  {CYAN}▸{RESET} {DIM}Targets:{RESET} ")
    for i, label in enumerate(labels):
        if i > 0:
            _w(f"{DARK}, {RESET}")
        _w(f"{WHITE}{label}{RESET}")
    _w("\n")


def pause():
    _w(f"\n  {GRAY}Press Enter to exit...{RESET} ")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass
