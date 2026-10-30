"""Synthetic fixture data; never imports the Steam adapter."""
from dataclasses import replace
from domain import Achievement


class DemoSession:
    app_id = 0
    account_id = "DEMO"

    def __init__(self, _=None):
        self.app_id = 0 if _ is None else _
        self.rows = [
            Achievement("FIRST_STEP", "A new beginning", "Finish the opening chapter.", True, 1720000000),
            Achievement("EXPLORER", "Off the beaten path", "Discover all five hidden locations.", False),
            Achievement("COLLECTOR", "Leave nothing behind", "Find every collectible in the base game.", False),
            Achievement("NO_DAMAGE", "Untouchable", "Finish a chapter without taking damage.", False),
            Achievement("STORY_END", "The final page", "Complete the main story.", False),
            Achievement("SECRET", "Behind the curtain", "A hidden achievement. Reveal spoilers in Steam.", False, hidden=True),
        ]

    def read(self):
        return list(self.rows)

    def set_state(self, key, state):
        self.rows = [replace(a, unlocked=state, unlock_time=0) if a.key == key else a for a in self.rows]
        return True

    def store(self):
        pass

    def close(self):
        pass
