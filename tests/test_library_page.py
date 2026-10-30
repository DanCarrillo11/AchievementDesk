import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from library import Game, discover_owned
from library_view import LibraryPage, letter_bucket
from media import Media, parse_game_icon
from native import SteamLibrarySession
from workspace import atomic_json


class SteamListIconTests(unittest.TestCase):
    def test_parser_selects_small_steam_icon_and_ignores_cover(self):
        for host in ("shared.fastly.steamstatic.com", "shared.akamai.steamstatic.com"):
            url = f"https://{host}/community_assets/images/apps/620/" + "a" * 40 + ".jpg"
            html = '<img src="https://cdn.akamai.steamstatic.com/steam/apps/620/library_600x900.jpg">' + f'<div class="apphub_AppIcon"><img src="{url}"><div class="overlay"></div></div>'
            self.assertEqual(parse_game_icon(html, 620), url)

    def test_wrong_app_and_untrusted_host_are_rejected(self):
        for url in ("https://evil.invalid/community_assets/images/apps/620/" + "a" * 40 + ".jpg",
                    "https://shared.fastly.steamstatic.com/community_assets/images/apps/440/" + "a" * 40 + ".jpg"):
            self.assertEqual(parse_game_icon(f'<div class="apphub_AppIcon"><img src="{url}"></div>', 620), "")

    def test_native_icon_uses_existing_metadata_interface_and_validates_hash(self):
        session = SteamLibrarySession.__new__(SteamLibrarySession)
        with patch.object(session, "app_data", return_value="A" * 40) as read:
            self.assertEqual(session.app_icon(620), "a" * 40)
            read.assert_called_once_with(620, b"icon")
        with patch.object(session, "app_data", return_value="../../private"):
            self.assertEqual(session.app_icon(620), "")

    def test_owned_library_carries_icon_hash_without_game_stats(self):
        from test_discovery import AccessSession
        session = AccessSession()
        session.app_icon = lambda app_id: "a" * 40
        games = discover_owned(session, [20])
        self.assertEqual(games[0].icon_hash, "a" * 40)
        self.assertFalse(games[0].installed)

    def test_known_icon_uses_local_steam_cache_without_http(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            media = Media(root / "cache", lambda callback: callback())
            media.steam_cache, media.checked_steam_cache = root / "steam", True
            path = media.steam_cache / "620" / ("a" * 40 + ".jpg")
            path.parent.mkdir(parents=True)
            path.write_bytes(b"example-local-image")
            done = Mock()
            with patch("media.fetch") as fetch:
                media.game_icon(620, done, "a" * 40)
                fetch.assert_not_called()
            done.assert_called_once_with(path)
            media.close()

    def test_known_hash_uses_icon_cdn_not_store_portrait_or_app_page(self):
        with tempfile.TemporaryDirectory() as folder:
            media = Media(folder, lambda callback: callback())
            media.checked_steam_cache = True
            done = Mock()
            with patch.object(media, "image") as image, patch("media.fetch") as fetch:
                media.game_icon(620, done, "b" * 40)
                image.assert_called_once_with("https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/620/" + "b" * 40 + ".jpg", done)
                fetch.assert_not_called()
            media.close()


class EmbeddedLibraryTests(unittest.TestCase):
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
        self.window.library = [Game(i, f"Game {i:03}") for i in range(235)]
        self.window.render()
        self.window.browse_library()
        self.page = self.window.library_page
        self.app.processEvents()

    def tearDown(self):
        self.window.desired.clear()
        self.window.busy = False
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_library_is_embedded_and_reused_in_main_window(self):
        self.assertIsInstance(self.page, LibraryPage)
        self.assertFalse(self.page.isWindow())
        self.assertIs(self.page.window(), self.window)
        self.assertIs(self.window.content_stack.currentWidget(), self.page)
        self.window.show_achievements()
        self.window.browse_library()
        self.assertIs(self.window.library_page, self.page)

    def test_100_game_pages_have_no_duplicates_or_missing_games(self):
        self.assertEqual(self.page.games.count(), 100)
        ids = list(self.page.visible_ids)
        self.page.turn(1)
        self.assertEqual(self.page.games.count(), 100)
        ids += self.page.visible_ids
        self.page.turn(1)
        self.assertEqual(self.page.games.count(), 35)
        ids += self.page.visible_ids
        self.assertEqual(ids, list(range(235)))
        self.assertFalse(self.page.next.isEnabled())
        self.page.turn(-99)
        self.assertEqual(self.page.page, 0)

    def test_letter_and_search_filter_entire_library_and_reset_page(self):
        self.window.library += [Game(1000, "Portal 2"), Game(1001, "Portal"), Game(1002, "Half-Life")]
        self.page.turn(2)
        self.page.set_letter("P")
        self.assertEqual(self.page.page, 0)
        self.assertEqual(set(self.page.visible_ids), {1000, 1001})
        self.page.search.setText("Portal 2")
        self.assertEqual(self.page.visible_ids, [1000])
        self.page.set_letter("H")
        self.assertEqual(self.page.games.count(), 0)
        self.assertFalse(self.page.empty.isHidden())
        self.page.search.clear()
        self.assertEqual(self.page.visible_ids, [1002])

    def test_accents_punctuation_numbers_and_other_scripts(self):
        for name, expected in (("Éternité", "E"), ('  "Portal"', "P"), ("123 Game", "#"), ("遊戲", "#"), ("™ Celeste", "C")):
            self.assertEqual(letter_bucket(name), expected)

    def test_library_navigation_preserves_drafts_and_does_not_reconnect_current_game(self):
        self.window.toggle_achievement("EXPLORER", True)
        self.page.games.setCurrentRow(0)
        self.page.open_selected()
        self.assertIs(self.window.content_stack.currentWidget(), self.window.editor_page)
        self.assertEqual(self.window.desired, {"EXPLORER": True})
        self.assertEqual(self.window.client.mock_calls, [])
        self.window.browse_library()
        self.assertEqual(self.window.desired, {"EXPLORER": True})

    def test_declining_discard_keeps_library_and_drafts(self):
        from PySide6.QtWidgets import QMessageBox
        self.window.toggle_achievement("EXPLORER", True)
        self.page.games.setCurrentRow(1)
        with patch("modern_ui.QMessageBox.question", return_value=QMessageBox.StandardButton.No), patch("modern_ui.GameClient") as connect:
            self.page.open_selected()
            connect.assert_not_called()
        self.assertIs(self.window.content_stack.currentWidget(), self.page)
        self.assertEqual(self.window.desired, {"EXPLORER": True})

    def test_favorite_shortcut_targets_selected_library_game(self):
        self.page.games.setCurrentRow(1)
        self.window.favorite_current_view()
        self.assertIn(1, self.window.profile()["favorites"])
        self.assertNotIn(0, self.window.profile()["favorites"])
        self.assertEqual(self.window.client.mock_calls, [])

    def test_shared_favorites_filter_composes_with_letter(self):
        self.window.workspace.favorite("DEMO", 1)
        self.page.filter.setCurrentText("Favorites")
        self.page.set_letter("G")
        self.assertEqual(self.page.visible_ids, [1])
        self.assertEqual(self.window.library_filter, "Favorites")
        self.assertEqual(self.window.games.count(), 1)

    def test_minimum_window_keeps_all_letter_controls_and_open_action_inside(self):
        self.window.resize(1020, 760)
        self.window.show()
        self.window.browse_library()
        self.app.processEvents()
        for control in [*self.page.letter_buttons.values(), self.page.open, self.page.next]:
            point = control.mapTo(self.page, control.rect().bottomRight())
            self.assertTrue(self.page.rect().contains(point), control.text())
        self.assertGreater(self.page.games.verticalScrollBar().maximum(), 0)
        self.page.games.scrollToItem(self.page.games.item(99))
        self.app.processEvents()
        self.assertTrue(self.page.games.viewport().rect().intersects(self.page.games.visualItemRect(self.page.games.item(99))))

    def test_scrolling_requests_icons_for_newly_visible_games(self):
        self.window.show()
        self.app.processEvents()
        self.page.games.scrollToItem(self.page.games.item(99))
        self.app.processEvents()
        with patch.object(self.window, "request_game_icon") as request:
            self.page.request_visible_icons()
        ids = {call.args[0] for call in request.call_args_list}
        self.assertIn(99, ids)
        self.assertNotIn(0, ids)
