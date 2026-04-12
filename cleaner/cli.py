import os
import sys
import argparse
import ctypes

from cleaner import __version__
from cleaner.display import (
    banner, confirm, menu, info, error, warning, success, show_selected, pause,
    GREEN, YELLOW, RESET, BOLD, DIM, GRAY,
)
from cleaner.engine import TASKS, QUICK_TASKS, DEEP_TASKS, run_tasks


def _enable_ansi():
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def show_status():
    if is_admin():
        success(f"Running as {BOLD}Administrator{RESET}")
    else:
        warning(f"Running as standard user — some operations may be limited")
        info(f"{DIM}Tip: Right-click CMD → Run as Administrator for full access{RESET}")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="shxrkcleaner",
        description="ShxrkCleaner — Windows system cleaner, fast & minimal.",
        epilog="Run without flags for interactive mode.",
    )
    parser.add_argument(
        "--version", action="version", version=f"ShxrkCleaner {__version__}"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick clean: temp files, prefetch, recycle bin",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Deep clean: all targets including browser cache and junk files",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompts",
    )
    parser.add_argument(
        "--temp", action="store_true", help="Clean Windows and user temp files"
    )
    parser.add_argument(
        "--prefetch", action="store_true", help="Clean Prefetch directory"
    )
    parser.add_argument(
        "--recycle", action="store_true", help="Empty Recycle Bin"
    )
    parser.add_argument(
        "--junk", action="store_true", help="Remove junk/log/cache files"
    )
    parser.add_argument(
        "--browser", action="store_true", help="Clean Chrome and Edge cache"
    )
    parser.add_argument(
        "--dns", action="store_true", help="Flush DNS resolver cache"
    )
    parser.add_argument(
        "--winupdate", action="store_true", help="Clean Windows Update cache"
    )
    parser.add_argument(
        "--discord", action="store_true", help="Clean Discord cache"
    )
    parser.add_argument(
        "--spotify", action="store_true", help="Clean Spotify cache"
    )
    parser.add_argument(
        "--steam", action="store_true", help="Clean Steam shader/depot cache"
    )
    parser.add_argument(
        "--eventlogs", action="store_true", help="Clear Windows Event Logs"
    )
    parser.add_argument(
        "--fontcache", action="store_true", help="Clean font cache"
    )
    parser.add_argument(
        "--nvidia", action="store_true", help="Clean NVIDIA shader cache"
    )
    parser.add_argument(
        "--teams", action="store_true", help="Clean Microsoft Teams cache"
    )
    parser.add_argument(
        "--pip", action="store_true", help="Clean pip package cache"
    )
    parser.add_argument(
        "--npm", action="store_true", help="Clean npm package cache"
    )
    parser.add_argument(
        "--thumbnails", action="store_true", help="Clean Windows thumbnail cache"
    )
    parser.add_argument(
        "--installer", action="store_true", help="Clean Windows Installer patch cache"
    )
    parser.add_argument(
        "--recent", action="store_true", help="Clean recent files and jump lists"
    )
    parser.add_argument(
        "--crashdumps", action="store_true", help="Clean crash dumps and minidumps"
    )
    parser.add_argument(
        "--vscode", action="store_true", help="Clean VS Code cache"
    )
    parser.add_argument(
        "--java", action="store_true", help="Clean Java/Gradle/Maven cache"
    )
    parser.add_argument(
        "--dxcache", action="store_true", help="Clean DirectX/GPU shader cache"
    )
    parser.add_argument(
        "--delivery", action="store_true", help="Clean Delivery Optimization cache"
    )
    parser.add_argument(
        "--telegram", action="store_true", help="Clean Telegram cache"
    )
    parser.add_argument(
        "--wer", action="store_true", help="Clean Windows Error Reports"
    )
    return parser


def resolve_tasks(args):
    if args.quick:
        return QUICK_TASKS[:]
    if args.deep:
        return DEEP_TASKS[:]

    flag_map = {
        "prefetch": ["prefetch"],
        "recycle": ["recycle"],
        "junk": ["junk"],
        "browser": ["browser"],
        "dns": ["dns"],
        "winupdate": ["winupdate"],
        "discord": ["discord"],
        "spotify": ["spotify"],
        "steam": ["steam"],
        "eventlogs": ["eventlogs"],
        "fontcache": ["fontcache"],
        "nvidia": ["nvidia"],
        "teams": ["teams"],
        "pip": ["pip"],
        "npm": ["npm"],
        "thumbnails": ["thumbnails"],
        "installer": ["installer"],
        "recent": ["recent"],
        "crashdumps": ["crashdumps"],
        "vscode": ["vscode"],
        "java": ["java"],
        "dxcache": ["dxcache"],
        "delivery": ["delivery"],
        "telegram": ["telegram"],
        "wer": ["wer"],
    }

    tasks = []
    if args.temp:
        tasks.extend(["temp_win", "temp_user"])
    for flag, keys in flag_map.items():
        if getattr(args, flag, False):
            tasks.extend(keys)
    return tasks


def interactive_mode(skip_confirm=False):
    options = [(key, label) for key, (label, _) in TASKS.items()]
    selected = menu(options)

    if not selected:
        info("Nothing selected.")
        return

    labels = [TASKS[k][0] for k in selected if k in TASKS]
    show_selected(labels)

    if not skip_confirm:
        if not confirm("Proceed with cleaning?"):
            info("Cancelled.")
            return

    run_tasks(selected)


def main():
    _enable_ansi()
    banner()
    show_status()

    parser = build_parser()
    args = parser.parse_args()

    tasks = resolve_tasks(args)

    if not tasks:
        interactive_mode(skip_confirm=args.yes)
        pause()
        return

    task_labels = [TASKS[k][0] for k in tasks if k in TASKS]
    show_selected(task_labels)

    if not args.yes:
        if not confirm("Proceed with cleaning?"):
            info("Cancelled.")
            pause()
            return

    run_tasks(tasks)
    pause()


if __name__ == "__main__":
    main()
