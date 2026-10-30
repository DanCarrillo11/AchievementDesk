"""Compact achievement cards and keyboard-accessible draft-state switches."""
import math
import tkinter as tk
from tkinter import ttk

BG, CARD, TEXT, MUTED, BLUE, GREEN, AMBER = "#101923", "#1b2838", "#e5edf5", "#9aafc3", "#66c0f4", "#8fce64", "#e7bc66"


def switch_image(master, on, scale=1):
    width, height = round(42 * scale), round(24 * scale)
    image = tk.PhotoImage(master=master, width=width, height=height)
    radius = height / 2 - 1
    thumb_x = width - height / 2 if on else height / 2
    center_y = height / 2
    track = "#4a9dce" if on else "#455366"
    # Transparent corners and a white thumb, drawn without external assets.
    for y in range(height):
        for x in range(width):
            nearest_x = min(max(x + .5, height / 2), width - height / 2)
            if (x + .5 - nearest_x) ** 2 + (y + .5 - center_y) ** 2 <= radius ** 2:
                color = "#f4f8fc" if math.hypot(x + .5 - thumb_x, y + .5 - center_y) <= radius - 3 * scale else track
                image.put(color, (x, y))
    return image


class AchievementList(tk.Frame):
    """Paginated cards. Selection is separate from each achievement's draft switch."""
    PAGE_SIZE = 25

    def __init__(self, master, on_toggle, on_selection):
        super().__init__(master, bg=BG)
        self.on_toggle, self.on_selection = on_toggle, on_selection
        self.records, self.order, self.selected = {}, [], set()
        self.page, self.busy = 0, False
        self.cards, self.switches, self.wrap_labels = {}, {}, []
        scale = max(1, min(2, self.winfo_fpixels("1i") / 96))
        self.off_image = switch_image(self, False, scale)
        self.on_image = switch_image(self, True, scale)
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", pady=(0, 8))
        self.summary = tk.Label(bar, bg=BG, fg=MUTED, font=("Segoe UI", 9), anchor="w")
        self.summary.pack(side="left")
        self.next_button = ttk.Button(bar, text="Next  ›", style="Small.TButton", command=lambda: self.turn_page(1))
        self.next_button.pack(side="right")
        self.previous_button = ttk.Button(bar, text="‹  Previous", style="Small.TButton", command=lambda: self.turn_page(-1))
        self.previous_button.pack(side="right", padx=(0, 6))
        holder = tk.Frame(self, bg=BG)
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, bg=BG, highlightthickness=0, borderwidth=0, height=180)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.inner = tk.Frame(self.canvas, bg=BG)
        self.window_id = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self.resize)
        self.canvas.bind("<MouseWheel>", self.wheel)

    def resize(self, event):
        self.canvas.itemconfigure(self.window_id, width=event.width)
        for label in self.wrap_labels:
            label.configure(wraplength=max(220, event.width - 150))

    def wheel(self, event):
        # Avoid the upward jump that Tk can make when all rows already fit.
        bounds = self.canvas.bbox("all")
        if bounds and bounds[3] > self.canvas.winfo_height():
            self.canvas.yview_scroll(-int(event.delta / 120) or (-1 if event.delta > 0 else 1), "units")
        return "break"

    def replace(self, records):
        old_order = self.order
        focused = self.focus_get()
        focus_key = next((key for key, widget in self.switches.items() if widget == focused), None)
        self.records = {row["key"]: row for row in records}
        self.order = [row["key"] for row in records]
        self.selected.intersection_update(self.records)
        if old_order != self.order:
            self.page = 0
        self.page = min(self.page, max(0, (len(self.order) - 1) // self.PAGE_SIZE))
        position = self.canvas.yview()[0] if old_order == self.order else 0
        self.paint()
        self.canvas.yview_moveto(position)
        if focus_key in self.switches:
            self.switches[focus_key].focus_set()

    def paint(self):
        for widget in self.inner.winfo_children():
            widget.destroy()
        self.cards, self.switches, self.wrap_labels = {}, {}, []
        count = len(self.order)
        first = self.page * self.PAGE_SIZE
        pages = max(1, math.ceil(count / self.PAGE_SIZE))
        self.summary.configure(text=f"{count:,} achievements  ·  Page {self.page + 1} of {pages}")
        self.previous_button.state(["disabled"] if not self.page else ["!disabled"])
        self.next_button.state(["disabled"] if self.page + 1 >= pages else ["!disabled"])
        if not count:
            tk.Label(self.inner, text="No achievements to display", bg=BG, fg=TEXT,
                     font=("Segoe UI", 15, "bold"), pady=32).pack(fill="x")
            tk.Label(self.inner, text="Choose a game, or adjust your search and filters.",
                     bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(fill="x")
        for key in self.order[first:first + self.PAGE_SIZE]:
            self.card(key)

    def card(self, key):
        data = self.records[key]
        values = data["values"]
        pending = values[3] != "—"
        outer = tk.Frame(self.inner, bg=BLUE if key in self.selected else CARD, padx=1, pady=1)
        outer.pack(fill="x", pady=(0, 6))
        row = tk.Frame(outer, bg=CARD, padx=12, pady=10)
        row.pack(fill="x")
        row.columnconfigure(0, weight=1)
        wrap = max(220, self.canvas.winfo_width() - 150) if self.canvas.winfo_width() > 1 else 450
        title = tk.Label(row, text=values[0], bg=CARD, fg=TEXT, anchor="w", justify="left",
                         font=("Segoe UI", 11, "bold"), wraplength=wrap)
        title.grid(row=0, column=0, sticky="ew", padx=(0, 16))
        description = tk.Label(row, text=data["description"], bg=CARD, fg=MUTED, anchor="w", justify="left",
                               font=("Segoe UI", 9), wraplength=wrap)
        description.grid(row=1, column=0, sticky="ew", padx=(0, 16), pady=(3, 4))
        status = f"{values[3]} queued  ·  Saved state: {values[1].lower()}" if pending else values[1]
        if not pending and data["actual"] and values[2] != "—":
            status += f"  ·  {values[2]} UTC"
        state_label = tk.Label(row, text=status, bg=CARD, fg=AMBER if pending else GREEN if data["actual"] else MUTED,
                               font=("Segoe UI", 9), anchor="w")
        state_label.grid(row=2, column=0, sticky="w")
        value = tk.BooleanVar(value=data["draft"])
        switch = ttk.Checkbutton(row, variable=value, style="Switch.TCheckbutton", takefocus=True,
                                 image=(self.off_image, "selected", self.on_image),
                                 command=lambda: self.on_toggle(key, value.get()))
        switch.grid(row=0, column=1, rowspan=2, sticky="e")
        if self.busy:
            switch.state(["disabled"])
        tk.Label(row, text="ON" if data["draft"] else "OFF", bg=CARD, fg=BLUE if data["draft"] else MUTED,
                 font=("Segoe UI", 8, "bold")).grid(row=2, column=1, sticky="e", padx=10)
        self.cards[key], self.switches[key] = outer, switch
        self.wrap_labels.extend([title, description])
        for widget in (outer, row, title, description, state_label):
            widget.bind("<Button-1>", lambda event, item=key: self.select(item, bool(event.state & 0x0004)))
        for widget in (outer, row, title, description, state_label, switch):
            widget.bind("<MouseWheel>", self.wheel)

    def select(self, key, extend=False):
        if extend:
            if key in self.selected:
                self.selected.remove(key)
            else:
                self.selected.add(key)
        else:
            self.selected = {key}
        self.selection_style()
        self.on_selection()

    def selection_style(self):
        for key, widget in self.cards.items():
            widget.configure(bg=BLUE if key in self.selected else CARD)

    def selection(self):
        return tuple(key for key in self.order if key in self.selected)

    def selection_set(self, keys):
        self.selected = set([keys] if isinstance(keys, str) else keys).intersection(self.records)
        self.selection_style()

    def get_children(self):
        return tuple(self.order)

    def exists(self, key):
        return key in self.records

    def item(self, key, option=None):
        values = self.records[key]["values"]
        return values if option == "values" else {"values": values}

    def turn_page(self, step):
        self.page = max(0, min(self.page + step, max(0, (len(self.order) - 1) // self.PAGE_SIZE)))
        self.paint()
        self.canvas.yview_moveto(0)

    def set_busy(self, value):
        self.busy = value
        for switch in self.switches.values():
            switch.state(["disabled"] if value else ["!disabled"])
