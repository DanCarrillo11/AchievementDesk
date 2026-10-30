import json
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from unittest.mock import Mock, patch
from completion import parse_completion, read_completion, set_progress, unlock_restriction
from compatibility import observe_read, observe_result, status
from domain import Achievement
from workspace import Workspace

ACCOUNT = "76561198000000000"  # Synthetic fixture, never requested from Steam.


def page(completed=False, achievable=True, archived=False, dlc=0, account=ACCOUNT, hash=7, include_user=True):
    group = dict(id=1, name="Main campaign", archived=False, developeronly=False, ispublic=True, dlcappid=dlc,
                 achievements=[dict(api_name="A", archived=archived), dict(api_name="B", archived=False)])
    schema = dict(appid=10, schema_hash=7, groups=[group])
    user = dict(appid=10, steamid=account, schema_hash=hash, groups={"1": dict(groupid=1,
                is_completed=completed, is_achievable=achievable, time_completed=100 if completed else 0)}, achievements={})
    queries = [dict(queryKey=["achievements", 10, "schema_v2"], state=dict(status="success", data=schema))]
    if include_user:
        queries += [dict(queryKey=["achievements", 10, "user_achievements", account], state=dict(status="success", data=user))]
    return '<script id="valve-ssr-data" type="application/json">' + json.dumps(dict(loaderData=[json.dumps(dict(queries=queries))])) + '</script>'


class CompletionParsingTests(unittest.TestCase):
    def test_official_completion_survives_incomplete_current_progress(self):
        data = parse_completion(page(completed=True), 10, ACCOUNT)
        group = data["groups"][0]
        self.assertTrue(group["completed"])
        self.assertEqual(set_progress(group, [Achievement("A", "A", "", False)]), (0, 2, 1))

    def test_full_progress_does_not_create_official_trophy(self):
        data = parse_completion(page(include_user=False), 10, ACCOUNT)
        self.assertIsNone(data["groups"][0]["completed"])
        self.assertEqual(set_progress(data["groups"][0], [Achievement("A", "A", "", True), Achievement("B", "B", "", True)]), (2, 2, 0))

    def test_wrong_account_completion_is_not_used(self):
        data = parse_completion(page(completed=True, account="76561198000000001"), 10, ACCOUNT)
        self.assertIsNone(data["groups"][0]["completed"])

    def test_changed_schema_drops_completion_flags(self):
        data = parse_completion(page(completed=True, hash=9), 10, ACCOUNT)
        self.assertIsNone(data["groups"][0]["completed"])

    def test_other_game_schema_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_completion(page(), 11, ACCOUNT)

    def test_login_or_private_page_never_means_no_trophy(self):
        fetch = Mock(side_effect=[b'<html>Private profile</html>', page(include_user=False).encode()])
        data = read_completion(10, ACCOUNT, fetch)
        self.assertIsNone(data["groups"][0]["completed"])
        self.assertIn("private", data["notice"])
        self.assertEqual(fetch.call_count, 2)

    def test_identifiers_cannot_inject_a_url(self):
        fetch = Mock()
        with self.assertRaises(ValueError):
            read_completion(10, "../other", fetch)
        fetch.assert_not_called()

    def test_archived_achievement_excluded_from_required_progress_and_unlocks(self):
        data = parse_completion(page(archived=True), 10, ACCOUNT)
        self.assertEqual(set_progress(data["groups"][0], [Achievement("B", "B", "", True)]), (1, 1, 0))
        self.assertIn("Archived", unlock_restriction(data, "A"))
        self.assertEqual(unlock_restriction(data, "B"), "")

    def test_unowned_and_unconfirmed_dlc_are_not_queued(self):
        data = parse_completion(page(dlc=999, achievable=False), 10, ACCOUNT)
        self.assertIn("cannot be earned", unlock_restriction(data, "A"))
        data = parse_completion(page(dlc=999, include_user=False), 10, ACCOUNT)
        self.assertIn("not confirmed", unlock_restriction(data, "A"))

    def test_missing_metadata_does_not_invent_restrictions(self):
        self.assertEqual(unlock_restriction({}, "UNKNOWN"), "")


class CompatibilityEvidenceTests(unittest.TestCase):
    def test_read_is_not_proof_of_edit_support(self):
        evidence = observe_read({}, 30)
        self.assertEqual(status(evidence)[0], "Achievements readable")
        self.assertNotIn("unlock_seen", evidence)

    def test_only_confirmed_direction_is_recorded(self):
        changes = [dict(key="A", after=True), dict(key="B", after=False)]
        value = observe_result({}, dict(status="partial", confirmed=["A"], rejected=["B"]), changes)
        self.assertTrue(value["unlock_seen"])
        self.assertFalse(value.get("relock_seen", False))
        self.assertEqual(status(value)[0], "Changes rejected")

    def test_unknown_outcome_never_becomes_compatible(self):
        value = observe_result({}, dict(status="unconfirmed", confirmed=[], unconfirmed=["A"]), [dict(key="A", after=True)])
        self.assertEqual(status(value)[0], "Changes unconfirmed")
        self.assertNotIn("unlock_seen", value)

    def test_rejected_write_is_not_erased_by_successful_read(self):
        value = observe_read(dict(rejected=1, last_result="rejected"), 12)
        self.assertEqual(status(value)[0], "Changes rejected")

    def test_account_scoping_and_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            w = Workspace(folder)
            w.save_compatibility("A", 10, observe_read({}, 0))
            w = Workspace(folder)
            self.assertEqual(status(w.compatibility("A", 10))[0], "No achievements")
            self.assertEqual(status(w.compatibility("B", 10))[0], "Not checked")


from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from modern_ui import Desk
from library import Game

APP = QApplication.instance() or QApplication([])
APP.setStyle("Fusion")


class CompletionUITests(unittest.TestCase):
    def setUp(self):
        self.desk = Desk(demo=True, hidden=True)
        self.desk.account_id = self.desk.library_account_id = ACCOUNT
        self.desk.game = Game(10, "Example game")
        self.desk.client = Mock()
        self.desk.library = [self.desk.game, Game(11, "Other")]
        self.desk.rows = [Achievement("A", "Alpha", "", False), Achievement("B", "Beta", "", False)]
        self.key = (ACCOUNT, 10)
        self.desk.completions[self.key] = parse_completion(page(), 10, ACCOUNT)
        self.desk.render()

    def tearDown(self):
        self.desk.desired.clear()
        self.desk.busy = False
        self.desk.close()
        self.desk.deleteLater()
        APP.processEvents()

    def test_sets_are_embedded_in_same_window(self):
        self.desk.show_completion()
        self.assertIs(self.desk.content_stack.currentWidget(), self.desk.completion_page)
        self.assertIs(self.desk.completion_page.window(), self.desk)

    def test_prepare_set_only_creates_draft_and_preserves_review(self):
        self.desk.show_completion()
        self.desk.completion_page.prepare_selected()
        self.assertEqual(self.desk.desired, {"A": True, "B": True})
        self.assertEqual(self.desk.client.mock_calls, [])
        dialog = self.desk.make_review_dialog()
        self.assertFalse(dialog.apply_button.isEnabled())
        self.assertEqual(dialog.listing.topLevelItemCount(), 2)
        dialog.close()

    def test_archived_and_dlc_restrictions_apply_to_single_and_bulk_actions(self):
        self.desk.completions[self.key] = parse_completion(page(archived=True), 10, ACCOUNT)
        self.desk.render()
        self.assertFalse(self.desk.cards["A"].switch.isEnabled())
        self.desk.toggle_achievement("A", True)
        self.assertEqual(self.desk.desired, {})
        self.desk.selected = {"A", "B"}
        self.desk.queue_state(True)
        self.assertEqual(self.desk.desired, {"B": True})
        self.assertEqual(self.desk.client.mock_calls, [])

    def test_trophy_not_inferred_from_draft_or_full_loaded_progress(self):
        self.desk.completions[self.key] = parse_completion(page(include_user=False), 10, ACCOUNT)
        self.desk.rows = [replace(row, unlocked=True) for row in self.desk.rows]
        self.desk.render()
        item = self.desk.completion_page.tree.topLevelItem(0)
        self.assertEqual(item.text(1), "2 / 2")
        self.assertEqual(item.text(2), "Unconfirmed")
        self.assertIn("completion unconfirmed", self.desk.completion_page.summary.text())
        self.assertNotIn("0 completed", self.desk.sets_button.text())

    def test_reported_completion_stays_visible_after_relocking_current_achievements(self):
        self.desk.completions[self.key] = parse_completion(page(completed=True), 10, ACCOUNT)
        self.desk.render()
        item = self.desk.completion_page.tree.topLevelItem(0)
        self.assertEqual(item.text(1), "0 / 2")
        self.assertEqual(item.text(2), "Completed")
        self.assertEqual(self.desk.client.mock_calls, [])

    def test_only_verified_evidence_matches_compatibility_filter(self):
        self.desk.save_compatibility(10, observe_read({}, 2))
        self.assertEqual([g.app_id for g in self.desk.match_games("", "Achievements readable")], [10])
        self.assertEqual([g.app_id for g in self.desk.match_games("", "Changes confirmed")], [])
        self.assertEqual([g.app_id for g in self.desk.match_games("", "Not checked")], [11])

    def test_stale_account_and_out_of_order_completion_callbacks_are_ignored(self):
        self.desk.demo = False
        self.desk.completions.clear()
        callbacks = []
        with patch.object(self.desk.completion_service, "load", side_effect=lambda a, s, done: callbacks.append(done)):
            self.desk.load_completion()
            self.desk.load_completion(force=True)
            callbacks[1](parse_completion(page(completed=True), 10, ACCOUNT))
            callbacks[0](parse_completion(page(completed=False), 10, ACCOUNT))
            self.assertTrue(self.desk.current_completion()["groups"][0]["completed"])
            self.desk.load_completion(force=True)
            self.desk.completion_generation += 1
            self.desk.completions.clear()
            callbacks[2](parse_completion(page(completed=True), 10, ACCOUNT))
            self.assertEqual(self.desk.current_completion(), {})

    def test_restriction_arriving_after_draft_removes_unlock(self):
        self.desk.demo = False
        self.desk.completions.clear()
        self.desk.toggle_achievement("A", True)
        callbacks = []
        with patch.object(self.desk.completion_service, "load", side_effect=lambda a, s, done: callbacks.append(done)):
            self.desk.load_completion()
            callbacks[0](parse_completion(page(archived=True), 10, ACCOUNT))
        self.assertEqual(self.desk.desired, {})
        self.assertEqual(self.desk.client.mock_calls, [])

    def test_review_checks_restrictions_again_at_submission(self):
        self.desk.toggle_achievement("A", True)
        dialog = self.desk.make_review_dialog()
        self.desk.completions[self.key] = parse_completion(page(archived=True), 10, ACCOUNT)
        dialog.consent.setChecked(True)
        with patch("modern_ui.QMessageBox.warning") as warning:
            dialog.apply_button.click()
        warning.assert_called_once()
        self.assertEqual(self.desk.client.mock_calls, [])
        dialog.close()


if __name__ == "__main__":
    unittest.main()
