import unittest
from unittest.mock import patch
from dataclasses import asdict
from demo import DemoSession
from ui import Desk
from library import Game
from domain import Achievement


class HiddenWindowTests(unittest.TestCase):
    """Construct and exercise widgets while the entire window stays withdrawn."""
    def setUp(self):
        self.root = Desk(demo=True, hidden=True)
        self.root.rows = DemoSession().read()
        self.root.account_id = "DEMO"
        self.root.render()
        self.root.update_idletasks()

    def tearDown(self):
        self.root.destroy()

    def test_window_stays_hidden(self):
        self.assertEqual(self.root.state(), "withdrawn")

    def test_search_and_pending_filter(self):
        self.root.search.set("beginning")
        self.assertEqual(self.root.table.get_children(), ("FIRST_STEP",))
        self.root.search.set("")
        self.root.desired["EXPLORER"] = True
        self.root.status_filter.set("Pending changes")
        self.root.render()
        self.assertEqual(self.root.table.get_children(), ("EXPLORER",))

    def test_queue_only_selected_and_keeps_hidden_changes(self):
        self.root.client = object()  # Queueing must not call the backend.
        self.root.table.selection_set("EXPLORER")
        self.root.queue_state(True)
        self.assertEqual(self.root.desired, {"EXPLORER": True})
        self.root.search.set("beginning")
        self.root.table.selection_set("FIRST_STEP")
        self.root.queue_state(False)
        self.assertEqual(self.root.desired, {"EXPLORER": True, "FIRST_STEP": False})
        self.root.clear_queue()
        self.assertEqual(self.root.desired, {})

    def test_hidden_details_concealed(self):
        values = self.root.table.item("SECRET", "values")
        self.assertEqual(values[0], "Hidden achievement")
        self.root.reveal.set(True)
        self.root.render()
        self.assertEqual(self.root.table.item("SECRET", "values")[0], "Behind the curtain")

    def test_apply_result_does_not_reconnect(self):
        with patch.object(self.root, "refresh") as refresh, patch("ui.messagebox.showinfo"):
            self.root.applied(dict(result=dict(status="confirmed", confirmed=["EXPLORER"], rejected=[],
                unconfirmed=[], snapshot="demo-reference.json", message="Demo confirmed",
                achievements=[asdict(a) for a in DemoSession().read()])))
            refresh.assert_not_called()
        self.assertEqual(len(self.root.rows), 6)

    def test_library_filters_and_id_search(self):
        self.root.library = [Game(10, "Local game", True), Game(20, "Remote game", False)]
        self.root.filter_games()
        self.assertEqual(len(self.root.visible_games), 2)
        self.root.library_filter.set("Not installed")
        self.root.filter_games()
        self.assertEqual(self.root.visible_games, [Game(20, "Remote game", False)])
        self.root.library_filter.set("All owned games")
        self.root.game_search.set("10")
        self.assertEqual(self.root.visible_games, [Game(10, "Local game", True)])

    def test_library_result_belongs_to_returned_account(self):
        self.root.library_loaded(dict(account_id="account-two", games=[dict(app_id=10, name="Owned", installed=False)]))
        self.assertEqual(self.root.library_account_id, "account-two")
        self.assertIn("1 not installed", self.root.status.cget("text"))

    def test_refresh_library_clears_previous_account_and_achievement_state(self):
        self.root.demo = False
        self.root.library_account_id = "previous-account"
        self.root.library = [Game(10, "Old game", False)]
        with patch.object(self.root, "task") as task:
            self.root.load_library()
            task.assert_called_once()
        self.assertEqual(self.root.rows, [])
        self.assertEqual(self.root.library, [])
        self.assertIsNone(self.root.account_id)
        self.assertIsNone(self.root.library_account_id)

    def test_noninstalled_game_routes_to_existing_achievement_functions(self):
        game = Game(123456, "An uninstalled game", False)
        self.root.library_account_id = "DEMO"
        with patch("ui.GameClient") as client, patch.object(self.root, "task", side_effect=lambda job, done: done(job())):
            client.return_value.receive.return_value = dict(account_id="DEMO", achievements=[asdict(a) for a in DemoSession().read()])
            self.root.connect(game)
            client.assert_called_once_with(123456, True)
        self.assertEqual(self.root.game.app_id, 123456)
        self.root.table.selection_set("EXPLORER")
        self.root.queue_state(True)
        self.assertEqual(self.root.desired, {"EXPLORER": True})

    def test_switches_reflect_saved_unlock_state(self):
        self.assertIn("selected", self.root.table.switches["FIRST_STEP"].state())
        self.assertNotIn("selected", self.root.table.switches["EXPLORER"].state())

    def test_switch_queues_unlock_without_sending_to_backend(self):
        from unittest.mock import Mock
        self.root.client = Mock()
        self.root.render()
        self.root.table.switches["EXPLORER"].invoke()
        self.assertEqual(self.root.desired, {"EXPLORER": True})
        self.assertTrue(self.root.table.records["EXPLORER"]["draft"])
        self.assertFalse(self.root.table.records["EXPLORER"]["actual"])
        self.assertEqual(self.root.client.mock_calls, [])

    def test_switch_back_discards_change(self):
        self.root.client = object()
        self.root.render()
        self.root.table.switches["EXPLORER"].invoke()
        self.root.table.switches["EXPLORER"].invoke()
        self.assertEqual(self.root.desired, {})
        self.assertFalse(self.root.table.records["EXPLORER"]["draft"])

    def test_switch_queues_relock(self):
        self.root.client = object()
        self.root.render()
        self.root.table.switches["FIRST_STEP"].invoke()
        self.assertEqual(self.root.desired, {"FIRST_STEP": False})
        self.assertTrue(self.root.table.records["FIRST_STEP"]["actual"])

    def test_busy_switches_do_not_accept_changes(self):
        self.root.client = object()
        self.root.busy = True
        self.root.render()
        self.root.table.switches["EXPLORER"].invoke()
        self.assertEqual(self.root.desired, {})
        self.assertIn("disabled", self.root.table.switches["EXPLORER"].state())

    def test_no_backend_switches_are_disabled(self):
        self.assertIn("disabled", self.root.table.switches["EXPLORER"].state())

    def test_discard_resets_switch_to_saved_state(self):
        self.root.client = object()
        self.root.toggle_achievement("EXPLORER", True)
        self.root.clear_queue()
        self.assertNotIn("selected", self.root.table.switches["EXPLORER"].state())

    def test_cards_show_description_without_selection(self):
        record = self.root.table.records["EXPLORER"]
        self.assertEqual(record["description"], "Discover all five hidden locations.")
        self.assertEqual(self.root.table.selection(), ())

    def test_hidden_descriptions_are_not_leaked(self):
        self.assertNotIn("Reveal spoilers", self.root.table.records["SECRET"]["description"])

    def test_pagination_keeps_all_records_and_pending_drafts(self):
        self.root.client = object()
        self.root.rows = [Achievement(f"A{i}", f"Achievement {i}", "Demo description", False) for i in range(60)]
        self.root.render()
        self.assertEqual(len(self.root.table.get_children()), 60)
        self.assertEqual(len(self.root.table.switches), 25)
        self.root.table.turn_page(1)
        self.assertIn("A25", self.root.table.switches)
        self.root.table.switches["A25"].invoke()
        self.assertEqual(self.root.table.page, 1)
        self.root.table.turn_page(-1)
        self.assertEqual(self.root.desired, {"A25": True})
        self.root.status_filter.set("Pending changes")
        self.root.render()
        self.assertEqual(self.root.table.get_children(), ("A25",))

    def test_search_matches_across_pages(self):
        self.root.rows = [Achievement(f"A{i}", f"Achievement {i}", "Demo description", False) for i in range(60)]
        self.root.render()
        self.root.search.set("A59")
        self.assertEqual(self.root.table.get_children(), ("A59",))
        self.assertEqual(self.root.table.page, 0)

    def test_review_enabled_only_when_changes_exist(self):
        self.assertIn("disabled", self.root.review_button.state())
        self.root.client = object()
        self.root.toggle_achievement("EXPLORER", True)
        self.assertNotIn("disabled", self.root.review_button.state())
        self.root.clear_queue()
        self.assertIn("disabled", self.root.review_button.state())


if __name__ == "__main__":
    unittest.main()
