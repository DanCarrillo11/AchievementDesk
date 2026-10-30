import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from workspace import Workspace, atomic_json, order_achievements
from media import Media, parse_icons, percentages
from updates import check_release, repository, version_key
from library import Game


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = Workspace(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_preferences_and_window_size_survive_restart(self):
        self.workspace.settings.update(compact=True, reveal_hidden=True, width=1440)
        self.workspace.save()
        loaded = Workspace(self.root)
        self.assertTrue(loaded.settings["compact"])
        self.assertTrue(loaded.settings["reveal_hidden"])
        self.assertEqual(loaded.settings["width"], 1440)

    def test_malformed_preferences_recover(self):
        (self.root / "workspace.json").write_text('{bad', encoding="utf-8")
        self.assertFalse(Workspace(self.root).settings["compact"])
        atomic_json(self.root / "workspace.json", dict(settings=dict(width=-100, compact="yes")))
        self.assertEqual(Workspace(self.root).settings["width"], 1020)
        self.assertFalse(Workspace(self.root).settings["compact"])

    def test_empty_preview_release_channel_migrates_to_project(self):
        self.workspace.settings["release_repository"] = ""
        self.workspace.save()
        self.assertEqual(Workspace(self.root).settings["release_repository"], "DanCarrillo11/AchievementDesk")

    def test_custom_release_channel_is_preserved(self):
        self.workspace.settings["release_repository"] = "owner/CustomChannel"
        self.workspace.save()
        self.assertEqual(Workspace(self.root).settings["release_repository"], "owner/CustomChannel")

    def test_favorites_and_recents_are_account_scoped(self):
        self.workspace.favorite("A", 10)
        self.workspace.visit("A", 10)
        self.assertEqual(self.workspace.profile("B")["favorites"], [])
        self.assertEqual(self.workspace.profile("B")["recent"], [])
        self.assertEqual(Workspace(self.root).profile("A")["favorites"], [10])
        self.workspace.favorite("A", 10)
        self.assertEqual(self.workspace.profile("A")["favorites"], [])

    def test_recent_order_is_deduplicated_and_bounded(self):
        for index in range(40):
            self.workspace.visit("A", index)
        self.workspace.visit("A", 20)
        recent = self.workspace.profile("A")["recent"]
        self.assertEqual(len(recent), 30)
        self.assertEqual(recent[0], 20)
        self.assertEqual(recent.count(20), 1)

    def test_history_starts_unconfirmed_and_records_partial_outcome(self):
        activity = self.workspace.start_activity("A", Game(10, "Game"), [dict(key="A", name="Name", before=False, after=True)])
        self.assertEqual(self.workspace.history("A")[0]["status"], "unconfirmed")
        self.workspace.finish_activity("A", activity, dict(status="partial", confirmed=["A"], rejected=["B"], unconfirmed=[], snapshot="local.json"))
        entry = Workspace(self.root).history("A")[0]
        self.assertEqual(entry["confirmed"], ["A"])
        self.assertEqual(entry["status"], "partial")
        self.assertEqual(self.workspace.history("B"), [])

    def test_history_path_cannot_escape_folder(self):
        with self.assertRaises(ValueError):
            self.workspace.history_path("../../outside")

    def test_failed_atomic_save_keeps_previous_file(self):
        path = self.root / "data.json"
        atomic_json(path, {"old": True})
        with patch("workspace.os.replace", side_effect=OSError("locked")):
            with self.assertRaises(OSError):
                atomic_json(path, {"new": True})
        self.assertEqual(json.loads(path.read_text()), {"old": True})
        self.assertEqual(list(self.root.glob("*.tmp")), [])


class PresentationTests(unittest.TestCase):
    def test_global_percentages_reject_invalid_and_accept_zero(self):
        rows = [{"name": "zero", "percent": "0"}, {"name": "valid", "percent": "47.2"},
                {"name": "bad", "percent": "NaN"}, {"name": "high", "percent": 101}]
        self.assertEqual(percentages({"achievementpercentages": {"achievements": rows}}), {"zero": 0, "valid": 47.2})

    def test_public_schema_extracts_exact_keys_and_filenames(self):
        text = r'{\"api_name\":\"EXAMPLE\",\"name\":\"A public title\",\"icon_achieved\":\"abc.jpg\",\"icon_unachieved\":\"def.jpg\"}'
        self.assertEqual(parse_icons(text), {"EXAMPLE": {"unlocked": "abc.jpg", "locked": "def.jpg"}})
        self.assertEqual(parse_icons(text.replace("abc.jpg", "../../x.jpg")), {})

    def test_sort_keeps_unknown_rarity_and_locked_dates_last(self):
        rows = [dict(name="A", rarity=None, unlock_time=0), dict(name="B", rarity=90, unlock_time=100), dict(name="C", rarity=0, unlock_time=200)]
        self.assertEqual([x["name"] for x in order_achievements(rows, "Rarest first")], ["C", "B", "A"])
        self.assertEqual([x["name"] for x in order_achievements(rows, "Most common first")], ["B", "C", "A"])
        self.assertEqual([x["name"] for x in order_achievements(rows, "Newest unlocks")], ["C", "B", "A"])
        self.assertEqual([x["name"] for x in order_achievements(rows, "Oldest unlocks")], ["B", "C", "A"])

    def test_artwork_is_cached_and_unsafe_hosts_are_not_requested(self):
        with tempfile.TemporaryDirectory() as folder:
            posted, results = [], []
            media = Media(folder, posted.append)
            with patch("media.fetch", return_value=b"\xff\xd8example") as request:
                media.image("https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/440/" + "a" * 40 + ".jpg", results.append)
                media.image("https://untrusted.invalid/image.jpg", results.append)
                media.pool.shutdown(wait=True)
                for callback in posted:
                    callback()
                media.image("https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/440/" + "a" * 40 + ".jpg", results.append)
                self.assertEqual(request.call_count, 1)
            self.assertEqual(len(results), 2)
            self.assertTrue(results[0].is_file())
            media.close()

    def test_disabled_artwork_makes_no_requests(self):
        with tempfile.TemporaryDirectory() as folder, patch("media.fetch") as request:
            media = Media(folder, lambda callback: callback(), enabled=False)
            media.game_icon(440, Mock())
            media.metadata(440, Mock())
            media.close()
            request.assert_not_called()


class UpdateTests(unittest.TestCase):
    def test_repository_validation(self):
        self.assertEqual(repository("https://github.com/owner/App/"), "owner/App")
        for value in ("https://evil.invalid/repo", "../..", "owner/a/b", "", "a/x?token=secret"):
            with self.assertRaises(ValueError):
                repository(value)

    def test_version_ordering(self):
        self.assertLess(version_key("v0.6.0-preview"), version_key("0.6.0"))
        self.assertLess(version_key("0.9.0"), version_key("0.10.0"))
        self.assertLess(version_key("0.6.0-rc.2"), version_key("0.6.0-rc.10"))
        with self.assertRaises(ValueError):
            version_key("0.6.0-surprise")

    def test_release_lookup_filters_drafts_and_external_urls(self):
        payload = [dict(tag_name="v0.7.0", html_url="https://github.com/a/App/releases/tag/v0.7.0"),
                   dict(tag_name="v9.0.0", html_url="https://evil.invalid/installer"),
                   dict(tag_name="v8.0.0", draft=True, html_url="https://github.com/a/App/releases/tag/v8.0.0")]
        with patch("updates.fetch", return_value=json.dumps(payload).encode()):
            result = check_release("a/App", "0.6.0-preview")
        self.assertTrue(result["newer"])
        self.assertTrue(result["url"].endswith("v0.7.0"))

    def test_empty_release_channel_does_not_claim_current(self):
        with patch("updates.fetch", return_value=b"[]"):
            self.assertEqual(check_release("a/App", "0.6.0-preview")["message"], "No published releases are available yet.")

    def test_repository_case_does_not_hide_valid_release(self):
        data = [dict(tag_name="v0.7.0", html_url="https://github.com/Owner/App/releases/tag/v0.7.0")]
        with patch("updates.fetch", return_value=json.dumps(data).encode()):
            self.assertTrue(check_release("owner/app", "0.6.0-preview")["newer"])

    def test_stable_channel_does_not_offer_previews(self):
        data = [dict(tag_name="v0.7.0-preview", prerelease=True, html_url="https://github.com/a/App/releases/tag/v0.7.0-preview")]
        with patch("updates.fetch", return_value=json.dumps(data).encode()):
            self.assertFalse(check_release("a/App", "0.6.0")["newer"])


class NewUITests(unittest.TestCase):
    def setUp(self):
        from test_modern_ui import APP
        from modern_ui import Desk
        from demo import DemoSession
        self.app = APP
        self.window = Desk(demo=True, hidden=True)
        self.window.account_id = self.window.library_account_id = "DEMO"
        self.window.client = Mock()
        self.window.game = Game(0, "Game", True)
        self.window.rows = DemoSession().read()
        self.window.library = [Game(0, "Game", True), Game(10, "Remote", False)]
        self.window.render()
        self.app.processEvents()

    def tearDown(self):
        self.window.desired.clear()
        self.window.busy = False
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_library_favorites_do_not_modify_achievements(self):
        self.window.browse_library()
        page = self.window.library_page
        page.games.setCurrentRow(1)
        page.toggle_favorite()
        page.filter.setCurrentText("Favorites")
        self.assertEqual(page.games.count(), 1)
        self.assertEqual(page.selected().app_id, 10)
        self.assertEqual(self.window.client.mock_calls, [])

    def test_review_compares_saved_and_requested_states(self):
        self.window.toggle_achievement("EXPLORER", True)
        dialog = self.window.make_review_dialog()
        item = dialog.listing.topLevelItem(0)
        self.assertEqual((item.text(1), item.text(2)), ("Locked", "Unlocked"))
        self.assertFalse(dialog.apply_button.isEnabled())
        dialog.close()

    def test_preferences_change_density_and_motion_without_writes(self):
        dialog = self.window.make_settings_dialog()
        dialog.density.setCurrentText("Compact")
        dialog.motion.setChecked(True)
        card = self.window.cards["EXPLORER"]
        self.assertEqual(card.layout().contentsMargins().top(), 10)
        self.assertTrue(card.switch.property("reduce_motion"))
        self.assertEqual(self.window.client.mock_calls, [])
        dialog.close()

    def test_global_sort_does_not_drop_pending_changes(self):
        self.window.presentation[0] = dict(percentages={"EXPLORER": 0})
        self.window.toggle_achievement("EXPLORER", True)
        self.window.set_sort("Rarest first")
        self.assertEqual(list(self.window.cards)[0], "EXPLORER")
        self.assertEqual(self.window.desired, {"EXPLORER": True})

    def test_history_is_account_scoped_in_ui(self):
        from library_view import history_dialog
        activity = self.window.workspace.start_activity("OTHER", Game(99, "Other game"), [])
        dialog = history_dialog(self.window)
        self.assertEqual(dialog.tree.topLevelItemCount(), 0)
        dialog.close()

    def test_concealed_achievements_do_not_show_icon(self):
        self.window.icon_paths[(0, "SECRET", "locked")] = "secret.jpg"
        record = self.window.display_record(next(row for row in self.window.rows if row.key == "SECRET"))
        self.assertTrue(record["concealed"])
        self.assertIsNone(record["icon_path"])

    def test_cancel_is_not_available_for_apply(self):
        gate = threading.Event()
        self.window.task(lambda: gate.wait(2), lambda _: None, uncertain=True, can_cancel=True)
        self.assertFalse(self.window.can_cancel)
        self.window.cancel_read()
        self.assertFalse(self.window.cancel_requested)
        gate.set()
        # Complete the queued callback before disposing the window.
        import time
        deadline = time.monotonic() + 2
        while self.window.busy and time.monotonic() < deadline:
            self.window.poll()
            time.sleep(.01)
        self.assertFalse(self.window.busy)

    def test_failed_read_exposes_retry_without_changing_drafts(self):
        self.window.toggle_achievement("EXPLORER", True)
        retry = Mock()
        def fail():
            raise OSError("Steam unavailable")
        self.window.task(fail, Mock(), can_cancel=True, retry=retry)
        import time
        deadline = time.monotonic() + 2
        while self.window.busy and time.monotonic() < deadline:
            self.window.poll()
            time.sleep(.01)
        self.assertFalse(self.window.error_bar.isHidden())
        self.assertFalse(self.window.retry_button.isHidden())
        self.assertEqual(self.window.desired, {"EXPLORER": True})
        self.window.retry()
        retry.assert_called_once_with()


class ReadCancellationTests(unittest.TestCase):
    def test_cancel_before_connection_does_not_start_worker(self):
        from transport import GameClient
        factory = Mock()
        client = GameClient(10, worker_factory=factory)
        client.cancel()
        with self.assertRaisesRegex(RuntimeError, "cancelled"):
            client.receive()
        factory.assert_not_called()

    def test_cancel_running_read_closes_helper(self):
        from transport import GameClient
        entered, cancelled = threading.Event(), threading.Event()
        worker = Mock()
        def receive():
            entered.set()
            if cancelled.wait(2):
                raise RuntimeError("read cancelled")
            raise AssertionError("Read did not cancel")
        worker.receive.side_effect = receive
        worker.cancel.side_effect = cancelled.set
        client = GameClient(10, worker_factory=lambda *_: worker)
        errors = []
        def read():
            try:
                client.receive()
            except Exception as exc:
                errors.append(exc)
        thread = threading.Thread(target=read)
        thread.start()
        self.assertTrue(entered.wait(2))
        client.cancel()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        worker.close.assert_called_once_with()
        self.assertIsInstance(errors[0], RuntimeError)


if __name__ == "__main__":
    unittest.main()
