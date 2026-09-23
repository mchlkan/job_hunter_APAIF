import argparse
import os
import signal
import subprocess
import sys
import threading

sys.stdout.reconfigure(line_buffering=True)  # visible immediately even when piped/redirected

FRONTEND_DIR = "frosted-editorial-job-app-source"
BACKEND_PORT = "8123"


def _handle_signal(signum, frame):
    # SIGTERM (plain `kill`) and SIGHUP (closing the terminal) don't become
    # KeyboardInterrupt in Python the way SIGINT/ctrl-c does — without this,
    # the cleanup in main()'s `finally` never runs and the three child
    # processes are orphaned. sys.exit() unwinds through that finally like
    # any other exception, so no custom exception type is needed here.
    sys.exit(0)


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGHUP, _handle_signal)


def _stream(proc: subprocess.Popen, name: str) -> None:
    for line in proc.stdout:
        print(f"[{name}] {line}", end="", flush=True)


def _spawn(name: str, cmd: list, cwd: str = None, env: dict = None) -> subprocess.Popen:
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    threading.Thread(target=_stream, args=(proc, name), daemon=True).start()
    return proc


def main():
    parser = argparse.ArgumentParser(
        description="Start the backend API, frontend, and data-refresh scheduler together."
    )
    parser.add_argument("--prod", action="store_true",
                         help="build the frontend and serve it with its production Node server, "
                              "instead of the vite dev server")
    parser.add_argument("--no-scheduler", action="store_true",
                         help="skip the background collection/CV scheduler")
    args = parser.parse_args()

    node_modules = os.path.join(FRONTEND_DIR, "node_modules")
    if not os.path.isdir(node_modules):
        print(f"[start] {node_modules} missing, running npm i...")
        subprocess.run(["npm", "i"], cwd=FRONTEND_DIR, check=True)

    procs = []

    def cleanup():
        print("\n[start] stopping...")
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    try:
        procs.append(_spawn(
            "api", [sys.executable, "-m", "uvicorn", "api.main:app", "--port", BACKEND_PORT],
        ))

        if args.prod:
            print("[start] building frontend for production...")
            subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIR, check=True)
            procs.append(_spawn("web", ["node", ".output/server/index.mjs"], cwd=FRONTEND_DIR))
            frontend_url = "http://localhost:3000"
        else:
            procs.append(_spawn("web", ["npm", "run", "dev"], cwd=FRONTEND_DIR))
            frontend_url = "http://localhost:8080"

        if not args.no_scheduler:
            procs.append(_spawn("scheduler", [sys.executable, "scheduler.py"]))

        print(f"\n[start] backend:  http://localhost:{BACKEND_PORT}")
        print(f"[start] frontend: {frontend_url}")
        print("[start] ctrl-c to stop everything\n")

        for proc in procs:
            proc.wait()

    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
