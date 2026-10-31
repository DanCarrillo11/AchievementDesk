"""Artwork failures must remain optional, retryable and correctly associated."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from media import Media, parse_icons
from workspace import atomic_json


class ArtworkParsing(unittest.TestCase):
    def page(self, rows, app_id=10):
        schema = dict(appid=app_id, groups=[dict(achievements=rows)])
        queries = [dict(queryKey=["achievements", app_id, "schema_v2"], state=dict(status="success", data=schema))]
        return '<script id="valve-ssr-data">' + json.dumps(dict(queries=queries)) + '</script>'

    def test_field_order_and_missing_variants_do_not_mix_achievements(self):
        rows = [dict(icon_unachieved="a_bw.png", api_name="A"),
                dict(icon_achieved="b.jpg", api_name="B", icon_unachieved="b_bw.jpg")]
        self.assertEqual(parse_icons(self.page(rows), 10),
                         {"A": {"locked": "a_bw.png"}, "B": {"unlocked": "b.jpg", "locked": "b_bw.jpg"}})

    def test_wrong_game_schema_is_not_used(self):
        self.assertEqual(parse_icons(self.page([dict(api_name="A", icon_achieved="a.jpg")], 20), 10), {})

    def test_unescaped_legacy_objects_and_unsafe_names(self):
        rows = '{"icon_achieved":"a.jpg","api_name":"A"}, {"api_name":"B","icon_achieved":"../bad.jpg"}'
        self.assertEqual(parse_icons(rows), {"A": {"unlocked": "a.jpg"}})


class ArtworkRecovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.media = Media(self.temp.name, lambda callback: callback())
        self.addCleanup(lambda: self.media.pool.shutdown(wait=True, cancel_futures=True))
        self.png = (Path(__file__).resolve().parents[1] / "assets/app.png").read_bytes()
        self.url = "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/10/a.jpg"

    def completed(self, request):
        values, event = [], threading.Event()
        request(lambda value: (values.append(value), event.set()))
        self.assertTrue(event.wait(3), "Artwork callback was stranded")
        return values[0]

    def test_failure_completes_callbacks_and_can_retry_after_cooldown(self):
        with patch("media.fetch", side_effect=OSError("Offline")) as fetch:
            self.assertIsNone(self.completed(lambda done: self.media.image(self.url, done)))
            self.assertIsNone(self.completed(lambda done: self.media.image(self.url, done)))
            self.assertEqual(fetch.call_count, 1)
        self.assertEqual(self.media.pending, {})
        self.media.failed[self.url] = time.monotonic() - 1
        with patch("media.fetch", return_value=self.png):
            self.assertTrue(self.completed(lambda done: self.media.image(self.url, done)).is_file())

    def test_corrupt_cache_is_replaced_with_a_valid_image(self):
        path = self.media.image_path(self.url)
        path.parent.mkdir(parents=True)
        path.write_bytes(b"\xff\xd8not a decodable image")
        with patch("media.fetch", return_value=self.png) as fetch:
            result = self.completed(lambda done: self.media.image(self.url, done))
            fetch.assert_called_once()
        self.assertEqual(result.read_bytes(), self.png)

    def test_html_and_corrupt_images_are_never_cached(self):
        with patch("media.fetch", return_value=b"\xff\xd8broken"):
            self.assertIsNone(self.completed(lambda done: self.media.image(self.url, done)))
        self.assertFalse(self.media.image_path(self.url).exists())

    def test_refresh_failure_keeps_valid_cached_metadata(self):
        path = Path(self.temp.name) / "schema-10.json"
        atomic_json(path, dict(format=2, icons={"A": {"unlocked": "a.jpg"}}, percentages={"A": 12}, warnings=[]))
        with patch("media.fetch", side_effect=OSError("Offline")):
            result = self.completed(lambda done: self.media.metadata(10, done, force=True))
        self.assertEqual(result["icons"], {"A": {"unlocked": "a.jpg"}})
        self.assertEqual(result["percentages"], {"A": 12})
        self.assertEqual(len(result["warnings"]), 2)

    def test_legacy_empty_cache_does_not_hide_artwork_for_a_day(self):
        atomic_json(Path(self.temp.name) / "schema-10.json", dict(icons={}, percentages={}))
        html = ArtworkParsing().page([dict(api_name="A", icon_achieved="a.jpg")]).encode()
        with patch("media.fetch", side_effect=[html, b'{"achievementpercentages":{"achievements":[]}}']) as fetch:
            result = self.completed(lambda done: self.media.metadata(10, done))
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(result["icons"], {"A": {"unlocked": "a.jpg"}})

    def test_invalid_metadata_types_are_rebuilt_instead_of_reaching_the_ui(self):
        atomic_json(Path(self.temp.name) / "schema-10.json", dict(format=2, icons={"A": "invalid"}, percentages={"A": "bad"}))
        with patch("media.fetch", side_effect=OSError("Offline")):
            result = self.completed(lambda done: self.media.metadata(10, done))
        self.assertEqual(result["icons"], {})
        self.assertEqual(result["percentages"], {})


if __name__ == "__main__":
    unittest.main()
