import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import unittest
from unittest.mock import Mock, patch
from dataclasses import asdict
from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtCore import Qt
from modern_ui import Desk
from domain import Achievement
from demo import DemoSession
from library import Game

APP = QApplication.instance() or QApplication([])
APP.setStyle("Fusion")


class ModernUITests(unittest.TestCase):
    def setUp(self):
        self.window = Desk(demo=True, hidden=True)
        self.window.client = Mock()
        self.window.account_id = "DEMO"
        self.window.game = Game(0, "Demo game", True)
        self.window.rows = DemoSession().read()
        self.window.render()
        APP.processEvents()

    def tearDown(self):
        self.window.desired.clear()
        self.window.busy = False
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()

    def test_offscreen_platform_never_uses_interactive_desktop(self):
        self.assertEqual(APP.platformName(), "offscreen")
        self.assertFalse(self.window.isVisible())

    def test_initial_saved_states(self):
        self.assertTrue(self.window.cards["FIRST_STEP"].switch.isChecked())
        self.assertFalse(self.window.cards["EXPLORER"].switch.isChecked())

    def test_toggle_does_not_call_backend(self):
        self.window.cards["EXPLORER"].switch.click()
        self.assertEqual(self.window.desired, {"EXPLORER": True})
        self.assertEqual(self.window.client.mock_calls, [])
        self.assertFalse(self.window.rows[1].unlocked)

    def test_toggle_back_removes_pending_change(self):
        self.window.cards["EXPLORER"].switch.click()
        self.window.cards["EXPLORER"].switch.click()
        self.assertEqual(self.window.desired, {})

    def test_pending_bar_only_appears_with_changes(self):
        self.assertTrue(self.window.pending_bar.isHidden())
        self.window.toggle_achievement("EXPLORER", True)
        self.assertFalse(self.window.pending_bar.isHidden())
        self.window.clear_queue()
        self.assertTrue(self.window.pending_bar.isHidden())

    def test_relock_is_pending_not_immediate(self):
        self.window.cards["FIRST_STEP"].switch.click()
        self.assertEqual(self.window.desired, {"FIRST_STEP": False})
        self.assertTrue(self.window.rows[0].unlocked)

    def test_discard_resets_switches(self):
        self.window.toggle_achievement("EXPLORER", True)
        self.window.clear_queue()
        self.assertFalse(self.window.cards["EXPLORER"].switch.isChecked())

    def test_busy_disables_switches_and_actions(self):
        self.window.busy = True
        self.window.sync_controls()
        self.window.cards["EXPLORER"].switch.click()
        self.assertEqual(self.window.desired, {})
        self.assertFalse(self.window.cards["EXPLORER"].switch.isEnabled())
        self.assertFalse(self.window.catalog_action.isEnabled())

    def test_no_client_disables_switches(self):
        self.window.client = None
        self.window.sync_controls()
        self.assertFalse(self.window.cards["EXPLORER"].switch.isEnabled())

    def test_hidden_details_are_concealed(self):
        card = self.window.cards["SECRET"]
        self.assertEqual(card.title.text(), "Hidden achievement")
        self.assertNotIn("curtain", card.description.text())
        self.window.search.setText("curtain")
        self.assertEqual(self.window.filtered, [])

    def test_settings_can_reveal_hidden_details(self):
        self.window.set_reveal(True)
        self.assertEqual(self.window.cards["SECRET"].title.text(), "Behind the curtain")

    def test_locked_filter_uses_saved_state(self):
        self.window.toggle_achievement("EXPLORER", True)
        self.window.set_filter("Locked")
        self.assertIn("EXPLORER", self.window.cards)
        self.assertNotIn("FIRST_STEP", self.window.cards)

    def test_pending_filter(self):
        self.window.toggle_achievement("EXPLORER", True)
        self.window.set_filter("Pending")
        self.assertEqual(list(self.window.cards), ["EXPLORER"])

    def test_search_covers_entire_loaded_list(self):
        self.window.rows = [Achievement(f"A{i}", f"Achievement {i}", "Description", False) for i in range(60)]
        self.window.render()
        self.assertEqual(len(self.window.cards), 25)
        self.window.search.setText("A59")
        self.assertEqual(list(self.window.cards), ["A59"])

    def test_pagination_preserves_changes(self):
        self.window.rows = [Achievement(f"A{i}", f"Achievement {i}", "Description", False) for i in range(60)]
        self.window.render()
        self.window.turn_page(1)
        self.window.toggle_achievement("A25", True)
        self.assertEqual(self.window.page, 1)
        self.window.turn_page(-1)
        self.assertEqual(self.window.desired, {"A25": True})

    def test_library_tools_are_grouped_separately_from_settings(self):
        text = [action.text() for action in self.window.library_tools_menu.actions()]
        for name in ("Refresh library", "Update game catalog", "Open game by App ID…"):
            self.assertIn(name, text)
        self.assertNotIn("Unlock selected", text)
        primary_text = [button.text() for button in self.window.findChildren(QPushButton)]
        self.assertNotIn("Update game catalog", primary_text)
        self.assertNotIn("Export", primary_text)

    def test_game_tools_contains_only_current_game_operations(self):
        text = [action.text() for action in self.window.game_menu.actions()]
        for name in ("Refresh achievements", "Export achievement state…", "View on Steam"):
            self.assertIn(name, text)
        self.assertNotIn("Unlock selected", text)
        self.assertNotIn("Update game catalog", text)

    def test_selection_tools_only_appear_for_selection_and_do_not_clear_drafts(self):
        self.assertTrue(self.window.selection_button.isHidden())
        self.window.select_row("EXPLORER")
        self.assertFalse(self.window.selection_button.isHidden())
        self.assertEqual(self.window.selection_button.text(), "1 selected")
        self.window.unlock_action.trigger()
        self.assertEqual(self.window.desired, {"EXPLORER": True})
        self.window.clear_selection()
        self.assertTrue(self.window.selection_button.isHidden())
        self.assertEqual(self.window.desired, {"EXPLORER": True})
        self.assertEqual(self.window.client.mock_calls, [])

    def test_settings_updates_hidden_details_without_connecting(self):
        dialog = self.window.make_settings_dialog()
        dialog.reveal_checkbox.setChecked(True)
        self.assertEqual(self.window.cards["SECRET"].title.text(), "Behind the curtain")
        self.assertEqual(self.window.client.mock_calls, [])
        dialog.deleteLater()

    def test_settings_respects_busy_state(self):
        self.window.busy = True
        dialog = self.window.make_settings_dialog()
        self.assertFalse(dialog.reveal_checkbox.isEnabled())
        dialog.deleteLater()

    def test_small_window_keeps_review_actions_visible(self):
        self.window.resize(1020, 760)
        self.window.toggle_achievement("EXPLORER", True)
        self.window.show()
        APP.processEvents()
        self.assertTrue(self.window.review_button.isVisible())
        bounds = self.window.review_button.rect()
        self.assertTrue(self.window.rect().contains(self.window.review_button.mapTo(self.window, bounds.bottomRight())))

    def test_achievement_labels_are_plain_text(self):
        self.window.rows = [Achievement("HTML", "<b>Literal title</b>", "<i>Literal description</i>", False)]
        self.window.render()
        self.assertEqual(self.window.cards["HTML"].title.textFormat(), Qt.TextFormat.PlainText)
        self.assertEqual(self.window.cards["HTML"].description.textFormat(), Qt.TextFormat.PlainText)

    def test_library_filters_and_ids(self):
        self.window.library = [Game(10, "Local", True), Game(20, "Remote", False)]
        self.window.filter_games()
        self.assertEqual(self.window.games.count(), 2)
        self.window.set_library_filter("Not installed")
        self.assertEqual(self.window.games.count(), 1)
        self.assertEqual(self.window.games.item(0).data(Qt.ItemDataRole.UserRole).app_id, 20)
        self.window.set_library_filter("All games")
        self.window.game_search.setText("10")
        self.assertEqual(self.window.games.count(), 1)

    def test_startup_loads_saved_library_without_full_scan(self):
        self.window.demo = False
        reply = dict(account_id="76561198000000001", cached=True,
                     games=[asdict(Game(10, "Cached game", True))])
        with patch("modern_ui.WorkerClient") as worker, \
             patch.object(self.window, "task", side_effect=lambda job, done, **kwargs: done(job())):
            worker.return_value.receive.return_value = reply
            self.window.load_library()
            worker.assert_called_once_with(0, library=True, refresh_library=False)
            worker.return_value.close.assert_called_once()
        self.assertEqual([game.app_id for game in self.window.library], [10])
        self.assertIn("Saved library", self.window.status.text())

    def test_refresh_action_forces_full_scan(self):
        self.window.demo = False
        reply = dict(account_id="76561198000000001", cached=False,
                     games=[asdict(Game(30, "New game", False))])
        with patch("modern_ui.WorkerClient") as worker, \
             patch.object(self.window, "task", side_effect=lambda job, done, **kwargs: done(job())):
            worker.return_value.receive.return_value = reply
            self.window.refresh_library_action.trigger()
            worker.assert_called_once_with(0, library=True, refresh_library=True)
        self.assertEqual([game.app_id for game in self.window.library], [30])
        self.assertIn("Steam library refreshed", self.window.status.text())

    def test_selection_batch_prepares_only_selected(self):
        self.window.select_row("EXPLORER")
        self.window.select_row("COLLECTOR", True)
        self.window.queue_state(True)
        self.assertEqual(self.window.desired, {"EXPLORER": True, "COLLECTOR": True})
        self.assertEqual(self.window.client.mock_calls, [])

    def test_review_requires_explicit_confirmation(self):
        self.window.toggle_achievement("EXPLORER", True)
        dialog = self.window.make_review_dialog()
        self.assertFalse(dialog.apply_button.isEnabled())
        dialog.consent.setChecked(True)
        self.assertTrue(dialog.apply_button.isEnabled())
        self.assertEqual(self.window.client.mock_calls, [])
        dialog.deleteLater()

    def test_review_does_not_reveal_hidden_name(self):
        self.window.toggle_achievement("SECRET", True)
        dialog = self.window.make_review_dialog()
        self.assertIn("Hidden achievement", dialog.listing.topLevelItem(0).text(0))
        self.assertNotIn("curtain", dialog.listing.topLevelItem(0).text(0))
        dialog.deleteLater()

    def test_noninstalled_game_uses_same_backend(self):
        self.window.library_account_id = "DEMO"
        with patch("modern_ui.GameClient") as client, patch.object(self.window, "task", side_effect=lambda job, done, **kwargs: done(job())):
            client.return_value.receive.return_value = dict(account_id="DEMO", achievements=[asdict(row) for row in DemoSession().read()])
            self.window.connect(Game(100, "Remote game", False))
            client.assert_called_once_with(100, True)
        self.assertEqual(self.window.game.app_id, 100)

    def test_apply_result_does_not_reconnect(self):
        with patch.object(self.window, "refresh") as refresh, patch("modern_ui.QMessageBox.information"):
            self.window.applied(dict(result=dict(status="confirmed", confirmed=["EXPLORER"], rejected=[], unconfirmed=[],
                snapshot="demo.json", message="Demo confirmed", achievements=[asdict(row) for row in DemoSession().read()])))
            refresh.assert_not_called()

    def test_offscreen_paint_has_no_missing_widget_methods(self):
        image = self.window.grab()
        self.assertFalse(image.isNull())
        self.assertGreaterEqual(image.width(), 970)
