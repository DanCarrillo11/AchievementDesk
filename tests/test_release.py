import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import publish_release as release


class ReleaseGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def files(self, private=False):
        for name in release.asset_names():
            path = self.folder / name
            if name.endswith(".zip"):
                with zipfile.ZipFile(path, "w") as z:
                    z.writestr("achievement-desk/README.md", "Synthetic packaging fixture")
                    if private:
                        z.writestr("achievement-desk/snapshots/private.json", "Do not publish")
            else:
                path.write_bytes(b"Synthetic setup fixture, never executed")
        (self.folder / "SHA256SUMS.txt").write_text("".join(release.digest(self.folder / n) + "  " + n + "\n" for n in release.asset_names()), encoding="ascii")

    def test_version_and_request_metadata_agree(self):
        value, notes = release.request()
        self.assertEqual(value["tag"], "v" + release.VERSION)
        self.assertTrue(notes.is_file())

    def test_mismatched_request_is_rejected(self):
        (self.folder / ".github").mkdir()
        (self.folder / ".github/release.json").write_text(json.dumps(dict(tag="v99.0.0", prerelease=False)), encoding="utf-8")
        with patch.object(release, "ROOT", self.folder), self.assertRaises(ValueError):
            release.request()

    def test_changed_asset_is_rejected(self):
        self.files()
        (self.folder / release.asset_names()[2]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "changed"):
            release.verify_assets(self.folder)

    def test_private_snapshot_is_rejected_even_with_matching_checksum(self):
        self.files(private=True)
        with self.assertRaisesRegex(ValueError, "Private"):
            release.verify_assets(self.folder)

    def test_extra_or_duplicate_checksum_is_rejected(self):
        self.files()
        path = self.folder / "SHA256SUMS.txt"
        path.write_text(path.read_text() + path.read_text().splitlines()[0] + "\n", encoding="ascii")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            release.verify_assets(self.folder)

    def environment(self):
        return patch.dict(os.environ, GITHUB_REPOSITORY="DanCarrillo11/AchievementDesk", GITHUB_REF="refs/heads/main", GITHUB_SHA="b" * 40)

    def test_published_release_is_never_reuploaded(self):
        value, notes = release.request()
        existing = dict(target_commitish="b" * 40, draft=False, html_url="https://github.com/DanCarrillo11/AchievementDesk/releases/tag/" + value["tag"])
        with self.environment(), patch.object(release, "verify_assets", return_value={}), patch.object(release.subprocess, "check_output", return_value="b" * 40), patch.object(release, "api", side_effect=[None, existing]), patch.object(release, "gh") as gh, patch("builtins.print"):
            release.publish(self.folder)
            gh.assert_not_called()

    def test_existing_release_for_other_source_is_not_changed(self):
        with self.environment(), patch.object(release, "verify_assets", return_value={}), patch.object(release.subprocess, "check_output", return_value="b" * 40), patch.object(release, "api", side_effect=[None, dict(target_commitish="a" * 40, draft=False)]), patch.object(release, "gh") as gh:
            with self.assertRaisesRegex(RuntimeError, "another commit"):
                release.publish(self.folder)
            gh.assert_not_called()

    def test_incomplete_uploaded_assets_stay_draft(self):
        with self.environment(), patch.object(release, "verify_assets", return_value={}), patch.object(release.subprocess, "check_output", return_value="b" * 40), patch.object(release, "api", side_effect=[None, None, dict(id=123, draft=True), dict(assets=[])]), patch.object(release, "gh") as gh:
            with self.assertRaisesRegex(RuntimeError, "intended release assets"):
                release.publish(self.folder)
            self.assertFalse(any(call.args[:2] == ("release", "edit") for call in gh.call_args_list))


if __name__ == "__main__":
    unittest.main()
