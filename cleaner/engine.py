import os
import sys
import ctypes
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from cleaner.display import (
    success, warning, error, info, detail, progress, Spinner, format_size,
)

PROTECTED_FILES = frozenset({
    "ntuser.dat", "ntuser.dat.log", "ntuser.dat.log1", "ntuser.dat.log2",
    "ntuser.ini", "bootmgr", "pagefile.sys", "hiberfil.sys", "swapfile.sys",
    "bootstat.dat", "bootmgfw.efi",
})

JUNK_EXTENSIONS = frozenset({
    ".tmp", ".log", ".dmp", ".chk", ".old", ".bak", ".etl",
})

JUNK_FILENAMES = frozenset({
    "thumbs.db", "desktop.ini", "debug.log", "npm-debug.log",
    "yarn-error.log", "yarn-debug.log",
})

MAX_WORKERS = 8


def _is_protected(name):
    return name.lower() in PROTECTED_FILES


def _safe_remove_file(path):
    try:
        stat = os.stat(path)
        size = stat.st_size
        os.remove(path)
        return size, True
    except (PermissionError, OSError):
        return 0, False


def _safe_remove_tree(path):
    total = 0
    count = 0
    dirs_to_remove = []
    try:
        for root, dirs, files in os.walk(path, topdown=False):
            for f in files:
                fp = os.path.join(root, f)
                freed, ok = _safe_remove_file(fp)
                total += freed
                if ok:
                    count += 1
            dirs_to_remove.append(root)
            for d in dirs:
                dirs_to_remove.append(os.path.join(root, d))
    except (PermissionError, OSError):
        pass

    for dp in reversed(dirs_to_remove):
        try:
            os.rmdir(dp)
        except OSError:
            pass

    try:
        os.rmdir(path)
    except OSError:
        pass

    return total, count


def _scan_dir_fast(target_dir):
    files = []
    dirs = []
    try:
        with os.scandir(target_dir) as it:
            for entry in it:
                try:
                    if entry.is_file(follow_symlinks=False):
                        files.append(entry.path)
                    elif entry.is_dir(follow_symlinks=False):
                        dirs.append(entry.path)
                except OSError:
                    continue
    except (PermissionError, OSError):
        pass
    return files, dirs


def _scan_recursive(target_dir, extensions=None, filenames=None, max_depth=10):
    results = []
    stack = [(target_dir, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > max_depth:
            continue
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_file(follow_symlinks=False):
                            name_lower = entry.name.lower()
                            if _is_protected(entry.name):
                                continue
                            match = False
                            if extensions:
                                _, ext = os.path.splitext(name_lower)
                                if ext in extensions:
                                    match = True
                            if filenames and name_lower in filenames:
                                match = True
                            if match:
                                results.append(entry.path)
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append((entry.path, depth + 1))
                    except OSError:
                        continue
        except (PermissionError, OSError):
            continue
    return results


def _parallel_delete_files(file_list, label="Cleaning"):
    freed = 0
    count = 0
    total = len(file_list)
    if total == 0:
        return 0, 0

    batch_size = max(1, total // 100)
    processed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for fp in file_list:
            fut = executor.submit(_safe_remove_file, fp)
            futures[fut] = fp

        for fut in as_completed(futures):
            size, ok = fut.result()
            freed += size
            if ok:
                count += 1
            processed += 1
            if processed % batch_size == 0 or processed == total:
                name = os.path.basename(futures[fut])
                progress(processed, total, name[:20], freed=freed)

    return freed, count


def _parallel_delete_trees(dir_list, label="Cleaning"):
    freed = 0
    count = 0
    total = len(dir_list)
    if total == 0:
        return 0, 0

    processed = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for dp in dir_list:
            fut = executor.submit(_safe_remove_tree, dp)
            futures[fut] = dp

        for fut in as_completed(futures):
            size, c = fut.result()
            freed += size
            count += c
            processed += 1
            name = os.path.basename(futures[fut])
            progress(processed, total, name[:20], freed=freed)

    return freed, count


def _clean_directory(target_dir):
    if not os.path.isdir(target_dir):
        warning(f"Not found: {target_dir}")
        return 0, 0, False

    spinner = Spinner(f"Scanning {target_dir}")
    spinner.start()
    files, dirs = _scan_dir_fast(target_dir)
    spinner.stop()

    detail(f"Found {len(files)} files, {len(dirs)} directories")

    freed_f, count_f = _parallel_delete_files(files)
    freed_d, count_d = _parallel_delete_trees(dirs)

    return freed_f + freed_d, count_f + count_d, True


def clean_windows_temp():
    win_temp = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Temp")
    info(f"Target: {win_temp}")
    freed, count, ok = _clean_directory(win_temp)
    if ok:
        success(f"Windows Temp cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": ok}


def clean_user_temp():
    user_temp = tempfile.gettempdir()
    info(f"Target: {user_temp}")
    freed, count, ok = _clean_directory(user_temp)
    if ok:
        success(f"User Temp cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": ok}


def clean_prefetch():
    prefetch = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Prefetch")
    info(f"Target: {prefetch}")
    freed, count, ok = _clean_directory(prefetch)
    if ok:
        success(f"Prefetch cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": ok}


def empty_recycle_bin():
    info("Emptying Recycle Bin via Shell API...")
    freed = 0
    ok = False
    try:
        SHEmptyRecycleBin = ctypes.windll.shell32.SHEmptyRecycleBinW
        flags = 0x00000001 | 0x00000002 | 0x00000004
        result = SHEmptyRecycleBin(None, None, flags)
        ok = result == 0 or result == -2147418113
    except Exception:
        pass

    if not ok:
        info("Shell API unavailable, scanning $Recycle.Bin...")
        drives = [
            f"{chr(d)}:\\" for d in range(65, 91) if os.path.exists(f"{chr(d)}:\\")
        ]
        recycle_dirs = []
        for drive in drives:
            rp = os.path.join(drive, "$Recycle.Bin")
            if os.path.isdir(rp):
                try:
                    for entry in os.scandir(rp):
                        if entry.is_dir(follow_symlinks=False):
                            recycle_dirs.append(entry.path)
                except (PermissionError, OSError):
                    continue

        if recycle_dirs:
            freed, count = _parallel_delete_trees(recycle_dirs)
            ok = True
            success(f"Recycle Bin emptied — {format_size(freed)} from {count:,} items")
        else:
            warning("Could not access Recycle Bin")
        return {"freed": freed, "files": 0, "ok": ok}

    success("Recycle Bin emptied")
    return {"freed": freed, "files": 0, "ok": True}


def clean_junk_files():
    user_profile = os.environ.get("USERPROFILE", "")
    system_root = os.environ.get("SystemRoot", r"C:\Windows")

    scan_dirs = [user_profile, system_root]
    all_files = []

    spinner = Spinner("Scanning for junk files across system...")
    spinner.start()
    for scan_dir in scan_dirs:
        if os.path.isdir(scan_dir):
            found = _scan_recursive(
                scan_dir,
                extensions=JUNK_EXTENSIONS,
                filenames=JUNK_FILENAMES,
                max_depth=8,
            )
            all_files.extend(found)
    spinner.stop()

    detail(f"Found {len(all_files):,} junk files to remove")

    if not all_files:
        success("No junk files found")
        return {"freed": 0, "files": 0, "ok": True}

    freed, count = _parallel_delete_files(all_files, "Junk files")
    success(f"Junk files cleaned — {format_size(freed)} from {count:,} files")
    return {"freed": freed, "files": count, "ok": True}


def _collect_browser_cache(base_path):
    paths = []
    if not os.path.isdir(base_path):
        return paths
    cache_names = {"Cache", "Code Cache", "GPUCache", "Service Worker", "ScriptCache"}
    try:
        for entry in os.scandir(base_path):
            if entry.is_dir(follow_symlinks=False):
                try:
                    for sub in os.scandir(entry.path):
                        if sub.is_dir(follow_symlinks=False) and sub.name in cache_names:
                            paths.append(sub.path)
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError):
        pass

    for extra in ("ShaderCache", "GrShaderCache"):
        ep = os.path.join(base_path, extra)
        if os.path.isdir(ep):
            paths.append(ep)

    return paths


def clean_browser_cache():
    local = os.environ.get("LOCALAPPDATA", "")

    browsers = {
        "Chrome": os.path.join(local, "Google", "Chrome", "User Data"),
        "Edge": os.path.join(local, "Microsoft", "Edge", "User Data"),
        "Brave": os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data"),
        "Opera": os.path.join(local, "Opera Software", "Opera Stable"),
        "Opera GX": os.path.join(local, "Opera Software", "Opera GX Stable"),
    }

    spinner = Spinner("Scanning browser cache directories...")
    spinner.start()
    all_paths = []
    found_browsers = []
    for name, base in browsers.items():
        paths = _collect_browser_cache(base)
        if paths:
            found_browsers.append(f"{name} ({len(paths)} dirs)")
            all_paths.extend(paths)
    spinner.stop()

    if not all_paths:
        warning("No browser cache found")
        return {"freed": 0, "files": 0, "ok": True}

    for fb in found_browsers:
        detail(fb)

    freed, count = _parallel_delete_trees(all_paths, "Browser cache")

    for name, base in browsers.items():
        paths = _collect_browser_cache(base)
        if paths:
            success(f"{name} cache cleaned")

    success(f"Browser cache cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": True}


def flush_dns():
    info("Flushing DNS resolver cache...")
    try:
        result = subprocess.run(
            ["ipconfig", "/flushdns"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            success("DNS cache flushed")
            return {"freed": 0, "files": 0, "ok": True}
        else:
            warning(f"DNS flush returned code {result.returncode}")
            return {"freed": 0, "files": 0, "ok": False}
    except FileNotFoundError:
        error("ipconfig not found")
        return {"freed": 0, "files": 0, "ok": False}
    except subprocess.TimeoutExpired:
        error("DNS flush timed out")
        return {"freed": 0, "files": 0, "ok": False}
    except PermissionError:
        warning("DNS flush requires administrator privileges")
        return {"freed": 0, "files": 0, "ok": False}


def clean_windows_update():
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    targets = [
        os.path.join(system_root, "SoftwareDistribution", "Download"),
        os.path.join(system_root, "SoftwareDistribution", "DataStore"),
    ]

    total_freed = 0
    total_count = 0
    ok = False

    for target in targets:
        if os.path.isdir(target):
            info(f"Target: {target}")
            freed, count, success_flag = _clean_directory(target)
            total_freed += freed
            total_count += count
            if success_flag:
                ok = True

    if ok:
        success(f"Windows Update cache cleaned — {format_size(total_freed)} from {total_count:,} items")
    else:
        warning("Could not access Windows Update cache (requires Admin)")

    return {"freed": total_freed, "files": total_count, "ok": ok}


def clean_discord_cache():
    appdata = os.environ.get("APPDATA", "")
    local = os.environ.get("LOCALAPPDATA", "")

    targets = []
    for base_name in ("discord", "discordcanary", "discordptb"):
        for root in (appdata, local):
            cache_dir = os.path.join(root, base_name, "Cache")
            code_cache = os.path.join(root, base_name, "Code Cache")
            gpu_cache = os.path.join(root, base_name, "GPUCache")
            for d in (cache_dir, code_cache, gpu_cache):
                if os.path.isdir(d):
                    targets.append(d)

    if not targets:
        warning("No Discord cache found")
        return {"freed": 0, "files": 0, "ok": True}

    spinner = Spinner(f"Cleaning Discord cache ({len(targets)} dirs)...")
    spinner.start()

    freed = 0
    count = 0
    for t in targets:
        f, c = _safe_remove_tree(t)
        freed += f
        count += c

    spinner.stop()
    success(f"Discord cache cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": True}


def clean_spotify_cache():
    local = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")

    targets = []
    paths_to_check = [
        os.path.join(local, "Spotify", "Storage"),
        os.path.join(local, "Spotify", "Data"),
        os.path.join(appdata, "Spotify", "Storage"),
        os.path.join(local, "Packages"),
    ]

    for p in paths_to_check[:3]:
        if os.path.isdir(p):
            targets.append(p)

    uwp_base = paths_to_check[3]
    if os.path.isdir(uwp_base):
        try:
            for entry in os.scandir(uwp_base):
                if entry.is_dir() and "spotify" in entry.name.lower():
                    local_cache = os.path.join(entry.path, "LocalCache")
                    if os.path.isdir(local_cache):
                        targets.append(local_cache)
        except (PermissionError, OSError):
            pass

    if not targets:
        warning("No Spotify cache found")
        return {"freed": 0, "files": 0, "ok": True}

    detail(f"Found {len(targets)} Spotify cache directories")
    freed, count = _parallel_delete_trees(targets)
    success(f"Spotify cache cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": True}


def clean_steam_cache():
    program_files = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    steam_base = os.path.join(program_files, "Steam")

    targets = []
    shader_dirs = [
        os.path.join(steam_base, "shadercache"),
        os.path.join(steam_base, "depotcache"),
        os.path.join(steam_base, "appcache", "httpcache"),
        os.path.join(steam_base, "logs"),
    ]

    for d in shader_dirs:
        if os.path.isdir(d):
            targets.append(d)

    local = os.environ.get("LOCALAPPDATA", "")
    steam_local = os.path.join(local, "Steam", "htmlcache")
    if os.path.isdir(steam_local):
        targets.append(steam_local)

    if not targets:
        warning("No Steam cache found")
        return {"freed": 0, "files": 0, "ok": True}

    detail(f"Found {len(targets)} Steam cache directories")
    freed, count = _parallel_delete_trees(targets)
    success(f"Steam cache cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": True}


def clean_event_logs():
    info("Clearing Windows Event Logs...")
    try:
        result = subprocess.run(
            ["wevtutil", "el"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            warning("Could not enumerate event logs")
            return {"freed": 0, "files": 0, "ok": False}

        logs = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        detail(f"Found {len(logs)} event logs")

        cleared = 0
        for log_name in logs:
            try:
                r = subprocess.run(
                    ["wevtutil", "cl", log_name],
                    capture_output=True, text=True, timeout=10,
                )
                if r.returncode == 0:
                    cleared += 1
            except (subprocess.TimeoutExpired, OSError):
                continue

        success(f"Event Logs cleared — {cleared}/{len(logs)} logs")
        return {"freed": 0, "files": cleared, "ok": True}

    except FileNotFoundError:
        error("wevtutil not found")
        return {"freed": 0, "files": 0, "ok": False}
    except PermissionError:
        warning("Event log clearing requires administrator privileges")
        return {"freed": 0, "files": 0, "ok": False}


def clean_font_cache():
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    local = os.environ.get("LOCALAPPDATA", "")

    targets = []
    font_cache_sys = os.path.join(system_root, "ServiceProfiles", "LocalService", "AppData", "Local", "FontCache")
    font_cache_user = os.path.join(local, "FontCache")

    for fc in (font_cache_sys, font_cache_user):
        if os.path.isdir(fc):
            targets.append(fc)

    fntcache = os.path.join(system_root, "System32", "FNTCACHE.DAT")
    freed = 0
    count = 0

    if targets:
        detail(f"Found {len(targets)} font cache directories")
        freed, count = _parallel_delete_trees(targets)

    if os.path.isfile(fntcache):
        f, ok = _safe_remove_file(fntcache)
        freed += f
        if ok:
            count += 1

    if freed > 0 or count > 0:
        success(f"Font cache cleaned — {format_size(freed)} from {count:,} items")
        return {"freed": freed, "files": count, "ok": True}
    else:
        warning("No font cache found or access denied")
        return {"freed": 0, "files": 0, "ok": count > 0}


def clean_nvidia_cache():
    local = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    temp = tempfile.gettempdir()

    targets = []
    candidates = [
        os.path.join(local, "NVIDIA", "DXCache"),
        os.path.join(local, "NVIDIA", "GLCache"),
        os.path.join(local, "NVIDIA Corporation", "NV_Cache"),
        os.path.join(appdata, "NVIDIA", "ComputeCache"),
        os.path.join(local, "D3DSCache"),
        os.path.join(temp, "NVIDIA Corporation"),
    ]

    for c in candidates:
        if os.path.isdir(c):
            targets.append(c)

    program_data = os.environ.get("ProgramData", r"C:\ProgramData")
    nvidia_pd = os.path.join(program_data, "NVIDIA Corporation", "Downloader")
    if os.path.isdir(nvidia_pd):
        targets.append(nvidia_pd)

    if not targets:
        warning("No NVIDIA cache found")
        return {"freed": 0, "files": 0, "ok": True}

    detail(f"Found {len(targets)} NVIDIA cache directories")
    freed, count = _parallel_delete_trees(targets)
    success(f"NVIDIA cache cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": True}


def clean_teams_cache():
    local = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")

    targets = []

    classic_base = os.path.join(appdata, "Microsoft", "Teams")
    classic_dirs = [
        "Cache", "Code Cache", "GPUCache", "Service Worker",
        "blob_storage", "databases", "IndexedDB", "Local Storage", "tmp",
    ]
    for d in classic_dirs:
        p = os.path.join(classic_base, d)
        if os.path.isdir(p):
            targets.append(p)

    new_base = os.path.join(local, "Packages")
    if os.path.isdir(new_base):
        try:
            for entry in os.scandir(new_base):
                if entry.is_dir() and "msteams" in entry.name.lower():
                    lc = os.path.join(entry.path, "LocalCache")
                    if os.path.isdir(lc):
                        targets.append(lc)
        except (PermissionError, OSError):
            pass

    new_teams = os.path.join(local, "Microsoft", "Teams")
    for sub in ("Cache", "Code Cache", "GPUCache", "blob_storage"):
        p = os.path.join(new_teams, sub)
        if os.path.isdir(p):
            targets.append(p)

    if not targets:
        warning("No Teams cache found")
        return {"freed": 0, "files": 0, "ok": True}

    detail(f"Found {len(targets)} Teams cache directories")
    freed, count = _parallel_delete_trees(targets)
    success(f"Teams cache cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": True}


def clean_pip_cache():
    local = os.environ.get("LOCALAPPDATA", "")
    pip_cache = os.path.join(local, "pip", "cache")

    if not os.path.isdir(pip_cache):
        pip_cache_alt = os.path.join(local, "pip", "Cache")
        if os.path.isdir(pip_cache_alt):
            pip_cache = pip_cache_alt
        else:
            warning("No pip cache found")
            return {"freed": 0, "files": 0, "ok": True}

    info(f"Target: {pip_cache}")
    freed, count, ok = _clean_directory(pip_cache)
    if ok:
        success(f"pip cache cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": ok}


def clean_npm_cache():
    appdata = os.environ.get("APPDATA", "")
    npm_cache = os.path.join(appdata, "npm-cache")

    if not os.path.isdir(npm_cache):
        local = os.environ.get("LOCALAPPDATA", "")
        npm_cache = os.path.join(local, "npm-cache")
        if not os.path.isdir(npm_cache):
            warning("No npm cache found")
            return {"freed": 0, "files": 0, "ok": True}

    info(f"Target: {npm_cache}")
    freed, count, ok = _clean_directory(npm_cache)
    if ok:
        success(f"npm cache cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": ok}


def clean_thumbnails():
    local = os.environ.get("LOCALAPPDATA", "")
    thumb_dir = os.path.join(local, "Microsoft", "Windows", "Explorer")

    if not os.path.isdir(thumb_dir):
        warning("Thumbnail cache directory not found")
        return {"freed": 0, "files": 0, "ok": True}

    spinner = Spinner("Scanning thumbnail cache...")
    spinner.start()
    files = []
    try:
        with os.scandir(thumb_dir) as it:
            for entry in it:
                if entry.is_file(follow_symlinks=False):
                    name_lower = entry.name.lower()
                    if name_lower.startswith("thumbcache_") or name_lower.startswith("iconcache_"):
                        files.append(entry.path)
    except (PermissionError, OSError):
        pass
    spinner.stop()

    if not files:
        success("No thumbnail cache files found")
        return {"freed": 0, "files": 0, "ok": True}

    detail(f"Found {len(files)} thumbnail cache files")
    freed, count = _parallel_delete_files(files)
    success(f"Thumbnail cache cleaned — {format_size(freed)} from {count:,} files")
    return {"freed": freed, "files": count, "ok": True}


def clean_installer_cache():
    system_root = os.environ.get("SystemRoot", r"C:\Windows")

    targets = []
    installer_tmp = os.path.join(system_root, "Installer", "$PatchCache$")
    if os.path.isdir(installer_tmp):
        targets.append(installer_tmp)

    temp_installer = os.path.join(system_root, "Temp", "msiredist")
    if os.path.isdir(temp_installer):
        targets.append(temp_installer)

    if not targets:
        warning("No installer cache found")
        return {"freed": 0, "files": 0, "ok": True}

    detail(f"Found {len(targets)} installer cache directories")
    freed, count = _parallel_delete_trees(targets)
    success(f"Installer cache cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": True}


def clean_recent_files():
    appdata = os.environ.get("APPDATA", "")

    targets = []
    recent = os.path.join(appdata, "Microsoft", "Windows", "Recent")
    if os.path.isdir(recent):
        targets.append(recent)

    auto_dest = os.path.join(recent, "AutomaticDestinations")
    custom_dest = os.path.join(recent, "CustomDestinations")
    for d in (auto_dest, custom_dest):
        if os.path.isdir(d):
            targets.append(d)

    if not targets:
        warning("No recent files cache found")
        return {"freed": 0, "files": 0, "ok": True}

    spinner = Spinner("Cleaning recent files and jump lists...")
    spinner.start()
    freed = 0
    count = 0
    for t in targets:
        try:
            with os.scandir(t) as it:
                for entry in it:
                    if entry.is_file(follow_symlinks=False):
                        f, ok = _safe_remove_file(entry.path)
                        freed += f
                        if ok:
                            count += 1
        except (PermissionError, OSError):
            continue
    spinner.stop()

    success(f"Recent files cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": True}


def clean_crash_dumps():
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    local = os.environ.get("LOCALAPPDATA", "")
    user_profile = os.environ.get("USERPROFILE", "")

    targets_dirs = []
    targets_files = []

    minidump = os.path.join(system_root, "Minidump")
    if os.path.isdir(minidump):
        targets_dirs.append(minidump)

    memory_dmp = os.path.join(system_root, "MEMORY.DMP")
    if os.path.isfile(memory_dmp):
        targets_files.append(memory_dmp)

    live_dumps = os.path.join(system_root, "LiveKernelReports")
    if os.path.isdir(live_dumps):
        targets_dirs.append(live_dumps)

    crash_dumps_user = os.path.join(local, "CrashDumps")
    if os.path.isdir(crash_dumps_user):
        targets_dirs.append(crash_dumps_user)

    if not targets_dirs and not targets_files:
        warning("No crash dumps found")
        return {"freed": 0, "files": 0, "ok": True}

    freed = 0
    count = 0

    if targets_dirs:
        detail(f"Found {len(targets_dirs)} crash dump directories")
        f, c = _parallel_delete_trees(targets_dirs)
        freed += f
        count += c

    for fp in targets_files:
        f, ok = _safe_remove_file(fp)
        freed += f
        if ok:
            count += 1

    success(f"Crash dumps cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": True}


def clean_vscode_cache():
    appdata = os.environ.get("APPDATA", "")
    local = os.environ.get("LOCALAPPDATA", "")

    targets = []

    for app_name in ("Code", "Code - Insiders"):
        base = os.path.join(appdata, app_name)
        for sub in ("Cache", "CachedData", "CachedExtensions", "CachedExtensionVSIXs",
                     "Code Cache", "GPUCache", "logs"):
            p = os.path.join(base, sub)
            if os.path.isdir(p):
                targets.append(p)

        local_base = os.path.join(local, app_name)
        for sub in ("Cache", "Code Cache", "GPUCache"):
            p = os.path.join(local_base, sub)
            if os.path.isdir(p):
                targets.append(p)

    if not targets:
        warning("No VS Code cache found")
        return {"freed": 0, "files": 0, "ok": True}

    detail(f"Found {len(targets)} VS Code cache directories")
    freed, count = _parallel_delete_trees(targets)
    success(f"VS Code cache cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": True}


def clean_java_cache():
    local = os.environ.get("LOCALAPPDATA", "")
    user_profile = os.environ.get("USERPROFILE", "")
    appdata = os.environ.get("APPDATA", "")

    targets = []
    candidates = [
        os.path.join(local, "Sun", "Java", "Deployment", "cache"),
        os.path.join(appdata, ".java", "cache"),
        os.path.join(user_profile, ".gradle", "caches"),
        os.path.join(user_profile, ".m2", "repository"),
    ]

    for c in candidates:
        if os.path.isdir(c):
            targets.append(c)

    if not targets:
        warning("No Java cache found")
        return {"freed": 0, "files": 0, "ok": True}

    detail(f"Found {len(targets)} Java/build cache directories")
    freed, count = _parallel_delete_trees(targets)
    success(f"Java cache cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": True}


def clean_dx_shader_cache():
    local = os.environ.get("LOCALAPPDATA", "")

    targets = []
    dx_cache = os.path.join(local, "D3DSCache")
    if os.path.isdir(dx_cache):
        targets.append(dx_cache)

    amd_cache = os.path.join(local, "AMD", "DxCache")
    if os.path.isdir(amd_cache):
        targets.append(amd_cache)

    amd_gl = os.path.join(local, "AMD", "GLCache")
    if os.path.isdir(amd_gl):
        targets.append(amd_gl)

    intel_cache = os.path.join(local, "Intel", "ShaderCache")
    if os.path.isdir(intel_cache):
        targets.append(intel_cache)

    if not targets:
        warning("No DirectX/GPU shader cache found")
        return {"freed": 0, "files": 0, "ok": True}

    detail(f"Found {len(targets)} shader cache directories")
    freed, count = _parallel_delete_trees(targets)
    success(f"DirectX shader cache cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": True}


def clean_delivery_optimization():
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    do_cache = os.path.join(system_root, "SoftwareDistribution", "DeliveryOptimization")

    if not os.path.isdir(do_cache):
        warning("No Delivery Optimization cache found")
        return {"freed": 0, "files": 0, "ok": True}

    info(f"Target: {do_cache}")
    freed, count, ok = _clean_directory(do_cache)
    if ok:
        success(f"Delivery Optimization cleaned — {format_size(freed)} from {count:,} items")
    else:
        warning("Could not access Delivery Optimization cache (requires Admin)")
    return {"freed": freed, "files": count, "ok": ok}


def clean_telegram_cache():
    appdata = os.environ.get("APPDATA", "")
    local = os.environ.get("LOCALAPPDATA", "")
    user_profile = os.environ.get("USERPROFILE", "")

    targets = []

    tdesktop = os.path.join(appdata, "Telegram Desktop", "tdata", "user_data")
    if os.path.isdir(tdesktop):
        targets.append(tdesktop)

    tdesktop_cache = os.path.join(appdata, "Telegram Desktop", "tdata", "cache")
    if os.path.isdir(tdesktop_cache):
        targets.append(tdesktop_cache)

    for td_sub in ("media_cache", "tmp"):
        p = os.path.join(appdata, "Telegram Desktop", "tdata", td_sub)
        if os.path.isdir(p):
            targets.append(p)

    uwp_base = os.path.join(local, "Packages")
    if os.path.isdir(uwp_base):
        try:
            for entry in os.scandir(uwp_base):
                if entry.is_dir() and "telegram" in entry.name.lower():
                    lc = os.path.join(entry.path, "LocalCache")
                    if os.path.isdir(lc):
                        targets.append(lc)
        except (PermissionError, OSError):
            pass

    if not targets:
        warning("No Telegram cache found")
        return {"freed": 0, "files": 0, "ok": True}

    detail(f"Found {len(targets)} Telegram cache directories")
    freed, count = _parallel_delete_trees(targets)
    success(f"Telegram cache cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": True}


def clean_error_reports():
    local = os.environ.get("LOCALAPPDATA", "")
    program_data = os.environ.get("ProgramData", r"C:\ProgramData")

    targets = []
    wer_paths = [
        os.path.join(local, "Microsoft", "Windows", "WER", "ReportArchive"),
        os.path.join(local, "Microsoft", "Windows", "WER", "ReportQueue"),
        os.path.join(local, "Microsoft", "Windows", "WER", "Temp"),
        os.path.join(program_data, "Microsoft", "Windows", "WER", "ReportArchive"),
        os.path.join(program_data, "Microsoft", "Windows", "WER", "ReportQueue"),
        os.path.join(program_data, "Microsoft", "Windows", "WER", "Temp"),
    ]

    for p in wer_paths:
        if os.path.isdir(p):
            targets.append(p)

    if not targets:
        warning("No Windows Error Reports found")
        return {"freed": 0, "files": 0, "ok": True}

    detail(f"Found {len(targets)} WER directories")
    freed, count = _parallel_delete_trees(targets)
    success(f"Error reports cleaned — {format_size(freed)} from {count:,} items")
    return {"freed": freed, "files": count, "ok": True}


TASKS = {
    "temp_win": ("Windows Temp Files", clean_windows_temp),
    "temp_user": ("User Temp Files", clean_user_temp),
    "prefetch": ("Prefetch Data", clean_prefetch),
    "recycle": ("Recycle Bin", empty_recycle_bin),
    "junk": ("Junk / Log / Cache Files", clean_junk_files),
    "browser": ("Browser Cache", clean_browser_cache),
    "dns": ("DNS Cache Flush", flush_dns),
    "winupdate": ("Windows Update Cache", clean_windows_update),
    "discord": ("Discord Cache", clean_discord_cache),
    "spotify": ("Spotify Cache", clean_spotify_cache),
    "steam": ("Steam Cache", clean_steam_cache),
    "eventlogs": ("Windows Event Logs", clean_event_logs),
    "fontcache": ("Font Cache", clean_font_cache),
    "nvidia": ("NVIDIA Shader Cache", clean_nvidia_cache),
    "teams": ("Microsoft Teams Cache", clean_teams_cache),
    "pip": ("pip Cache", clean_pip_cache),
    "npm": ("npm Cache", clean_npm_cache),
    "thumbnails": ("Thumbnail Cache", clean_thumbnails),
    "installer": ("Windows Installer Cache", clean_installer_cache),
    "recent": ("Recent Files & Jump Lists", clean_recent_files),
    "crashdumps": ("Crash Dumps", clean_crash_dumps),
    "vscode": ("VS Code Cache", clean_vscode_cache),
    "java": ("Java / Gradle / Maven Cache", clean_java_cache),
    "dxcache": ("DirectX / GPU Shader Cache", clean_dx_shader_cache),
    "delivery": ("Delivery Optimization Cache", clean_delivery_optimization),
    "telegram": ("Telegram Cache", clean_telegram_cache),
    "wer": ("Windows Error Reports", clean_error_reports),
}

QUICK_TASKS = ["temp_win", "temp_user", "prefetch", "recycle", "dns", "thumbnails"]
DEEP_TASKS = [
    "temp_win", "temp_user", "prefetch", "recycle", "dns",
    "junk", "browser", "winupdate", "discord", "spotify",
    "steam", "eventlogs", "fontcache", "nvidia", "teams",
    "pip", "npm", "thumbnails", "installer", "recent",
    "crashdumps", "vscode", "java", "dxcache", "delivery",
    "telegram", "wer",
]


def run_tasks(task_keys):
    from cleaner.display import header, summary_table

    start = time.perf_counter()
    results = []

    for key in task_keys:
        if key not in TASKS:
            continue
        label, func = TASKS[key]
        header(label)
        try:
            result = func()
            result["name"] = label
        except Exception as e:
            error(f"Failed: {e}")
            result = {"name": label, "freed": 0, "files": 0, "ok": False}
        results.append(result)

    elapsed = time.perf_counter() - start
    summary_table(results, elapsed=elapsed)
