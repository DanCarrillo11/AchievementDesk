from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from domain import Achievement, plan_changes
from library import Game
from transport import GameClient, WorkerClient
from catalog import update_catalog
from widgets import AchievementList

BG, PANEL, INK, MUTED, ACCENT = "#101923", "#1b2838", "#e5edf5", "#9aafc3", "#66c0f4"


class Desk(tk.Tk):
    def __init__(self, demo=False, hidden=False):
        super().__init__()
        if hidden:
            self.withdraw()  # Automated construction tests must never show a window.
        self.title("Achievement Desk — 0.3.0 Preview")
        self.geometry("1180x790")
        self.minsize(1040, 720)
        self.configure(bg=BG)
        self.demo, self.client, self.game = demo, None, None
        self.rows, self.desired = [], {}
        self.account_id = None
        self.library_account_id = None
        self.library, self.visible_games = [], []
        self.busy, self.spoilers = False, False
        self.callbacks = queue.Queue()
        self.controls = []
        self.data_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.cwd()))) / "AchievementDesk"
        self._style()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.bind("<Control-f>", lambda _: self.search_entry.focus_set())
        self.bind("<Control-r>", lambda _: self.refresh())
        self.after(75, self._poll)
        if not hidden:
            self.after(100, self.load_library)

    def _style(self):
        self.option_add("*Font", "{Segoe UI} 10")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=INK)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("TButton", background="#293c50", foreground=INK, borderwidth=0, padding=(12, 8), focusthickness=1, focuscolor=ACCENT)
        style.map("TButton", background=[("active", "#36516b"), ("disabled", "#1c2937")], foreground=[("disabled", "#64778a")])
        style.configure("Small.TButton", padding=(8, 5), font=("Segoe UI", 9))
        style.configure("Accent.TButton", background="#3c82b5", foreground="#ffffff", font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#4f9bcf"), ("disabled", "#233c50")], foreground=[("disabled", "#698498")])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=INK,
                        bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL,
                        rowheight=36, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background="#222e3d", foreground=MUTED, padding=9, relief="flat")
        style.map("Treeview", background=[("selected", "#305344")], foreground=[("selected", "#ffffff")])
        style.configure("TEntry", fieldbackground=PANEL, foreground=INK, insertcolor=INK,
                        bordercolor="#344256", lightcolor="#344256", darkcolor="#344256", padding=8)
        style.configure("TCombobox", fieldbackground=PANEL, foreground=INK, background="#263344", padding=7)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", INK)])
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor="#263344", borderwidth=0, thickness=4)
        style.configure("TCheckbutton", background=BG, foreground=MUTED)
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("Switch.TCheckbutton", background=PANEL, padding=3, focuscolor=ACCENT, focusthickness=1)
        style.map("Switch.TCheckbutton", background=[("active", PANEL), ("selected", PANEL)])
        style.layout("Switch.TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
            ("Checkbutton.focus", {"sticky": "nswe", "children": [("Checkbutton.label", {"sticky": "nswe"})]})]})])
        self.option_add("*TCombobox*Listbox.background", PANEL)
        self.option_add("*TCombobox*Listbox.foreground", INK)
        self.option_add("*TCombobox*Listbox.selectBackground", "#30506c")

    def label(self, parent, text, size=10, color=INK, bold=False, **kw):
        widget = tk.Label(parent, text=text, bg=parent.cget("background") if isinstance(parent, tk.Frame) else BG,
                          fg=color, font=("Segoe UI", size, "bold" if bold else "normal"), anchor="w", **kw)
        return widget

    def button(self, parent, text, command, accent=False):
        button = ttk.Button(parent, text=text, command=command, style="Accent.TButton" if accent else "TButton")
        self.controls.append(button)
        return button

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        top = tk.Frame(self, bg="#171f2b", padx=22, pady=15)
        top.grid(row=0, column=0, sticky="ew")
        self.label(top, "ACHIEVEMENT DESK", 16, bold=True).pack(side="left")
        self.label(top, "0.3.0  /  PREVIEW", 9, MUTED).pack(side="left", padx=15)
        self.account_label = self.label(top, "DEMO MODE" if self.demo else "Steam account not loaded", 10, ACCENT, True)
        self.account_label.pack(side="right")
        body = tk.Frame(self, bg=BG)
        body.grid(row=1, column=0, sticky="nsew", padx=18, pady=(16, 0))
        body.rowconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        sidebar = tk.Frame(body, bg="#151f2c", width=285, padx=12, pady=12)
        sidebar.grid(row=0, column=0, sticky="ns", padx=(0, 18))
        sidebar.grid_propagate(False)
        sidebar.columnconfigure(0, weight=1)
        sidebar.rowconfigure(4, weight=1)
        heading = tk.Frame(sidebar, bg="#151f2c")
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.label(heading, "LIBRARY", 11, bold=True).pack(side="left")
        self.library_count = self.label(heading, "0 games", 9, MUTED)
        self.library_count.pack(side="right")
        self.label(sidebar, "Search games or App IDs", 9, MUTED).grid(row=1, column=0, sticky="w", pady=(0, 5))
        self.game_search = tk.StringVar()
        entry = ttk.Entry(sidebar, textvariable=self.game_search)
        entry.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.game_search.trace_add("write", lambda *_: self.filter_games())
        self.library_filter = tk.StringVar(value="All owned games")
        self.library_combo = ttk.Combobox(sidebar, textvariable=self.library_filter, state="readonly",
            values=("All owned games", "Installed", "Not installed"))
        self.library_combo.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self.library_combo.bind("<<ComboboxSelected>>", lambda _: self.filter_games())
        self.controls.append(self.library_combo)
        game_wrap = tk.Frame(sidebar, bg="#151f2c")
        game_wrap.grid(row=4, column=0, sticky="nsew")
        self.games = tk.Listbox(game_wrap, bg="#151f2c", fg=INK, selectbackground="#2c4b65",
                                selectforeground="white", relief="flat", borderwidth=0,
                                highlightthickness=0, exportselection=False, activestyle="none", font=("Segoe UI", 10), height=5)
        self.games.pack(side="left", fill="both", expand=True)
        scroller = ttk.Scrollbar(game_wrap, command=self.games.yview)
        scroller.pack(side="right", fill="y")
        self.games.configure(yscrollcommand=scroller.set)
        self.games.bind("<Double-1>", lambda _: self.open_selected())
        self.games.bind("<Return>", lambda _: self.open_selected())
        self.games.bind("<<ListboxSelect>>", self._library_selected)
        self.selected_game_info = self.label(sidebar, "Select a game to view its achievements", 9, MUTED, wraplength=245)
        self.selected_game_info.grid(row=5, column=0, sticky="ew", pady=(9, 7))
        self.load_button = self.button(sidebar, "Load achievements", self.open_selected, True)
        self.load_button.grid(row=6, column=0, sticky="ew", pady=(0, 8))
        library_actions = tk.Frame(sidebar, bg=BG)
        library_actions.grid(row=7, column=0, sticky="ew", pady=(0, 14))
        self.button(library_actions, "Refresh library", self.load_library).pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.button(library_actions, "Update catalog", self.refresh_catalog).pack(side="left", fill="x", expand=True)
        self.label(sidebar, "LOAD BY APP ID", 9, MUTED, True).grid(row=8, column=0, sticky="w", pady=(0, 5))
        manual = tk.Frame(sidebar, bg="#151f2c")
        manual.grid(row=9, column=0, sticky="ew")
        manual.columnconfigure(0, weight=1)
        self.app_id = tk.StringVar()
        self.app_entry = ttk.Entry(manual, textvariable=self.app_id, width=12)
        self.app_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.button(manual, "Load", self.open_id).grid(row=0, column=1)
        self.label(sidebar, "● Installed   ○ Not installed", 9, MUTED).grid(row=10, column=0, sticky="w", pady=(10, 0))
        main = tk.Frame(body, bg=BG)
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)
        hero = tk.Frame(main, bg=BG)
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.game_title = self.label(hero, "Your achievement library", 22, bold=True, wraplength=680, justify="left")
        self.game_title.pack(anchor="w", fill="x")
        self.game_caption = self.label(hero, "Choose a game from your Steam library to begin.", 10, MUTED)
        self.game_caption.pack(anchor="w", pady=(4, 0))
        hero.bind("<Configure>", lambda event: self.game_title.configure(wraplength=max(350, event.width - 10)))
        overview = tk.Frame(main, bg=BG)
        overview.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        stats = tk.Frame(overview, bg=BG)
        stats.pack(fill="x", pady=(0, 7))
        self.metric = self.label(stats, "0 / 0 unlocked", 12, ACCENT, True)
        self.metric.pack(side="left")
        self.pending_label = self.label(stats, "No pending changes", 10, MUTED)
        self.pending_label.pack(side="right")
        self.progress = ttk.Progressbar(overview, mode="determinate", maximum=100)
        self.progress.pack(fill="x")
        tools = tk.Frame(main, bg=BG)
        tools.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        tools.columnconfigure(0, weight=1)
        self.label(tools, "Search achievements", 9, MUTED).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.search = tk.StringVar()
        self.search_entry = ttk.Entry(tools, textvariable=self.search)
        self.search_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        self.search.trace_add("write", lambda *_: self.render())
        self.status_filter = tk.StringVar(value="All achievements")
        self.filter_combo = ttk.Combobox(tools, textvariable=self.status_filter, state="readonly", width=18,
                                        values=("All achievements", "Locked", "Unlocked", "Pending changes"))
        self.filter_combo.grid(row=1, column=1, sticky="e")
        self.filter_combo.bind("<<ComboboxSelected>>", lambda _: self.render())
        self.controls.append(self.filter_combo)
        self.table = AchievementList(main, self.toggle_achievement, self.show_details)
        self.table.grid(row=3, column=0, sticky="nsew")
        self.details = self.label(main, "ON = unlocked  ·  OFF = locked  ·  Switch changes stay pending until reviewed.", 9, MUTED, wraplength=850)
        self.details.grid(row=4, column=0, sticky="ew", pady=(8, 6))
        preferences = tk.Frame(main, bg=BG)
        preferences.grid(row=5, column=0, sticky="ew", pady=(0, 8))
        self.reveal = tk.BooleanVar(value=False)
        ttk.Checkbutton(preferences, text="Show hidden details", variable=self.reveal,
                        command=lambda: (self.render(), self.show_details())).pack(side="left")
        self.label(preferences, "Ctrl+click to select multiple", 9, MUTED).pack(side="right")
        actions = tk.Frame(main, bg=BG)
        actions.grid(row=6, column=0, sticky="ew", pady=(0, 10))
        self.unlock_button = self.button(actions, "Unlock selected", lambda: self.queue_state(True))
        self.unlock_button.pack(side="left", padx=(0, 6))
        self.lock_button = self.button(actions, "Lock selected", lambda: self.queue_state(False))
        self.lock_button.pack(side="left", padx=(0, 6))
        self.clear_button = self.button(actions, "Discard", self.clear_queue)
        self.clear_button.pack(side="left")
        self.review_button = self.button(actions, "Review changes (0)", self.review, True)
        self.review_button.pack(side="right")
        bottom = tk.Frame(main, bg=BG)
        bottom.grid(row=7, column=0, sticky="ew")
        self.refresh_button = self.button(bottom, "Refresh", self.refresh)
        self.refresh_button.pack(side="left", padx=(0, 6))
        self.export_button = self.button(bottom, "Export", self.export)
        self.export_button.pack(side="left", padx=(0, 6))
        self.steam_button = self.button(bottom, "View on Steam", self.open_steam)
        self.steam_button.pack(side="left")
        self.label(bottom, "Sets & trophies: coming later", 9, MUTED).pack(side="right")
        self.status = self.label(self, "Ready. Selecting or queuing changes does not write to Steam.", 10, MUTED, wraplength=1120)
        self.status.grid(row=2, column=0, sticky="ew", padx=22, pady=(12, 12))
        self._sync_controls()

    def _sync_controls(self):
        for control in self.controls:
            control.state(["disabled"] if self.busy else ["!disabled"])
        self.table.set_busy(self.busy or not self.client)
        if self.busy:
            return
        ready = bool(self.client and self.rows)
        for control, enabled in ((self.load_button, bool(self.games.curselection())),
            (self.unlock_button, ready and bool(self.table.selection())),
            (self.lock_button, ready and bool(self.table.selection())),
            (self.clear_button, bool(self.desired)), (self.review_button, ready and bool(self.desired)),
            (self.refresh_button, bool(self.client)), (self.export_button, bool(self.rows)),
            (self.steam_button, bool(self.game and self.account_id and not self.demo))):
            control.state(["!disabled"] if enabled else ["disabled"])

    def _library_selected(self, _=None):
        selected = self.games.curselection()
        if selected and selected[0] < len(self.visible_games):
            game = self.visible_games[selected[0]]
            self.selected_game_info.config(text=f"App ID {game.app_id}  ·  {'Installed' if game.installed else 'Not installed'}")
        else:
            self.selected_game_info.config(text="Select a game to view its achievements")
        self._sync_controls()

    def _poll(self):
        try:
            while True:
                self.callbacks.get_nowait()()
        except queue.Empty:
            pass
        self.after(75, self._poll)

    def task(self, job, success, uncertain=False):
        if self.busy:
            return
        self.busy = True
        self._sync_controls()
        def finish(value=None, error=None):
            self.busy = False
            self._sync_controls()
            if error:
                if uncertain:
                    self.desired.clear()
                    self.rows.clear()
                    self.render()
                    if self.client:
                        self.client.close()
                        self.client = None
                    error = "The outcome may be partial or unknown. Check Steam and reload the game before retrying.\n\n" + error
                self.status.config(text="Request failed. " + error)
                messagebox.showerror("Steam request", error, parent=self)
            else:
                try:
                    success(value)
                except Exception as exc:
                    self.status.config(text=f"Unable to display the result: {exc}. Reopen the game.")
                    messagebox.showerror("Result unavailable", str(exc), parent=self)
        def execute():
            try:
                value = job()
                self.callbacks.put(lambda: finish(value=value))
            except Exception as exc:
                error = str(exc)
                self.callbacks.put(lambda: finish(error=error))
        threading.Thread(target=execute, daemon=True).start()

    def load_library(self):
        if self.busy or not self.discard_queue():
            return
        if self.client:
            self.client.close()
            self.client = None
        self.game, self.account_id, self.library_account_id = None, None, None
        self.rows.clear()
        self.desired.clear()
        self.library.clear()
        self.render()
        self.filter_games()
        self.game_title.config(text="Choose a game to begin")
        self.game_caption.config(text="Detect your library, including games that are not installed.")
        self.account_label.config(text="DEMO MODE" if self.demo else "Detecting Steam account…")
        if self.demo:
            self.library = [Game(0, "The Last Explorer (demo)", True), Game(100, "Distant Worlds (demo)", False)]
            self.library_account_id = "DEMO"
            self.status.config(text="DEMO MODE — synthetic achievements only. Steam will not be contacted.")
            self.filter_games()
            self.connect(self.library[0])
            return
        self.status.config(text="Detecting the signed-in account's games. No achievement sessions are opened…")
        def progress(info):
            text = f"Checking game access: {info['scanned']:,} / {info['total']:,} IDs. Found {info['found']:,} accessible games."
            self.callbacks.put(lambda: self.status.config(text=text))
        def job():
            worker = WorkerClient(0, library=True)
            try:
                return worker.receive(timeout=120, progress=progress)
            finally:
                worker.close()
        self.task(job, self.library_loaded)

    def library_loaded(self, reply):
        self.library_account_id = reply["account_id"]
        self.account_label.config(text=f"Steam account  ·  …{self.library_account_id[-4:]}")
        self.library = [Game(**game) for game in reply["games"]]
        self.filter_games()
        installed = sum(game.installed for game in self.library)
        self.game_caption.config(text=f"Steam account ending {self.library_account_id[-4:]}  ·  {len(self.library)} accessible games")
        self.status.config(text=f"Library loaded: {installed} installed, {len(self.library) - installed} not installed. Select a game to load its achievements. Library connection closed.")

    def refresh_catalog(self):
        if self.busy:
            return
        if self.demo:
            self.status.config(text="Demo mode uses synthetic games; no catalog update is needed.")
        else:
            self.status.config(text="Downloading public game IDs from gib.me. No account or library data is sent.")
            self.task(lambda: update_catalog(self.data_dir), lambda count:
                self.status.config(text=f"Catalog updated: {count:,} public game IDs. Choose Refresh library to detect newly added games."))

    def filter_games(self):
        self.games.delete(0, tk.END)
        query = self.game_search.get().casefold()
        mode = self.library_filter.get()
        self.visible_games = [g for g in self.library
            if (query in g.name.casefold() or query in str(g.app_id))
            and (mode != "Installed" or g.installed)
            and (mode != "Not installed" or not g.installed)]
        for game in self.visible_games:
            self.games.insert(tk.END, ("●  " if game.installed else "○  ") + game.name)
        self.library_count.config(text=f"{len(self.visible_games)} / {len(self.library)}")
        self._library_selected()

    def open_selected(self):
        selected = self.games.curselection()
        if selected and not self.busy:
            self.connect(self.visible_games[selected[0]])

    def open_id(self):
        if self.busy:
            return
        try:
            app_id = int(self.app_id.get().strip())
            if not 0 < app_id < 2**32:
                raise ValueError()
        except ValueError:
            messagebox.showinfo("App ID", "Enter a numeric Steam App ID between 1 and 4294967295.", parent=self)
            return
        if self.demo:
            messagebox.showinfo("Demo mode", "Close the demo and launch normally to connect to Steam.", parent=self)
            return
        game = next((g for g in self.library if g.app_id == app_id), Game(app_id, f"Steam App {app_id}"))
        self.connect(game)

    def discard_queue(self):
        return not self.desired or messagebox.askyesno("Discard pending changes?", "Discard the queued changes? Nothing has been sent to Steam.", parent=self)

    def connect(self, game):
        if self.busy or not self.discard_queue():
            return
        self.desired.clear()
        self.rows.clear()
        self.render()
        self.status.config(text=f"Reading {game.name} from {'the demo' if self.demo else 'Steam'}…")
        def job():
            if self.client:
                self.client.close()
                self.client = None
            client = GameClient(game.app_id, self.demo)
            try:
                reply = client.receive()
                if self.library_account_id is not None and reply["account_id"] != self.library_account_id:
                    raise RuntimeError("Steam account changed. Refresh the library before loading achievements.")
            except Exception:
                client.close()
                raise
            return client, reply
        def loaded(value):
            self.client, reply = value
            self.game = game
            self.account_id = reply["account_id"]
            self.set_rows(reply)
            self.game_title.config(text=game.name)
            self.game_caption.config(text=f"App ID {game.app_id}  ·  {'Installed' if game.installed else 'Not installed'}  ·  " + ("Demo data" if self.demo else "Last retrieved from Steam"))
            self.account_label.config(text="DEMO MODE" if self.demo else f"Steam account  ·  …{self.account_id[-4:]}")
        self.task(job, loaded)

    def set_rows(self, reply):
        if self.account_id != reply["account_id"]:
            raise RuntimeError("Steam account changed. Reopen the game.")
        self.rows = [Achievement(**a) for a in reply["achievements"]]
        self.desired.clear()
        self.render()
        self.status.config(text=("DEMO — " if self.demo else "Steam session closed — ") + f"Loaded {len(self.rows)} achievements. Select rows and queue a change." if self.rows else "No achievements returned. Steam session closed.")

    def render(self):
        records = []
        query = self.search.get().casefold()
        mode = self.status_filter.get()
        for row in self.rows:
            hidden = row.hidden and not row.unlocked and not self.reveal.get()
            name = "Hidden achievement" if hidden else row.name
            if query not in (name + " " + ("" if hidden else row.description) + " " + row.key).casefold():
                continue
            if mode == "Locked" and row.unlocked or mode == "Unlocked" and not row.unlocked or mode == "Pending changes" and row.key not in self.desired:
                continue
            timestamp = datetime.fromtimestamp(row.unlock_time, timezone.utc).strftime("%Y-%m-%d") if row.unlock_time else "—"
            pending = ("Unlock" if self.desired[row.key] else "Lock") if row.key in self.desired else "—"
            description = "Hidden achievement. Enable Show hidden details to reveal." if hidden else row.description or "No description provided by Steam."
            records.append(dict(key=row.key, values=(name, "Unlocked" if row.unlocked else "Locked", timestamp, pending),
                description=description, actual=row.unlocked, draft=self.desired.get(row.key, row.unlocked)))
        self.table.replace(records)
        count = sum(row.unlocked for row in self.rows)
        self.metric.config(text=f"{count} / {len(self.rows)} unlocked")
        self.progress["value"] = 100 * count / len(self.rows) if self.rows else 0
        self.review_button.config(text=f"Review changes ({len(self.desired)})")
        self.pending_label.config(text=f"{len(self.desired)} pending changes" if self.desired else "No pending changes",
                                  fg="#e7bc66" if self.desired else MUTED)
        self._sync_controls()

    def show_details(self, _=None):
        selection = self.table.selection()
        self._sync_controls()
        if not selection:
            self.details.config(text="ON = unlocked  ·  OFF = locked  ·  Switch changes stay pending until reviewed.")
            return
        row = next((a for a in self.rows if a.key == selection[0]), None)
        if row:
            self.details.config(text=f"{len(selection)} selected  ·  API ID: {row.key}" if len(selection) == 1 else f"{len(selection)} selected  ·  Unlock or lock the selection, then review all changes.")

    def toggle_achievement(self, key, state):
        if self.busy or not self.client or type(state) is not bool:
            self.render()
            return
        row = next((row for row in self.rows if row.key == key), None)
        if row is None:
            return
        if row.unlocked == state:
            self.desired.pop(key, None)
        else:
            self.desired[key] = state
        self.render()
        self.status.config(text=f"{len(self.desired)} pending changes. Switches show your draft; Steam changes only after Review changes.")

    def queue_state(self, state):
        if self.busy or not self.client:
            return
        selected = set(self.table.selection())
        for row in self.rows:
            if row.key in selected:
                if row.unlocked == state:
                    self.desired.pop(row.key, None)
                else:
                    self.desired[row.key] = state
        self.render()
        self.status.config(text=f"{len(self.desired)} queued changes across all filters. Nothing has been applied.")

    def clear_queue(self):
        self.desired.clear()
        self.render()

    def refresh(self):
        if not self.client or self.busy or not self.discard_queue():
            return
        self.status.config(text="Refreshing achievement states…")
        self.task(lambda: self.client.exchange({"command": "read"}), self.set_rows)

    def review(self):
        if self.busy or not self.client or not self.desired:
            return
        changes = plan_changes(self.rows, self.desired)
        dialog = tk.Toplevel(self)
        dialog.title("Review changes — " + self.game.name)
        dialog.geometry("660x540")
        dialog.minsize(580, 450)
        dialog.configure(bg=BG)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(2, weight=1)
        dialog.transient(self)
        dialog.grab_set()
        self.label(dialog, "Review before applying", 20, bold=True).grid(row=0, column=0, sticky="w", padx=22, pady=(20, 8))
        self.label(dialog, f"{self.game.name}  ·  {len(changes)} changes  ·  Account …{self.account_id[-4:]}", 10, MUTED, wraplength=610).grid(row=1, column=0, sticky="ew", padx=22)
        listing = tk.Text(dialog, bg=PANEL, fg=INK, relief="flat", wrap="word", height=8, font=("Segoe UI", 11))
        listing.grid(row=2, column=0, sticky="nsew", padx=22, pady=16)
        names = {a.key: "Hidden achievement" if a.hidden and not a.unlocked and not self.reveal.get() else a.name for a in self.rows}
        for c in changes:
            listing.insert("end", f"{'UNLOCK' if c.after else 'LOCK'}    {names[c.key]}\n    {c.key}\n\n")
        listing.config(state="disabled")
        text = "A reference snapshot is saved before applying. Steam may refuse protected achievements. Changes can be partial. Original dates and completion trophies cannot be restored by the snapshot."
        self.label(dialog, "DEMO ONLY. Steam will not be contacted." if self.demo else text, 10, MUTED, wraplength=610, justify="left").grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 12))
        consent = tk.BooleanVar()
        controls = tk.Frame(dialog, bg=BG)
        controls.grid(row=5, column=0, sticky="ew", padx=22, pady=(0, 20))
        apply = ttk.Button(controls, text="Apply to demo" if self.demo else "Apply to Steam", style="Accent.TButton", state="disabled")
        ttk.Checkbutton(dialog, text="I reviewed the selected changes.", variable=consent,
                        command=lambda: apply.state(["!disabled"] if consent.get() else ["disabled"])).grid(row=4, column=0, sticky="w", padx=22, pady=(0, 12))
        ttk.Button(controls, text="Cancel", command=dialog.destroy).pack(side="left")
        def submit():
            dialog.destroy()
            self.status.config(text="Applying reviewed changes. Steam may briefly show the game as running…")
            request = dict(command="apply", changes=[asdict(c) for c in changes],
                           account_id=self.account_id, snapshot_folder=str(self.data_dir / ("demo-snapshots" if self.demo else "snapshots")))
            self.task(lambda: self.client.exchange(request), self.applied, uncertain=True)
        apply.config(command=submit)
        apply.pack(side="right")

    def applied(self, reply):
        result = reply["result"]
        self.desired.clear()
        message = ("Demo result\n\n" if self.demo else "Steam result\n\n") + f"Status: {result['status']}\nConfirmed: {len(result['confirmed'])}\nRejected: {len(result['rejected'])}\nUnconfirmed: {len(result['unconfirmed'])}\n\n{result['message']}\n\nSnapshot: {result['snapshot']}"
        if result["status"] == "unconfirmed":
            self.rows.clear()
            self.render()
            self.client.close()
            self.client = None
            self.status.config(text="Outcome unconfirmed. Check Steam, then reopen the game before retrying.")
        else:
            # These rows came from the worker's post-submit verification. Display
            # them without opening another native session automatically.
            self.set_rows(dict(account_id=self.account_id, achievements=result["achievements"]))
            self.status.config(text=f"Result: {result['status']}. " + ("Demo data updated." if self.demo else "Steam session closed. Displaying the last verified state."))
        messagebox.showinfo("Change result", message, parent=self)

    def export(self):
        if not self.rows or self.busy:
            return
        path = filedialog.asksaveasfilename(parent=self, title="Export current state", defaultextension=".json", initialfile=f"achievement-desk-{self.game.app_id}.json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            Path(path).write_text(json.dumps(dict(schema=1, app_id=self.game.app_id, account_id=self.account_id,
                achievements=[asdict(a) for a in self.rows], note="Reference only; does not restore dates or trophies."), ensure_ascii=False, indent=2), encoding="utf-8")
            self.status.config(text="Achievement reference exported locally.")
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)

    def open_steam(self):
        if self.game and not self.demo and self.account_id:
            webbrowser.open(f"https://steamcommunity.com/profiles/{int(self.account_id)}/stats/{self.game.app_id}/achievements/")

    def quit_app(self):
        if self.busy:
            messagebox.showinfo("Request in progress", "Wait for the current Steam request to finish before closing.", parent=self)
            return
        if not self.discard_queue():
            return
        if self.client:
            self.client.close()
        self.destroy()


def launch(demo=False):
    Desk(demo).mainloop()
