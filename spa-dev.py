#!/usr/bin/env python3
"""
spa-dev: Development launcher for Open LPR backend + Next.js SPA.

Starts both the Django REST API and the Next.js frontend with a
split-pane terminal UI — API logs on the left, SPA logs on the right.

Usage:
    python spa-dev.py [--backend-port PORT] [--spa-port PORT] [--no-tui]

Falls back to plain stdout mode if no terminal is available.
"""

import os
import shutil
import sys
import signal
import subprocess
import threading
import argparse
import time
import collections

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(SCRIPT_DIR, ".venv")
SPA_DIR = os.path.join(SCRIPT_DIR, "single-page-ui")

HAS_CURSES = False
try:
    import curses
    HAS_CURSES = True
except ImportError:
    pass

COLOR_BACKEND = 1
COLOR_SPA = 2
COLOR_HEADER = 3
COLOR_ERROR = 4
COLOR_BORDER = 5

TAG_BACKEND = "API"
TAG_SPA = "SPA"

ANSI_CYAN = "\033[36m"
ANSI_GREEN = "\033[32m"
ANSI_RED = "\033[31m"
ANSI_YELLOW = "\033[33m"
ANSI_DIM = "\033[2m"
ANSI_BOLD = "\033[1m"
ANSI_RESET = "\033[0m"

TAG_ANSI = {TAG_BACKEND: ANSI_CYAN, TAG_SPA: ANSI_GREEN}

MAX_LINES = 5000


def has_terminal():
    return (
        hasattr(sys.stdin, "isatty") and sys.stdin.isatty()
        and hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    )


def find_python():
    venv_python = os.path.join(VENV_DIR, "bin", "python")
    if os.path.isfile(venv_python):
        return venv_python
    return sys.executable


def find_npm():
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        p = os.path.join(path_dir, "npm")
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def check_prerequisites():
    errors = []
    python = find_python()
    try:
        with open(python):
            pass
    except (OSError, IOError):
        errors.append(f"Python not found: {python}")
    if not os.path.isdir(SPA_DIR):
        errors.append(f"SPA directory not found: {SPA_DIR}")
    else:
        if not os.path.isdir(os.path.join(SPA_DIR, "node_modules")):
            errors.append(f"SPA deps not installed. Run: cd {SPA_DIR} && npm install")
    if not find_npm():
        errors.append("npm not found in PATH")
    return errors


def find_pids_on_port(port):
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return [int(p) for p in result.stdout.strip().split("\n") if p.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return []


def kill_port(port):
    pids = find_pids_on_port(port)
    if not pids:
        return False
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    time.sleep(0.5)
    remaining = find_pids_on_port(port)
    for pid in remaining:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    time.sleep(0.3)
    return len(find_pids_on_port(port)) == 0


def kill_all_dev_ports(backend_port, spa_port):
    killed = []
    for port in [backend_port, spa_port]:
        pids = find_pids_on_port(port)
        if pids:
            if kill_port(port):
                killed.append(port)
    cleanup_nextjs_dev_state()
    return killed


def cleanup_nextjs_dev_state():
    next_dev_dir = os.path.join(SPA_DIR, ".next", "dev")
    if os.path.isdir(next_dev_dir):
        shutil.rmtree(next_dev_dir, ignore_errors=True)


def check_port_conflicts(backend_port, spa_port):
    conflicts = {}
    for label, port in [("Backend", backend_port), ("SPA", spa_port)]:
        pids = find_pids_on_port(port)
        if pids:
            conflicts[label] = (port, pids)
    return conflicts


def prompt_kill_conflicts(conflicts):
    if not conflicts:
        return True
    parts = []
    for label, (port, pids) in conflicts.items():
        parts.append(f"  {label} port {port}: PID{'s' if len(pids) > 1 else ''} {', '.join(str(p) for p in pids)}")
    print(f"{ANSI_YELLOW}{ANSI_BOLD}Port conflicts detected:{ANSI_RESET}")
    for p in parts:
        print(f"{ANSI_YELLOW}{p}{ANSI_RESET}")
    print()
    try:
        answer = input(f"{ANSI_BOLD}Kill existing processes? [Y/n] {ANSI_RESET}").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if answer in ("", "y", "yes"):
        for label, (port, pids) in conflicts.items():
            if kill_port(port):
                print(f"{ANSI_GREEN}  Killed processes on port {port}{ANSI_RESET}")
            else:
                print(f"{ANSI_RED}  Failed to kill processes on port {port}{ANSI_RESET}")
                return False
        cleanup_nextjs_dev_state()
        time.sleep(0.3)
        return True
    return False


def start_process(cmd, cwd, env_extra=None):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        preexec_fn=os.setsid,
    )


def stream_output(proc, tag, color_pair, log_deque, lock, ready_event):
    try:
        for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="replace").rstrip()
            with lock:
                log_deque.append(line)
                if len(log_deque) > MAX_LINES:
                    log_deque.popleft()
            if ready_event and tag == TAG_BACKEND:
                low = line.lower()
                if "starting development server" in low or ("watching for file changes" in low):
                    ready_event.set()
    except ValueError:
        pass
    finally:
        with lock:
            exit_code = proc.poll()
            log_deque.append(f"--- process exited (code {exit_code}) ---")


def _truncate(text, width):
    if len(text) > width:
        return text[:width]
    return text


def draw_pane(stdscr, log_deque, lock, top, left, height, width, title, color, procs_state):
    try:
        for y in range(top, top + height):
            stdscr.addstr(y, left, " " * width, curses.color_pair(COLOR_BORDER))
    except curses.error:
        pass

    border_ch = " "
    for y in range(top, top + height):
        try:
            stdscr.addch(y, left + width - 1, curses.ACS_VLINE, curses.color_pair(COLOR_BORDER))
        except curses.error:
            pass

    inner_w = width - 2
    title_bar = f" {title} "
    if procs_state:
        title_bar += f"  {procs_state} "
    title_bar = _truncate(title_bar, inner_w)
    try:
        stdscr.addstr(top, left + 1, title_bar, curses.color_pair(color) | curses.A_BOLD)
    except curses.error:
        pass

    body_top = top + 1
    body_height = height - 1

    with lock:
        visible = list(log_deque)[-body_height:]

    for i, line in enumerate(visible):
        row = body_top + i
        if row >= top + height:
            break
        is_exit = "--- process exited" in line
        c = COLOR_ERROR if is_exit else color
        try:
            stdscr.addstr(row, left + 1, _truncate(line, inner_w), curses.color_pair(c))
        except curses.error:
            pass


def run_tui(stdscr, backend_proc, spa_proc, backend_log, spa_log, lock, start_time, backend_port, spa_port):
    curses.curs_set(0)
    stdscr.nodelay(True)

    curses.init_pair(COLOR_BACKEND, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(COLOR_SPA, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(COLOR_HEADER, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(COLOR_ERROR, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(COLOR_BORDER, curses.COLOR_BLUE, curses.COLOR_BLACK)

    while True:
        try:
            key = stdscr.getch()
            if key in (ord("q"), ord("Q")):
                break
            if key in (ord("k"), ord("K")):
                killed = kill_all_dev_ports(backend_port, spa_port)
                with lock:
                    if killed:
                        backend_log.append(f"--- killed stale processes on port{'s' if len(killed) > 1 else ''} {', '.join(str(p) for p in killed)} ---")
                    else:
                        backend_log.append("--- no stale processes found ---")
        except curses.error:
            pass

        stdscr.erase()
        h, w = stdscr.getmaxyx()

        header = f" Open LPR Dev Server  |  API: localhost:{backend_port}  |  SPA: localhost:{spa_port}  |  Started {time.strftime('%H:%M:%S', time.localtime(start_time))} "
        right = " [k] Kill stale  [q] Quit "
        try:
            stdscr.addstr(0, 0, _truncate(header, w), curses.color_pair(COLOR_HEADER) | curses.A_BOLD)
            stdscr.addstr(0, max(len(_truncate(header, w)), w - len(right) - 1), right, curses.color_pair(COLOR_HEADER))
            stdscr.chgat(0, 0, w, curses.A_REVERSE | curses.color_pair(COLOR_HEADER))
        except curses.error:
            pass

        pane_top = 1
        pane_height = h - pane_top
        half_w = w // 2
        right_left = half_w
        right_width = w - half_w

        be_rc = backend_proc.poll()
        spa_rc = spa_proc.poll()
        be_state = f"RUNNING" if be_rc is None else f"EXITED({be_rc})"
        spa_state = f"RUNNING" if spa_rc is None else f"EXITED({spa_rc})"

        draw_pane(stdscr, backend_log, lock, pane_top, 0, pane_height, half_w,
                  f"[API]", COLOR_BACKEND, be_state)
        draw_pane(stdscr, spa_log, lock, pane_top, right_left, pane_height, right_width,
                  f"[SPA]", COLOR_SPA, spa_state)

        stdscr.refresh()

        all_dead = be_rc is not None and spa_rc is not None
        if all_dead:
            time.sleep(3)
            break

        time.sleep(0.08)


def run_plain(backend_proc, spa_proc, backend_log, spa_log, lock, start_time, stop_event, backend_port, spa_port):
    last_be = 0
    last_spa = 0
    print(f"{ANSI_BOLD} Open LPR Dev Server started {time.strftime('%H:%M:%S', time.localtime(start_time))} {ANSI_RESET}")
    print(f"{ANSI_DIM} Press Ctrl+C to stop  |  'k' + Enter to kill stale processes{ANSI_RESET}")
    print()

    def kill_input():
        while not stop_event.is_set():
            try:
                ch = sys.stdin.readline()
                if ch and ch.strip().lower() == "k":
                    killed = kill_all_dev_ports(backend_port, spa_port)
                    if killed:
                        print(f"{ANSI_YELLOW}  Killed stale processes on port{'s' if len(killed) > 1 else ''} {', '.join(str(p) for p in killed)}{ANSI_RESET}")
                    else:
                        print(f"{ANSI_DIM}  No stale processes found{ANSI_RESET}")
            except Exception:
                break

    if has_terminal():
        kt = threading.Thread(target=kill_input, daemon=True)
        kt.start()

    while not stop_event.is_set():
        with lock:
            be_len = len(backend_log)
            spa_len = len(spa_log)

        if be_len > last_be:
            with lock:
                new = list(backend_log)[last_be:be_len]
            for line in new:
                print(f"{ANSI_CYAN}{ANSI_BOLD} [API] {ANSI_RESET}{ANSI_CYAN}{line}{ANSI_RESET}")
            last_be = be_len

        if spa_len > last_spa:
            with lock:
                new = list(spa_log)[last_spa:spa_len]
            for line in new:
                print(f"{ANSI_GREEN}{ANSI_BOLD} [SPA] {ANSI_RESET}{ANSI_GREEN}{line}{ANSI_RESET}")
            last_spa = spa_len

        all_dead = backend_proc.poll() is not None and spa_proc.poll() is not None
        if all_dead:
            time.sleep(1)
            break

        time.sleep(0.1)


def main():
    parser = argparse.ArgumentParser(description="Start Open LPR dev servers")
    parser.add_argument("--backend-port", type=int, default=8000, help="Django backend port (default: 8000)")
    parser.add_argument("--spa-port", type=int, default=3000, help="Next.js SPA port (default: 3000)")
    parser.add_argument("--no-tui", action="store_true", help="Disable TUI, use plain stdout output")
    args = parser.parse_args()

    errors = check_prerequisites()
    if errors:
        print("Prerequisites check failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    conflicts = check_port_conflicts(args.backend_port, args.spa_port)
    if conflicts:
        if not prompt_kill_conflicts(conflicts):
            print(f"{ANSI_RED}Cannot start — ports still in use.{ANSI_RESET}")
            sys.exit(1)

    python = find_python()
    npm = find_npm()

    backend_log = collections.deque(maxlen=MAX_LINES)
    spa_log = collections.deque(maxlen=MAX_LINES)
    lock = threading.Lock()
    start_time = time.time()
    stop_event = threading.Event()

    backend_cmd = [python, "manage.py", "runserver", str(args.backend_port)]
    spa_cmd = [npm, "run", "dev", "--", "--port", str(args.spa_port)]
    backend_env = {
        "CORS_ALLOWED_ORIGINS": f"http://localhost:{args.spa_port}",
    }
    spa_env = {
        "PORT": str(args.spa_port),
        "BACKEND_API_URL": f"http://localhost:{args.backend_port}",
    }

    print(f"Starting backend: {' '.join(backend_cmd)}")
    print(f"Starting SPA:     {' '.join(spa_cmd)}")
    print()

    cleanup_nextjs_dev_state()
    backend_proc = start_process(backend_cmd, SCRIPT_DIR, backend_env)
    spa_proc = start_process(spa_cmd, SPA_DIR, spa_env)

    bt = threading.Thread(
        target=stream_output,
        args=(backend_proc, TAG_BACKEND, COLOR_BACKEND, backend_log, lock, None),
        daemon=True,
    )
    st = threading.Thread(
        target=stream_output,
        args=(spa_proc, TAG_SPA, COLOR_SPA, spa_log, lock, None),
        daemon=True,
    )
    bt.start()
    st.start()

    def shutdown(signum=None, frame=None):
        stop_event.set()
        for proc in [backend_proc, spa_proc]:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    proc.kill()
                except Exception:
                    pass
        for proc in [backend_proc, spa_proc]:
            try:
                proc.wait(timeout=5)
            except Exception:
                pass

    signal.signal(signal.SIGTERM, shutdown)

    use_tui = HAS_CURSES and has_terminal() and not args.no_tui

    try:
        if use_tui:
            curses.wrapper(
                lambda stdscr: run_tui(
                    stdscr, backend_proc, spa_proc,
                    backend_log, spa_log, lock,
                    start_time, args.backend_port, args.spa_port,
                )
            )
        else:
            run_plain(backend_proc, spa_proc, backend_log, spa_log, lock, start_time, stop_event, args.backend_port, args.spa_port)
    except KeyboardInterrupt:
        pass
    finally:
        shutdown()
        print(f"\n{ANSI_DIM}Dev servers stopped.{ANSI_RESET}")


if __name__ == "__main__":
    main()
