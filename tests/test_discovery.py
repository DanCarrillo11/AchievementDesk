import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from catalog import catalog_ids, parse_xml, read_catalog, update_catalog
from library import Game, discover_owned
from native import SteamLibrarySession, SteamSession


class AccessSession:
    account_id = "account-one"

    def __init__(self):
        self.checked = []
        self.verifications = 0

    def verify_identity(self):
        self.verifications += 1

    def owns(self, app_id):
        self.checked.append(app_id)
        return app_id in {10, 20, 30}

    def app_name(self, app_id):
        return {10: "Installed game", 20: "Uninstalled game"}.get(app_id, "")


class DiscoveryTests(unittest.TestCase):
    def test_uninstalled_and_installed_owned_games(self):
        session = AccessSession()
        rows = discover_owned(session, [10, 20, 99], [Game(10, "Local", True), Game(99, "Other account", True)])
        self.assertEqual(rows, [Game(10, "Installed game", True), Game(20, "Uninstalled game", False)])
        self.assertGreaterEqual(session.verifications, 2)

    def test_installed_ids_missing_from_catalog_are_checked(self):
        rows = discover_owned(AccessSession(), [20], [Game(30, "New local game", True)])
        self.assertIn(Game(30, "New local game", True), rows)

    def test_unknown_metadata_retains_app_id(self):
        self.assertEqual(discover_owned(AccessSession(), [30]), [Game(30, "Steam App 30", False)])

    def test_duplicates_invalid_ids_and_redistributables(self):
        session = AccessSession()
        rows = discover_owned(session, [10, 10, True, -1, 0, 2**32, 228980])
        self.assertEqual(session.checked, [10])
        self.assertEqual(len(rows), 1)

    def test_progress_includes_completed_count(self):
        updates = []
        discover_owned(AccessSession(), [10, 20], progress=lambda *args: updates.append(args))
        self.assertEqual(updates[-1], (2, 2, 2))

    def test_account_change_aborts_scan(self):
        session = AccessSession()
        def verify():
            session.verifications += 1
            if session.verifications > 2:
                raise RuntimeError("Account changed")
        session.verify_identity = verify
        with self.assertRaisesRegex(RuntimeError, "Account changed"):
            discover_owned(session, [10, 20])

    def test_native_discovery_cannot_read_or_write_achievements(self):
        session = SteamLibrarySession.__new__(SteamLibrarySession)
        session.library_mode = True
        for operation in (session.read, lambda: session.set_state("A", True), session.store):
            with self.assertRaisesRegex(RuntimeError, "cannot read or modify"):
                operation()

    def test_native_discovery_selects_no_game(self):
        with patch.object(SteamSession, "__init__", return_value=None) as initialize, patch.object(SteamLibrarySession, "interface", return_value=123):
            SteamLibrarySession()
            initialize.assert_called_once_with(0, library_mode=True)


class CatalogTests(unittest.TestCase):
    def test_xml_ids_and_types(self):
        self.assertEqual(parse_xml(b'<games><game>10</game><game>10</game><game type="junk">480</game><game type="demo">20</game></games>'), [10, 20])

    def test_reject_unsafe_empty_or_invalid_catalogs(self):
        for xml in (b'<!DOCTYPE games><games><game>10</game></games>', b'<games/>',
                    b'<wrong><game>10</game></wrong>', b'<games><game>no</game></games>',
                    b'<games><game>0</game></games>'):
            with self.subTest(xml=xml), self.assertRaises(ValueError):
                parse_xml(xml)

    def test_cached_public_catalog(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "catalog.json").write_text(json.dumps(dict(app_ids=[20, 10, 10])))
            self.assertEqual(catalog_ids(folder), [10, 20])

    def test_corrupted_cache_uses_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "catalog.json").write_text("not-json")
            self.assertGreater(len(catalog_ids(folder)), 1000)

    def test_json_boolean_is_not_an_app_id(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "catalog.json"
            path.write_text(json.dumps(dict(app_ids=[True])))
            with self.assertRaises(ValueError):
                read_catalog(path)

    def test_failed_download_keeps_existing_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "catalog.json"
            text = json.dumps(dict(app_ids=[10]))
            path.write_text(text)
            with patch("catalog.urllib.request.urlopen", side_effect=OSError("Offline")):
                with self.assertRaises(OSError):
                    update_catalog(folder)
            self.assertEqual(path.read_text(), text)


if __name__ == "__main__":
    unittest.main()
