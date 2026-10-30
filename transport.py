import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time


class WorkerClient:
    def __init__(self, app_id, demo=False, library=False):
        args = [sys.executable]
        if getattr(sys, "frozen", False):
            worker = Path(sys.executable).with_name("AchievementDeskWorker.exe")
            if not worker.is_file():
                raise RuntimeError("AchievementDeskWorker.exe is missing. Extract the complete portable folder.")
            args = [str(worker)]
        else:
            args += ["-u", str(Path(__file__).with_name("app.py"))]
        args += ["--library"] if library else ["--worker", str(app_id)]
        if demo:
            args += ["--demo"]
        self.process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.messages = queue.Queue()
        self.lock = threading.Lock()
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        try:
            for line in self.process.stdout:
                try:
                    value = json.loads(line)
                    if isinstance(value, dict) and ("ok" in value or value.get("progress")):
                        self.messages.put(value)
                except ValueError:
                    pass  # A native library may print diagnostic lines.
        finally:
            self.messages.put(dict(ok=False, error="Steam connection closed unexpectedly. Reload the game."))

    def receive(self, timeout=50, progress=None):
        deadline = time.monotonic() + timeout
        while True:
            try:
                reply = self.messages.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty:
                raise TimeoutError("The Steam connection timed out. Check Steam before retrying.") from None
            if reply.get("progress"):
                if progress:
                    progress(reply)
                continue
            if not reply.get("ok"):
                raise RuntimeError(reply.get("error", "Steam request failed."))
            return reply

    def exchange(self, request):
        with self.lock:
            if self.process.poll() is not None:
                raise RuntimeError("Steam connection ended. Reload the game.")
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            return self.receive()

    def close(self):
        try:
            if self.process.poll() is None:
                self.process.stdin.write('{"command":"close"}\n')
                self.process.stdin.flush()
                self.process.wait(timeout=2)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            self.process.kill()
            self.process.wait(timeout=2)
        finally:
            for stream in (self.process.stdin, self.process.stdout):
                if stream:
                    stream.close()

    def cancel(self):
        """Terminate a read helper. The UI never exposes this during apply."""
        try:
            if self.process.poll() is None:
                self.process.kill()
        except OSError:
            pass


class GameClient:
    """UI handle without an idle native Steam session.

    Every real read/apply owns and closes its helper before returning a result.
    Demo data keeps its synthetic worker to retain edits, without using Steam.
    """
    def __init__(self, app_id, demo=False, worker_factory=None):
        self.app_id, self.demo = app_id, demo
        self.worker_factory = worker_factory or WorkerClient
        self._demo_client = None
        self._active_client = None
        self._cancelled = False

    def receive(self):
        return self.exchange({"command": "read"})

    def exchange(self, request):
        if self._cancelled:
            raise RuntimeError("Read cancelled.")
        if request.get("command") not in ("read", "apply"):
            raise ValueError("Unknown game operation.")
        if self.demo:
            if self._demo_client is None:
                client = self.worker_factory(self.app_id, True)
                try:
                    initial = client.receive()
                except BaseException:
                    client.close()
                    raise
                self._demo_client = client
                if request["command"] == "read":
                    return initial
            return self._demo_client.exchange(request)
        client = self.worker_factory(self.app_id, False)
        self._active_client = client
        try:
            if self._cancelled:
                client.cancel()
                raise RuntimeError("Read cancelled.")
            initial = client.receive()
            if request["command"] == "read":
                return initial
            if initial["account_id"] != str(request.get("account_id")):
                raise ValueError("Steam account changed. Reload and review again.")
            return client.exchange(request)
        finally:
            client.close()
            self._active_client = None

    def cancel(self):
        self._cancelled = True
        if self._active_client:
            self._active_client.cancel()

    def reset_cancel(self):
        self._cancelled = False

    def close(self):
        if self._demo_client is not None:
            self._demo_client.close()
            self._demo_client = None
