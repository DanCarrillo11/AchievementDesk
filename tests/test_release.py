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
        (self.folder / "release-request.json").write_text(json.dumps(dict(version="99.0.0", prerelease=False)), encoding="utf-8")
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

    def hashes(self):
        return {name: "a" * 64 for name in release.asset_names()}

    def test_published_release_is_never_reuploaded(self):
        value, notes = release.request()
        existing = dict(target_commitish="b" * 40, draft=False, html_url="https://github.com/DanCarrillo11/AchievementDesk/releases/tag/" + value["tag"])
        with self.environment(), patch.object(release, "verify_assets", return_value=self.hashes()), patch.object(release.subprocess, "check_output", return_value="b" * 40), patch.object(release, "api", side_effect=[None, existing]), patch.object(release, "gh") as gh, patch("builtins.print"):
            release.publish(self.folder)
            gh.assert_not_called()

    def test_existing_release_for_other_source_is_not_changed(self):
        with self.environment(), patch.object(release, "verify_assets", return_value=self.hashes()), patch.object(release.subprocess, "check_output", return_value="b" * 40), patch.object(release, "api", side_effect=[None, dict(target_commitish="a" * 40, draft=False)]), patch.object(release, "gh") as gh:
            with self.assertRaisesRegex(RuntimeError, "another commit"):
                release.publish(self.folder)
            gh.assert_not_called()

    def test_incomplete_uploaded_assets_stay_draft(self):
        with self.environment(), patch.object(release, "verify_assets", return_value=self.hashes()), patch.object(release.subprocess, "check_output", return_value="b" * 40), patch.object(release, "api", side_effect=[None, None, [], dict(id=123, draft=True, target_commitish="b" * 40), dict(assets=[])]), patch.object(release, "gh") as gh:
            with self.assertRaisesRegex(RuntimeError, "intended release assets"):
                release.publish(self.folder)
            self.assertFalse(any(call.args[:2] == ("release", "edit") for call in gh.call_args_list))

    def test_stable_publication_sets_latest_and_verifies_both_downloads(self):
        self.files()
        names = [release.asset_names()[0], release.asset_names()[2]]
        assets = [dict(name=n, size=(self.folder / n).stat().st_size, state="uploaded",
                       digest="sha256:" + release.digest(self.folder / n)) for n in names]
        responses = [None, None, [], dict(id=123, draft=True, target_commitish="b" * 40), dict(assets=assets),
                     dict(draft=False, prerelease=False, html_url="https://github.com/DanCarrillo11/AchievementDesk/releases/tag/v" + release.VERSION)]
        with self.environment(), patch.object(release.subprocess, "check_output", return_value="b" * 40), patch.object(release, "api", side_effect=responses), patch.object(release, "gh") as gh, patch("builtins.print"):
            release.publish(self.folder)
        edit = next(c.args for c in gh.call_args_list if c.args[:2] == ("release", "edit"))
        self.assertIn("--prerelease=false", edit)
        self.assertIn("--latest", edit)
        body = (self.folder / "published-notes.md").read_text(encoding="utf-8")
        for n in names:
            self.assertIn(release.digest(self.folder / n), body)

    def test_server_checksum_mismatch_keeps_release_unpublished(self):
        self.files()
        assets = [dict(name=n, size=(self.folder / n).stat().st_size, state="uploaded", digest="sha256:" + "0" * 64)
                  for n in (release.asset_names()[0], release.asset_names()[2])]
        with self.environment(), patch.object(release.subprocess, "check_output", return_value="b" * 40), patch.object(release, "api", side_effect=[None, None, [], dict(id=123, draft=True, target_commitish="b" * 40), dict(assets=assets)]), patch.object(release, "gh") as gh:
            with self.assertRaisesRegex(RuntimeError, "checksum"):
                release.publish(self.folder)
        self.assertFalse(any(c.args[:2] == ("release", "edit") for c in gh.call_args_list))

    def test_pending_draft_is_reused_without_a_tag_lookup_after_creation(self):
        draft = dict(id=123, tag_name="v" + release.VERSION, draft=True, target_commitish="b" * 40, assets=[])
        with self.environment(), patch.object(release, "verify_assets", return_value=self.hashes()), patch.object(release.subprocess, "check_output", return_value="b" * 40), patch.object(release, "api", side_effect=[None, None, [draft], dict(assets=[])]) as api, patch.object(release, "gh"):
            with self.assertRaisesRegex(RuntimeError, "intended release assets"):
                release.publish(self.folder)
        self.assertFalse(any(c.kwargs.get("payload") for c in api.call_args_list))

    def test_explicit_recovery_discards_only_an_empty_untagged_draft(self):
        value, notes = release.request()
        value["discard_empty_draft_from"] = "a" * 40
        old = dict(id=100, tag_name=value["tag"], draft=True, target_commitish="a" * 40, assets=[])
        created = dict(id=123, draft=True, target_commitish="b" * 40)
        with self.environment(), patch.object(release, "request", return_value=(value, notes)), patch.object(release, "verify_assets", return_value=self.hashes()), patch.object(release.subprocess, "check_output", return_value="b" * 40), patch.object(release, "api", side_effect=[None, None, [old], created, dict(assets=[])]) as api, patch.object(release, "gh") as gh:
            with self.assertRaisesRegex(RuntimeError, "intended release assets"):
                release.publish(self.folder)
        gh.assert_any_call("api", "--method", "DELETE", "repos/DanCarrillo11/AchievementDesk/releases/100")
        payload = next(c.kwargs["payload"] for c in api.call_args_list if "payload" in c.kwargs)
        self.assertTrue(payload["draft"])
        self.assertEqual(payload["target_commitish"], "b" * 40)

    def test_a_draft_with_downloads_cannot_be_discarded(self):
        value, notes = release.request()
        value["discard_empty_draft_from"] = "a" * 40
        old = dict(id=100, tag_name=value["tag"], draft=True, target_commitish="a" * 40, assets=[dict(name="keep.exe")])
        with self.environment(), patch.object(release, "request", return_value=(value, notes)), patch.object(release, "verify_assets", return_value=self.hashes()), patch.object(release.subprocess, "check_output", return_value="b" * 40), patch.object(release, "api", side_effect=[None, None, [old]]), patch.object(release, "gh") as gh:
            with self.assertRaisesRegex(RuntimeError, "another commit"):
                release.publish(self.folder)
        gh.assert_not_called()

    def test_installer_smoke_cannot_run_on_the_users_desktop(self):
        from tools.verify_packaged import check_installation
        with patch.dict(os.environ, GITHUB_ACTIONS="false"), self.assertRaisesRegex(RuntimeError, "disposable Windows"):
            check_installation(self.folder / "not-an-installer.exe")


if __name__ == "__main__":
    unittest.main()
