import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from domain import Achievement, Change, apply_changes, plan_changes, validate_changes
from library import installed_games, manifest_game


class Backend:
    account_id = "test-account"
    app_id = 123

    def __init__(self):
        self.rows = [Achievement("A", "First", "", False), Achievement("B", "Second", "", True, 123456)]
        self.reject = set()
        self.calls = []
        self.store_error = False
        self.revert = False

    def read(self):
        self.calls.append("read")
        return list(self.rows)

    def set_state(self, key, state):
        self.calls.append((key, state))
        if key in self.reject:
            return False
        self.rows = [replace(a, unlocked=state) if a.key == key else a for a in self.rows]
        return True

    def store(self):
        self.calls.append("store")
        if self.store_error:
            raise TimeoutError("No acknowledgement")
        if self.revert:
            self.rows = [replace(a, unlocked=False) if a.key == "A" else a for a in self.rows]


class ChangesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.backend = Backend()

    def tearDown(self):
        self.temp.cleanup()

    def apply(self, changes=None):
        return apply_changes(self.backend, changes or [Change("A", False, True)], self.temp.name, "test-account")

    def test_noop_removed(self):
        self.assertEqual([], plan_changes(self.backend.rows, {"A": False, "B": True}))

    def test_lock_and_unlock_plan(self):
        self.assertEqual([Change("A", False, True), Change("B", True, False)], plan_changes(self.backend.rows, {"A": True, "B": False}))

    def test_invalid_boolean(self):
        with self.assertRaises(ValueError):
            plan_changes(self.backend.rows, {"A": 1})

    def test_unknown_key(self):
        with self.assertRaises(ValueError):
            plan_changes(self.backend.rows, {"missing": True})

    def test_duplicate_schema(self):
        with self.assertRaises(ValueError):
            plan_changes(self.backend.rows * 2, {})

    def test_duplicate_request(self):
        with self.assertRaises(ValueError):
            self.apply([Change("A", False, True)] * 2)
        self.assertNotIn("store", self.backend.calls)

    def test_unknown_request(self):
        with self.assertRaises(ValueError):
            self.apply([Change("missing", False, True)])

    def test_empty_validation(self):
        with self.assertRaises(ValueError):
            validate_changes(self.backend.rows, [])

    def test_stale_review_stops_before_write(self):
        self.backend.rows[0] = replace(self.backend.rows[0], unlocked=True)
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(self.backend.calls, ["read"])
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_wrong_account_stops_before_read(self):
        with self.assertRaises(ValueError):
            apply_changes(self.backend, [Change("A", False, True)], self.temp.name, "someone-else")
        self.assertEqual(self.backend.calls, [])

    def test_snapshot_before_first_mutation(self):
        original = self.backend.set_state
        def checking_set(key, state):
            snapshots = list(Path(self.temp.name).glob("*.json"))
            self.assertEqual(len(snapshots), 1)
            data = json.loads(snapshots[0].read_text())
            self.assertFalse(data["achievements"][0]["unlocked"])
            return original(key, state)
        self.backend.set_state = checking_set
        result = self.apply()
        self.assertEqual(result["status"], "confirmed")
        self.assertEqual(result["confirmed"], ["A"])
        self.assertEqual(self.backend.calls.count("store"), 1)

    def test_snapshot_failure_stops_before_mutation(self):
        bad = Path(self.temp.name) / "not-a-folder"
        bad.write_text("existing")
        with self.assertRaises(OSError):
            apply_changes(self.backend, [Change("A", False, True)], bad, "test-account")
        self.assertEqual(self.backend.calls, ["read"])

    def test_every_change_rejected_skips_store(self):
        self.backend.reject.add("A")
        result = self.apply()
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["rejected"], ["A"])
        self.assertNotIn("store", self.backend.calls)

    def test_partial_result(self):
        self.backend.reject.add("B")
        result = self.apply([Change("A", False, True), Change("B", True, False)])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["confirmed"], ["A"])
        self.assertEqual(result["rejected"], ["B"])

    def test_timeout_is_not_reported_as_success(self):
        self.backend.store_error = True
        result = self.apply()
        self.assertEqual(result["status"], "unconfirmed")
        self.assertEqual(result["confirmed"], [])
        self.assertEqual(result["unconfirmed"], ["A"])

    def test_rejected_persistence_not_success(self):
        self.backend.revert = True
        result = self.apply()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["unconfirmed"], ["A"])

    def test_snapshot_filenames_unique(self):
        first = self.apply()
        second = self.apply([Change("A", True, False)])
        self.assertNotEqual(first["snapshot"], second["snapshot"])


class LibraryTests(unittest.TestCase):
    def test_manifest(self):
        game = manifest_game('"appid" "123"\n"name" "A Game"')
        self.assertEqual((game.app_id, game.name), (123, "A Game"))

    def test_malformed(self):
        self.assertIsNone(manifest_game('"appid" "oops"'))

    def test_secondary_library_and_deduplication(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            primary, secondary = root / "one", root / "two"
            for p in (primary, secondary):
                (p / "steamapps").mkdir(parents=True)
                (p / "steamapps" / "appmanifest_123.acf").write_text('"appid" "123" "name" "Example"')
            (secondary / "steamapps" / "appmanifest_456.acf").write_text('"appid" "456" "name" "Other"')
            escaped = str(secondary).replace("\\", "\\\\")
            (primary / "steamapps" / "libraryfolders.vdf").write_text(f'"path" "{escaped}"')
            self.assertEqual([g.app_id for g in installed_games(primary)], [123, 456])


if __name__ == "__main__":
    unittest.main()
