"""Distinguish a pending read from an empty result and navigate filtered pages."""
from dataclasses import asdict
import threading
import time
import unittest
from unittest.mock import Mock, patch

from demo import DemoSession
from experience import page_numbers
from library import Game


class PageNumberTests(unittest.TestCase):
    def test_small_sets_show_all_pages_and_large_sets_keep_the_edges(self):
        self.assertEqual(page_numbers(0, 0), [])
        self.assertEqual(page_numbers(0, 3), [0, 1, 2])
        self.assertEqual(page_numbers(0, 1001), [0, 1, 2, 3, 4, None, 1000])
        self.assertEqual(page_numbers(1000, 1001), [0, None, 996, 997, 998, 999, 1000])
        middle = page_numbers(500, 1001)
        self.assertEqual(middle[0], 0)
        self.assertEqual(middle[-1], 1000)
        self.assertIn(500, middle)
        self.assertLessEqual(len(middle), 11)


class LoadingAndPagesTests(unittest.TestCase):
    def setUp(self):
        from test_modern_ui import APP
        from modern_ui import Desk
        self.app = APP
        self.window = Desk(demo=True, hidden=True)
        self.window.account_id = self.window.library_account_id = "DEMO"
        self.window.game = Game(10, "Previously open game")
        self.window.client = Mock()
        self.window.rows = DemoSession().read()
        self.window.render()
        self.gates = []

    def tearDown(self):
        for gate in self.gates:
            gate.set()
        self.finish()
        self.window.busy = False
        self.window.desired.clear()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def finish(self):
        deadline = time.monotonic() + 4
        while self.window.busy and time.monotonic() < deadline:
            self.window.poll()
            self.app.processEvents()
            time.sleep(.005)
        self.assertFalse(self.window.busy)

    def start_read(self, rows=None, error=None):
        entered, gate = threading.Event(), threading.Event()
        self.gates.append(gate)
        client = Mock()
        def receive():
            entered.set()
            if not gate.wait(4):
                raise TimeoutError("Synthetic read gate timed out")
            if error:
                raise error
            return dict(account_id="DEMO", achievements=[asdict(r) for r in (rows if rows is not None else DemoSession().read())])
        client.receive.side_effect = receive
        client.cancel.side_effect = gate.set
        with patch("modern_ui.GameClient", return_value=client):
            self.window.connect(Game(20, "Selected game"))
            self.assertTrue(entered.wait(2))
        return gate, client

    def test_delayed_read_shows_loading_until_rows_arrive(self):
        gate, _ = self.start_read()
        self.assertEqual(self.window.empty_title.text(), "Loading achievements…")
        self.assertFalse(self.window.empty_loading.isHidden())
        self.assertEqual(self.window.result_count.text(), "…")
        self.assertEqual(self.window.game_title.text(), "Selected game")
        self.assertNotIn("No achievements", self.window.progress_text.text())
        gate.set(); self.finish()
        self.assertTrue(self.window.empty_loading.isHidden())
        self.assertTrue(self.window.empty_panel.isHidden())
        self.assertEqual(self.window.game.app_id, 20)

    def test_only_a_successful_empty_read_reports_no_achievements(self):
        gate, _ = self.start_read(rows=[])
        self.assertEqual(self.window.empty_title.text(), "Loading achievements…")
        gate.set(); self.finish()
        self.assertEqual(self.window.empty_title.text(), "No achievements returned")
        self.assertTrue(self.window.empty_loading.isHidden())
        self.assertEqual(self.window.result_count.text(), "0")

    def test_failed_read_has_retry_instead_of_a_false_empty_result(self):
        gate, _ = self.start_read(error=RuntimeError("Steam is offline"))
        gate.set(); self.finish()
        self.assertEqual(self.window.empty_title.text(), "Achievements could not be loaded")
        self.assertFalse(self.window.retry_button.isHidden())
        self.assertTrue(self.window.empty_loading.isHidden())
        self.assertFalse(self.window.favorite_button.isEnabled())

    def test_cancelled_read_has_its_own_state_and_closes_the_new_client(self):
        _, client = self.start_read()
        self.window.cancel_read()
        self.finish()
        self.assertEqual(self.window.empty_title.text(), "Achievement loading cancelled")
        self.assertTrue(self.window.empty_loading.isHidden())
        client.close.assert_called()

    def test_refresh_can_show_progress_without_discarding_loaded_rows(self):
        self.window.set_rows(dict(account_id="DEMO", achievements=[asdict(r) for r in self.window.rows]))
        entered, gate = threading.Event(), threading.Event()
        self.gates.append(gate)
        def read(_):
            entered.set(); gate.wait(4)
            return dict(account_id="DEMO", achievements=[asdict(r) for r in DemoSession().read()])
        self.window.client.exchange.side_effect = read
        self.window.refresh()
        self.assertTrue(entered.wait(2))
        self.assertEqual(len(self.window.rows), 6)
        self.assertTrue(self.window.empty_panel.isHidden())
        self.assertFalse(self.window.cards["EXPLORER"].switch.isEnabled())
        gate.set(); self.finish()

    def test_unknown_apply_result_does_not_claim_the_game_has_no_achievements(self):
        self.window.applied(dict(result=dict(status="unconfirmed", confirmed=[], rejected=[], unconfirmed=["EXPLORER"],
                                            snapshot="synthetic.json", message="Synthetic unknown result")))
        self.assertEqual(self.window.empty_title.text(), "Reload achievements to continue")

    def library(self, count=235):
        self.window.library = [Game(1000+i, f"Portal {i:04}") for i in range(count)] + [Game(999, "Half-Life")]
        self.window.browse_library()
        page = self.window.library_page
        page.set_letter("P")
        self.app.processEvents()
        return page

    def test_numbered_buttons_jump_within_the_letter_filtered_library(self):
        page = self.library()
        self.assertEqual([b.text() for b in page.page_buttons.values()], ["1", "2", "3"])
        self.window.toggle_achievement("EXPLORER", True)
        page.page_buttons[2].click()
        self.assertEqual(page.page, 2)
        self.assertEqual(page.games.count(), 35)
        self.assertEqual(page.visible_ids[0], 1200)
        self.assertTrue(page.page_buttons[2].isChecked())
        self.assertFalse(page.next.isEnabled())
        self.assertEqual(self.window.desired, {"EXPLORER": True})
        self.assertEqual(self.window.client.mock_calls, [])

    def test_search_recalculates_pages_and_empty_results_hide_the_page_bar(self):
        page = self.library()
        page.go_to_page(2)
        page.search.setText("Portal 000")
        self.assertEqual(page.page, 0)
        self.assertEqual(list(page.page_buttons), [0])
        page.search.setText("no matching game")
        self.assertEqual(page.page_buttons, {})
        self.assertTrue(page.page_navigation.isHidden())

    def test_many_page_links_stay_bounded_and_fit_the_minimum_window(self):
        page = self.library(2105)
        page.go_to_page(10)
        self.window.resize(1020, 760)
        self.window.show()
        self.app.processEvents()
        self.assertLessEqual(len(page.page_buttons), 9)
        self.assertIn(0, page.page_buttons)
        self.assertIn(21, page.page_buttons)
        self.assertIn(10, page.page_buttons)
        self.assertEqual(self.window.width(), 1020)
        for control in [page.previous, page.next, *page.page_buttons.values()]:
            self.assertTrue(page.rect().contains(control.mapTo(page, control.rect().bottomRight())))


if __name__ == "__main__":
    unittest.main()
