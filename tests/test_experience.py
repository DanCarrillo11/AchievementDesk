"""Usability changes operate only on the loaded snapshot and local preferences."""
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from experience import clean_view, explain_error, match_ranges
from workspace import Workspace
from domain import Achievement
from demo import DemoSession
from library import Game


class ViewDataTests(unittest.TestCase):
    def test_literal_unicode_matching_keeps_character_offsets(self):
        self.assertEqual(match_ranges("🚀 Straße Straße", "SS"), [(6, 7), (13, 14)])
        self.assertEqual(match_ranges("a.b axb", "."), [(1, 2)])
        self.assertEqual(match_ranges("Anything", ""), [])

    def test_bad_view_values_recover_without_changing_preference_types(self):
        value = clean_view(dict(query=["bad"], filter="Unknown", sort=[], page=True, scroll=-12))
        self.assertEqual(value, dict(query="", filter="All", sort="Steam order", page=0, scroll=0))

    def test_views_survive_restart_and_are_scoped_by_game_and_account(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Workspace(folder)
            workspace.save_game_view("A", 10, dict(query="Explorer", filter="Locked", sort="Name Z–A", page=3, scroll=185))
            loaded = Workspace(folder)
            self.assertEqual(loaded.game_view("A", 10)["scroll"], 185)
            self.assertEqual(loaded.game_view("A", 10)["query"], "Explorer")
            self.assertEqual(loaded.game_view("B", 10)["query"], "")
            self.assertEqual(loaded.game_view("A", 20)["query"], "")

    def test_corrupt_views_are_ignored_and_history_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Workspace(folder)
            workspace.profile("A")["views"] = "invalid"
            self.assertEqual(workspace.game_view("A", 10)["page"], 0)
            with patch.object(workspace, "save"):
                for i in range(210):
                    workspace.save_game_view("A", i, dict(query="x" * 400))
            self.assertEqual(len(workspace.profile("A")["views"]), 200)
            self.assertEqual(len(workspace.game_view("A", 209)["query"]), 256)

    def test_unknown_apply_outcomes_always_have_cautious_explanation(self):
        title, hint = explain_error("Timed out", uncertain=True)
        self.assertIn("Check", title)
        self.assertIn("may have been saved", hint)
        self.assertNotIn("retry the read", hint)


class WorkspaceExperienceTests(unittest.TestCase):
    def setUp(self):
        from test_modern_ui import APP
        from modern_ui import Desk
        self.app = APP
        self.window = Desk(demo=True, hidden=True)
        self.window.account_id = self.window.library_account_id = "DEMO"
        self.window.client = Mock()
        self.window.game = Game(10, "A long but recognizable game title")
        self.window.rows = DemoSession().read()
        self.window.render()
        self.app.processEvents()

    def tearDown(self):
        self.window.desired.clear()
        self.window.busy = False
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_undo_restores_the_previous_draft_without_a_backend_request(self):
        self.window.toggle_achievement("EXPLORER", True)
        self.window.toggle_achievement("FIRST_STEP", False)
        self.window.undo_draft()
        self.assertEqual(self.window.desired, {"EXPLORER": True})
        self.window.undo_draft()
        self.assertEqual(self.window.desired, {})
        self.assertEqual(self.window.client.mock_calls, [])

    def test_batch_is_one_undo_step_and_discard_can_be_undone(self):
        self.window.selected = {"EXPLORER", "COLLECTOR"}
        self.window.queue_state(True)
        previous = dict(self.window.desired)
        self.assertEqual(len(self.window.draft_history), 1)
        self.window.clear_queue()
        self.window.undo_draft()
        self.assertEqual(self.window.desired, previous)
        self.window.undo_draft()
        self.assertEqual(self.window.desired, {})

    def test_noop_edits_do_not_fill_undo_history(self):
        self.window.toggle_achievement("FIRST_STEP", True)
        self.assertEqual(self.window.draft_history, [])
        for i in range(120):
            self.window.toggle_achievement("EXPLORER", bool(i % 2))
        self.assertLessEqual(len(self.window.draft_history), 100)

    def test_undo_cannot_cross_an_account_or_apply_boundary(self):
        self.window.toggle_achievement("EXPLORER", True)
        self.window.account_id = "OTHER"
        self.window.desired.clear()
        self.window.undo_draft()
        self.assertEqual(self.window.desired, {})
        self.window.account_id = "DEMO"
        self.window.toggle_achievement("EXPLORER", True)
        self.window.set_rows(dict(account_id="DEMO", achievements=[asdict(r) for r in self.window.rows]))
        self.window.undo_draft()
        self.assertEqual(self.window.desired, {})

    def test_undo_is_disabled_while_an_operation_is_running(self):
        self.window.toggle_achievement("EXPLORER", True)
        self.window.busy = True
        self.window.undo_draft()
        self.assertEqual(self.window.desired, {"EXPLORER": True})

    def test_undo_cannot_reinstate_an_unlock_that_is_now_restricted(self):
        self.window.toggle_achievement("EXPLORER", True)
        self.window.clear_queue()
        with patch("modern_ui.unlock_restriction", return_value="Archived achievement"):
            self.window.undo_draft()
        self.assertEqual(self.window.desired, {})
        self.assertEqual(self.window.client.mock_calls, [])

    def test_ctrl_z_in_search_undoes_typing_and_leaves_drafts_alone(self):
        self.window.toggle_achievement("EXPLORER", True)
        self.window.show()
        self.window.search.setFocus()
        self.app.processEvents()
        self.window.search.insert("Explorer")
        self.window.undo_shortcut()
        self.assertEqual(self.window.search.text(), "")
        self.assertEqual(self.window.desired, {"EXPLORER": True})

    def test_details_are_embedded_read_only_and_follow_pending_edits(self):
        self.window.cards["EXPLORER"].details_button.click()
        self.assertFalse(self.window.details_panel.isHidden())
        self.assertTrue(self.window.details_panel.identifier.isReadOnly())
        self.window.toggle_achievement("EXPLORER", True)
        self.assertIn("pending review", self.window.details_panel.state.text())
        self.assertEqual(self.window.client.mock_calls, [])

    def test_hidden_details_and_identifier_are_not_revealed_or_copied(self):
        with patch("achievement_details.QApplication.clipboard") as clipboard:
            self.window.show_details("SECRET")
            self.assertEqual(self.window.details_panel.name.text(), "Hidden achievement")
            self.assertNotEqual(self.window.details_panel.identifier.text(), "SECRET")
            self.window.details_panel.copy_button.click()
            clipboard.assert_not_called()
            self.window.set_reveal(True)
            self.window.details_panel.copy_button.click()
            clipboard.return_value.setText.assert_called_once_with("SECRET")

    def test_clear_filters_keeps_the_review_queue(self):
        self.window.toggle_achievement("EXPLORER", True)
        self.window.search.setText("nothing matches this")
        self.assertFalse(self.window.empty_panel.isHidden())
        self.window.clear_filters_button.click()
        self.assertIn("EXPLORER", self.window.cards)
        self.assertEqual(self.window.desired, {"EXPLORER": True})
        self.assertEqual(self.window.client.mock_calls, [])

    def test_search_highlights_keep_game_text_plain_including_markup(self):
        from PySide6.QtCore import Qt
        self.window.rows = [Achievement("MARKUP", "<b>Literal title</b>", "Straße 🚀", False)]
        self.window.search.setText("ss")
        card = self.window.cards["MARKUP"]
        self.assertEqual(card.title.textFormat(), Qt.TextFormat.PlainText)
        self.assertEqual(card.title.text(), "<b>Literal title</b>")
        self.assertEqual(card.description.query, "ss")
        self.window.show()
        self.app.processEvents()
        self.assertFalse(card.grab().isNull())

    def test_saved_game_view_restores_filter_sort_page_and_scroll(self):
        rows = [Achievement(f"A{i}", f"Task {i:03}", "Description", False) for i in range(100)]
        self.window.workspace.save_game_view("DEMO", 10, dict(query="Task", filter="Locked", sort="Name A–Z", page=2, scroll=120))
        self.window.show()
        self.app.processEvents()
        self.window._restore_next_view = True
        self.window.set_rows(dict(account_id="DEMO", achievements=[asdict(r) for r in rows]))
        for _ in range(4):
            self.app.processEvents()
        self.assertEqual((self.window.search.text(), self.window.achievement_filter, self.window.page), ("Task", "Locked", 2))
        self.assertEqual(self.window.achievement_sort, "Name A–Z")
        self.assertEqual(self.window.scroll.verticalScrollBar().value(), 120)
        self.assertEqual(self.window.client.mock_calls, [])

    def test_a_new_search_supersedes_deferred_scroll_restore(self):
        self.window.restore_view(dict(query="", filter="All", sort="Steam order", page=0, scroll=500))
        self.window.search.setText("Explorer")
        self.app.processEvents()
        self.assertEqual(self.window.scroll.verticalScrollBar().value(), 0)
        self.assertFalse(self.window._restoring_view)

    def test_rerendering_artwork_preserves_scroll_position(self):
        self.window.rows = [Achievement(str(i), f"Task {i}", "Description", False) for i in range(80)]
        self.window.render()
        self.window.show()
        self.app.processEvents()
        self.window.scroll.verticalScrollBar().setValue(160)
        self.window.render()
        self.app.processEvents()
        self.assertEqual(self.window.scroll.verticalScrollBar().value(), 160)

    def test_errors_remain_visible_in_library_and_details_are_collapsed(self):
        self.window.browse_library()
        self.window.show()
        self.window.show_problem("Steam is offline. Native detail: diagnostic-123", retry=True)
        self.app.processEvents()
        self.assertTrue(self.window.error_bar.isVisible())
        self.assertNotIn("diagnostic-123", self.window.error_label.text())
        self.assertTrue(self.window.error_details.isHidden())
        self.window.error_details_button.click()
        self.assertIn("diagnostic-123", self.window.error_details.toPlainText())
        self.assertTrue(self.window.error_details.isVisible())

    def test_confirmed_results_use_a_notice_and_cannot_be_undone(self):
        self.window.toggle_achievement("EXPLORER", True)
        result = dict(status="confirmed", confirmed=["EXPLORER"], rejected=[], unconfirmed=[],
                      snapshot="synthetic.json", message="Synthetic only", achievements=[asdict(r) for r in self.window.rows])
        with patch("modern_ui.QMessageBox.information") as modal:
            self.window.applied(dict(result=result))
            modal.assert_not_called()
        self.assertFalse(self.window.notice_bar.isHidden())
        self.assertEqual(self.window.draft_history, [])

    def test_partial_results_do_not_show_a_success_notice_or_automatic_retry(self):
        result = dict(status="partial", confirmed=["FIRST_STEP"], rejected=["EXPLORER"], unconfirmed=[],
                      snapshot="synthetic.json", message="Synthetic only", achievements=[asdict(r) for r in self.window.rows])
        self.window.applied(dict(result=result))
        self.assertTrue(self.window.notice_bar.isHidden())
        self.assertFalse(self.window.error_bar.isHidden())
        self.assertTrue(self.window.retry_button.isHidden())
        self.assertIn("1 rejected", self.window.error_label.text())

    def test_compact_header_and_details_fit_the_minimum_window(self):
        self.window.resize(1020, 760)
        self.window.show_details("EXPLORER")
        self.window.toggle_achievement("EXPLORER", True)
        self.window.show()
        self.app.processEvents()
        self.assertLessEqual(self.window.hero.height(), 115)
        bottom = self.window.review_button.mapTo(self.window, self.window.review_button.rect().bottomRight())
        self.assertTrue(self.window.rect().contains(bottom))
        self.assertTrue(self.window.rect().contains(self.window.details_panel.mapTo(self.window, self.window.details_panel.rect().bottomRight())))
        self.assertEqual(self.window.scroll.horizontalScrollBar().maximum(), 0)


if __name__ == "__main__":
    unittest.main()
