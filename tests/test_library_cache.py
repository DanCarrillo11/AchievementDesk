"""Cached libraries are snapshots, never authoritative Steam permissions."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from library import Game
from library_cache import cache_path, load_library_cache, save_library_cache
from worker import run_library

ACCOUNT_A = "76561198000000001"
ACCOUNT_B = "76561198000000002"
SAMPLE = [Game(10, "First Game", True, "a" * 40), Game(20, "Second Game", False)]


class LibraryCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_first_scan_then_fast_restart(self):
        self.assertIsNone(load_library_cache(self.folder, ACCOUNT_A))
        save_library_cache(self.folder, ACCOUNT_A, SAMPLE)
        self.assertEqual(load_library_cache(self.folder, ACCOUNT_A), SAMPLE)
        self.assertTrue(cache_path(self.folder, ACCOUNT_A).is_file())

    def test_zero_games_is_a_valid_cached_result(self):
        save_library_cache(self.folder, ACCOUNT_A, [])
        self.assertEqual(load_library_cache(self.folder, ACCOUNT_A), [])

    def test_accounts_have_separate_snapshots(self):
        save_library_cache(self.folder, ACCOUNT_A, SAMPLE)
        self.assertIsNone(load_library_cache(self.folder, ACCOUNT_B))
        save_library_cache(self.folder, ACCOUNT_B, [Game(99, "Private to B")])
        self.assertEqual(load_library_cache(self.folder, ACCOUNT_A), SAMPLE)
        self.assertEqual(load_library_cache(self.folder, ACCOUNT_B), [Game(99, "Private to B")])

    def test_invalid_account_id_cannot_escape_cache_directory(self):
        for account in ("../other", "../../secret", "DEMO", "", "0", "765/99", 7656119, True):
            with self.subTest(account=account), self.assertRaises(ValueError):
                cache_path(self.folder, account)

    def test_corrupted_or_wrong_account_snapshot_falls_back_to_scan(self):
        save_library_cache(self.folder, ACCOUNT_A, SAMPLE)
        path = cache_path(self.folder, ACCOUNT_A)
        path.write_text("not json", encoding="utf-8")
        self.assertIsNone(load_library_cache(self.folder, ACCOUNT_A))
        save_library_cache(self.folder, ACCOUNT_A, SAMPLE)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["account_id"] = ACCOUNT_B
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertIsNone(load_library_cache(self.folder, ACCOUNT_A))

    def test_cache_rejects_duplicate_ids_and_bad_metadata(self):
        save_library_cache(self.folder, ACCOUNT_A, SAMPLE)
        path = cache_path(self.folder, ACCOUNT_A)
        base = json.loads(path.read_text(encoding="utf-8"))
        cases = [
            [base["games"][0], base["games"][0]],
            [dict(base["games"][0], app_id=True)],
            [dict(base["games"][0], installed=1)],
            [dict(base["games"][0], name="")],
            [dict(base["games"][0], icon_hash="../bad")],
            [dict(base["games"][0], app_id=228980)],
            [dict(base["games"][0], token="not-permitted")],
        ]
        for records in cases:
            with self.subTest(records=records):
                path.write_text(json.dumps(dict(base, games=records)), encoding="utf-8")
                self.assertIsNone(load_library_cache(self.folder, ACCOUNT_A))

    def test_atomic_write_failure_preserves_last_good_snapshot(self):
        save_library_cache(self.folder, ACCOUNT_A, SAMPLE)
        with patch("library_cache.atomic_json", side_effect=OSError("Disk full")):
            with self.assertRaises(OSError):
                save_library_cache(self.folder, ACCOUNT_A, [Game(30, "New")])
        self.assertEqual(load_library_cache(self.folder, ACCOUNT_A), SAMPLE)

    def test_no_account_credentials_or_achievement_details_stored(self):
        save_library_cache(self.folder, ACCOUNT_A, SAMPLE)
        data = json.loads(cache_path(self.folder, ACCOUNT_A).read_text(encoding="utf-8"))
        self.assertEqual(set(data), {"schema", "account_id", "games"})
        self.assertEqual(set(data["games"][0]), {"app_id", "name", "installed", "icon_hash"})


class CachedWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def run_worker(self, refresh=False):
        output = StringIO()
        with patch.dict("os.environ", {"LOCALAPPDATA": self.temp.name}), redirect_stdout(output):
            run_library(refresh=refresh)
        return json.loads(output.getvalue().strip().splitlines()[-1])

    @patch("native.SteamLibrarySession")
    def test_cached_restart_does_not_scan_catalog(self, session_class):
        session = session_class.return_value
        session.account_id = int(ACCOUNT_A)
        save_library_cache(Path(self.temp.name) / "AchievementDesk", ACCOUNT_A, SAMPLE)
        with patch("catalog.catalog_ids", side_effect=AssertionError("Catalog should not be checked")), \
             patch("library.installed_games", side_effect=AssertionError("No filesystem scan")):
            reply = self.run_worker()
        self.assertTrue(reply["ok"])
        self.assertTrue(reply["cached"])
        self.assertEqual(reply["games"][0]["name"], "First Game")
        self.assertEqual(session.mock_calls[0][0], "verify_identity")
        self.assertEqual(session.verify_identity.call_count, 2)
        session.close.assert_called_once()

    @patch("native.SteamLibrarySession")
    def test_initial_discovery_saves_for_next_start(self, session_class):
        session_class.return_value.account_id = int(ACCOUNT_A)
        with patch("catalog.catalog_ids", return_value=[10, 20]), \
             patch("library.installed_games", return_value=[]), \
             patch("library.discover_owned", return_value=SAMPLE) as discover:
            reply = self.run_worker()
        self.assertTrue(reply["ok"])
        self.assertFalse(reply["cached"])
        discover.assert_called_once()
        self.assertEqual(load_library_cache(Path(self.temp.name) / "AchievementDesk", ACCOUNT_A), SAMPLE)

    @patch("native.SteamLibrarySession")
    def test_explicit_refresh_rescans_and_replaces_snapshot(self, session_class):
        session_class.return_value.account_id = int(ACCOUNT_A)
        folder = Path(self.temp.name) / "AchievementDesk"
        save_library_cache(folder, ACCOUNT_A, SAMPLE)
        with patch("catalog.catalog_ids", return_value=[30]), \
             patch("library.installed_games", return_value=[]), \
             patch("library.discover_owned", return_value=[Game(30, "Updated")]) as discover, \
             patch("library_cache.load_library_cache", side_effect=AssertionError("Refresh must bypass cache")):
            reply = self.run_worker(refresh=True)
        self.assertTrue(reply["ok"])
        self.assertFalse(reply["cached"])
        discover.assert_called_once()
        self.assertEqual(load_library_cache(folder, ACCOUNT_A), [Game(30, "Updated")])

    @patch("native.SteamLibrarySession")
    def test_account_change_does_not_load_previous_snapshot(self, session_class):
        save_library_cache(Path(self.temp.name) / "AchievementDesk", ACCOUNT_A, SAMPLE)
        session_class.return_value.account_id = int(ACCOUNT_B)
        with patch("catalog.catalog_ids", return_value=[99]), \
             patch("library.installed_games", return_value=[]), \
             patch("library.discover_owned", return_value=[Game(99, "Other account")]):
            reply = self.run_worker()
        self.assertFalse(reply["cached"])
        self.assertEqual([g["app_id"] for g in reply["games"]], [99])

    @patch("native.SteamLibrarySession")
    def test_failed_identity_does_not_reveal_stored_games(self, session_class):
        session_class.return_value.account_id = int(ACCOUNT_A)
        session_class.return_value.verify_identity.side_effect = RuntimeError("Account changed")
        save_library_cache(Path(self.temp.name) / "AchievementDesk", ACCOUNT_A, SAMPLE)
        reply = self.run_worker()
        self.assertFalse(reply["ok"])
        self.assertNotIn("games", reply)
        session_class.return_value.close.assert_called_once()

    @patch("native.SteamLibrarySession")
    def test_failed_refresh_preserves_previous_cache(self, session_class):
        session_class.return_value.account_id = int(ACCOUNT_A)
        folder = Path(self.temp.name) / "AchievementDesk"
        save_library_cache(folder, ACCOUNT_A, SAMPLE)
        with patch("catalog.catalog_ids", return_value=[30]), \
             patch("library.installed_games", return_value=[]), \
             patch("library.discover_owned", side_effect=RuntimeError("Steam changed")):
            reply = self.run_worker(refresh=True)
        self.assertFalse(reply["ok"])
        self.assertEqual(load_library_cache(folder, ACCOUNT_A), SAMPLE)


if __name__ == "__main__":
    unittest.main()
