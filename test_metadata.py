import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
from unittest.mock import patch

import fetch_metadata
from musicbrainz_to_cddb import build_cddb

RELEASE_ID = "e925ed61-5bbf-41d8-a352-e31f2ef53f8e"


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.disc = {
            "disc_id": "test-disc",
            "cddb_id": "12345678",
            "lead_out_frame": 15000,
            "tracks": [
                {"number": 1, "offset_frames": 150},
                {"number": 2, "offset_frames": 7500},
            ],
        }
        self.release = {
            "id": RELEASE_ID,
            "title": "Album",
            "date": "2026-01-01",
            "artist-credit": [{"name": "Artist"}],
            "media": [{
                "position": 1,
                "discs": [{"id": "test-disc"}],
                "tracks": [
                    {"position": 1, "title": "First"},
                    {"position": 2, "title": "Second"},
                ],
            }],
        }

    def build(self, manual=False, medium=None):
        return build_cddb(
            {"releases": [self.release]}, self.disc,
            RELEASE_ID if manual else None, medium,
        )

    def test_automatic_lookup_unchanged(self):
        cddb, release_id = self.build()
        self.assertEqual(release_id, RELEASE_ID)
        self.assertIn("DTITLE=Artist / Album\n", cddb)
        self.assertIn("TTITLE1=Second\n", cddb)
        self.assertIn("DISCID=12345678\n", cddb)

    def test_unknown_disc_requires_explicit_release(self):
        self.release["media"][0]["discs"] = []
        with self.assertRaises(ValueError):
            self.build()
        self.assertIn("TTITLE0=First\n", self.build(manual=True)[0])

    def test_track_count_mismatch_rejected_even_with_explicit_medium(self):
        self.release["media"][0]["tracks"].pop()
        with self.assertRaises(ValueError):
            self.build(manual=True, medium=1)

    def test_multiple_discs_require_unambiguous_selection(self):
        first = self.release["media"][0]
        first["discs"] = []
        second = copy.deepcopy(first)
        second["position"] = 2
        second["tracks"][0]["title"] = "Disc two"
        self.release["media"].append(second)
        with self.assertRaises(ValueError):
            self.build(manual=True)
        self.assertIn("TTITLE0=Disc two\n", self.build(manual=True, medium=2)[0])
        with self.assertRaises(ValueError):
            self.build(manual=True, medium=3)
        first["discs"] = [{"id": "test-disc"}]
        self.assertIn("TTITLE0=First\n", self.build(manual=True)[0])

    def test_unique_track_count_selects_medium(self):
        self.release["media"][0]["discs"] = []
        second = copy.deepcopy(self.release["media"][0])
        second["position"] = 2
        second["tracks"].pop()
        self.release["media"].append(second)
        self.assertIn("TTITLE1=Second\n", self.build(manual=True)[0])

    def test_fetch_404_and_empty_releases_abort_without_output(self):
        for response in ("404", {"releases": []}):
            with self.subTest(response=response):
                output = io.StringIO()
                with patch("fetch_metadata.fetch_musicbrainz_metadata") as fetch, contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                    if response == "404":
                        fetch.side_effect = urllib.error.HTTPError("url", 404, "missing", {}, None)
                    else:
                        fetch.return_value = response
                    self.assertEqual(fetch_metadata.main(["test-disc"]), 1)
                self.assertEqual(output.getvalue(), "")

    def test_release_fetch_wrapped_for_converter(self):
        output = io.StringIO()
        with patch("fetch_metadata.fetch_musicbrainz_metadata", return_value=self.release) as fetch, contextlib.redirect_stdout(output):
            self.assertEqual(fetch_metadata.main(["test-disc", "--release-id", RELEASE_ID]), 0)
        self.assertEqual(str(fetch.call_args.args[1]), RELEASE_ID)
        metadata = json.loads(output.getvalue())
        self.assertEqual(build_cddb(metadata, self.disc, RELEASE_ID)[1], RELEASE_ID)

    def test_fetch_uses_release_endpoint(self):
        with patch("fetch_metadata.urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = io.StringIO("{}")
            fetch_metadata.fetch_musicbrainz_metadata("test-disc", RELEASE_ID)
        url = urlopen.call_args.args[0].full_url
        self.assertIn(f"/release/{RELEASE_ID}?", url)
        self.assertIn("discids", url)

    def test_503_retries(self):
        error = urllib.error.HTTPError("url", 503, "busy", {}, None)
        with patch("fetch_metadata.fetch_musicbrainz_metadata", side_effect=[error, {"releases": [self.release]}]), patch("fetch_metadata.time.sleep") as sleep, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(fetch_metadata.main(["test-disc"]), 0)
        sleep.assert_called_once_with(5)

    def test_503_retry_deadline_and_error_output(self):
        error = urllib.error.HTTPError("url", 503, "busy", {}, None)
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("fetch_metadata.fetch_musicbrainz_metadata", side_effect=[error, error]) as fetch:
            with patch("fetch_metadata.time.monotonic", side_effect=[100, 155, 156]):
                with patch("fetch_metadata.time.sleep") as sleep:
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        self.assertEqual(fetch_metadata.main(["test-disc"]), 1)
        self.assertEqual(fetch.call_count, 2)
        sleep.assert_called_once_with(5)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(
            stderr.getvalue(),
            "MusicBrainz is bezet (503); nieuwe poging over 5 seconden.\n"
            "MusicBrainz gaf HTTP-status 503; afbreken.\n",
        )

    def test_fetch_errors_abort_without_retry(self):
        errors = [
            (urllib.error.HTTPError("url", 404, "missing", {}, None),
             "Geen release gevonden in MusicBrainz; afbreken.\n"),
            (urllib.error.HTTPError("url", 400, "bad request", {}, None),
             "MusicBrainz gaf HTTP-status 400; afbreken.\n"),
            (urllib.error.URLError("offline"), "Metadata ophalen mislukt: <urlopen error offline>\n"),
            (TimeoutError("timeout"), "Metadata ophalen mislukt: timeout\n"),
            (json.JSONDecodeError("invalid", "", 0),
             "Metadata ophalen mislukt: invalid: line 1 column 1 (char 0)\n"),
        ]
        for error, message in errors:
            with self.subTest(error=error):
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch("fetch_metadata.fetch_musicbrainz_metadata", side_effect=error) as fetch:
                    with patch("fetch_metadata.time.sleep") as sleep:
                        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                            self.assertEqual(fetch_metadata.main(["test-disc"]), 1)
                fetch.assert_called_once_with("test-disc", None)
                sleep.assert_not_called()
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(stderr.getvalue(), message)

    def test_automatic_fetch_preserves_json_output(self):
        metadata = {"releases": [{"title": "Björk"}]}
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("fetch_metadata.fetch_musicbrainz_metadata", return_value=metadata):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(fetch_metadata.main(["test-disc"]), 0)
        self.assertEqual(stdout.getvalue(), json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
        self.assertEqual(stderr.getvalue(), "")

    def test_invalid_release_id_is_rejected_before_fetching(self):
        stderr = io.StringIO()
        with patch("fetch_metadata.fetch_musicbrainz_metadata") as fetch, contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as error:
                fetch_metadata.main(["test-disc", "--release-id", "invalid"])
        self.assertEqual(error.exception.code, 2)
        self.assertIn("invalid UUID value", stderr.getvalue())
        fetch.assert_not_called()

    @contextlib.contextmanager
    def shell_project(self, scenario):
        repository = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".venv/bin").mkdir(parents=True)
            (root / "bin").mkdir()
            shutil.copy2(repository / "rip-cd.sh", root)
            shutil.copy2(repository / "abcde.conf", root)
            release = copy.deepcopy(self.release)
            if scenario != "automatic":
                release["media"][0]["discs"] = []
            if scenario == "mismatch":
                release["media"][0]["tracks"].pop()
            if scenario in ("ambiguous", "selected"):
                medium = copy.deepcopy(release["media"][0])
                medium["position"] = 2
                release["media"].append(medium)
            disc = {**self.disc, "toc": "1 2 15000 150 7500"}
            (root / "disc.json").write_text(json.dumps(disc))
            (root / "release.json").write_text(json.dumps({"releases": [release]}))
            commands = {
                ".venv/bin/python": f"""#!{sys.executable}
import pathlib
import subprocess
import sys
import time
command = sys.argv[1]
if command == "read_disc.py":
    print(pathlib.Path("disc.json").read_text())
elif command == "fetch_metadata.py":
    if pathlib.Path("hold_fetch").exists() and "--release-id" not in sys.argv:
        pathlib.Path("fetch_started").touch()
        while not pathlib.Path("release_fetch").exists():
            time.sleep(0.01)
    if {scenario!r} == "unknown" and "--release-id" not in sys.argv:
        sys.exit(1)
    if {scenario!r} == "empty":
        sys.exit(0)
    if "--release-id" in sys.argv:
        assert sys.argv[sys.argv.index("--release-id") + 1] == {RELEASE_ID!r}
    print(pathlib.Path("release.json").read_text())
else:
    sys.exit(subprocess.call([
        sys.executable, {str(repository / "musicbrainz_to_cddb.py")!r}, *sys.argv[2:]
    ]))
""",
                "bin/abcde": """#!/usr/bin/env bash
set -eu
source ./abcde.conf
test -s "$RIP_CDDB_DIR/12345678"
jq -e --arg id e925ed61-5bbf-41d8-a352-e31f2ef53f8e '.id == $id' "$RIP_RELEASE_FILE" >/dev/null
test -n "$TOC_OUTPUT"
touch ripped
if [[ "$EJECTCD" == y ]]; then
    eject "$CDROM"
fi
""",
                "bin/eject": "#!/usr/bin/env bash\ntouch ejected\n",
                "bin/curl": "#!/usr/bin/env bash\nexit 22\n",
            }
            for name, content in commands.items():
                path = root / name
                path.write_text(content)
                path.chmod(0o755)
            (root / "muziek").mkdir()
            environment = {
                **os.environ,
                "HOME": str(root),
                "PATH": f"{root / 'bin'}:{os.environ['PATH']}",
            }
            yield root, environment

    def run_shell_scenario(self, scenario, arguments, status, ripped):
        with self.shell_project(scenario) as (root, environment):
            result = subprocess.run(
                ["bash", "rip-cd.sh", *arguments], cwd=root,
                env=environment, capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, status, result.stdout + result.stderr)
            self.assertEqual((root / "ripped").exists(), ripped, result.stdout)
            self.assertEqual((root / "ejected").exists(), ripped, result.stdout)
            if not ripped:
                self.assertIn("De cd blijft in het station.", result.stdout + result.stderr)

    def test_shell_pipeline(self):
        scenarios = [
            ("unknown", [], 1, False),
            ("empty", [], 1, False),
            ("automatic", [], 0, True),
            ("manual", [RELEASE_ID], 0, True),
            ("mismatch", [RELEASE_ID, "1"], 1, False),
            ("ambiguous", [RELEASE_ID], 1, False),
            ("selected", [RELEASE_ID, "2"], 0, True),
        ]
        for scenario, arguments, status, ripped in scenarios:
            with self.subTest(scenario=scenario):
                self.run_shell_scenario(scenario, arguments, status, ripped)

    def test_manual_rip_after_automatic_metadata_failure(self):
        with self.shell_project("unknown") as (root, environment):
            automatic = subprocess.run(
                ["bash", "rip-cd.sh"], cwd=root, env=environment,
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(automatic.returncode, 1, automatic.stdout + automatic.stderr)
            self.assertFalse((root / "ripped").exists())
            self.assertFalse((root / "ejected").exists())

            manual = subprocess.run(
                ["bash", "rip-cd.sh", RELEASE_ID], cwd=root, env=environment,
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(manual.returncode, 0, manual.stdout + manual.stderr)
            self.assertTrue((root / "ripped").exists())
            self.assertTrue((root / "ejected").exists())

    def test_concurrent_rips_are_rejected_until_the_first_finishes(self):
        with self.shell_project("unknown") as (root, environment):
            (root / "hold_fetch").touch()
            automatic = subprocess.Popen(
                ["bash", "rip-cd.sh"], cwd=root, env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                deadline = time.monotonic() + 10
                while not (root / "fetch_started").exists():
                    if automatic.poll() is not None or time.monotonic() >= deadline:
                        self.fail("De automatische rip begon niet met metadata ophalen.")
                    time.sleep(0.01)

                manual = subprocess.run(
                    ["bash", "rip-cd.sh", RELEASE_ID], cwd=root, env=environment,
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(manual.returncode, 1, manual.stdout + manual.stderr)
                self.assertIn("Er is al een rip actief", manual.stderr)
                self.assertFalse((root / "ripped").exists())
                self.assertFalse((root / "ejected").exists())
            finally:
                (root / "release_fetch").touch()
                try:
                    stdout, stderr = automatic.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    automatic.kill()
                    stdout, stderr = automatic.communicate(timeout=5)
                    self.fail(f"De automatische rip stopte niet:\n{stdout}{stderr}")

            self.assertEqual(automatic.returncode, 1, stdout + stderr)
            self.assertFalse((root / "ejected").exists())
            manual = subprocess.run(
                ["bash", "rip-cd.sh", RELEASE_ID], cwd=root, env=environment,
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(manual.returncode, 0, manual.stdout + manual.stderr)
            self.assertTrue((root / "ripped").exists())
            self.assertTrue((root / "ejected").exists())

    def test_shell_reports_lock_failure(self):
        with self.shell_project("automatic") as (root, environment):
            flock = root / "bin/flock"
            flock.write_text("#!/usr/bin/env bash\nprintf 'Lockfout\\n' >&2\nexit 74\n")
            flock.chmod(0o755)
            result = subprocess.run(
                ["bash", "rip-cd.sh"], cwd=root, env=environment,
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 74)
            self.assertIn("Lockfout", result.stderr)
            self.assertIn("Vergrendeling van de cd-rip mislukt (status 74).", result.stderr)
            self.assertFalse((root / "ripped").exists())
            self.assertFalse((root / "ejected").exists())

    def test_shell_rejects_invalid_arguments_before_reading_disc(self):
        script = Path(__file__).resolve().parent / "rip-cd.sh"
        for arguments in (["invalid"], [RELEASE_ID, "0"], [RELEASE_ID, "1", "extra"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    ["bash", str(script), *arguments], capture_output=True, text=True
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("Gebruik:", result.stderr)


if __name__ == "__main__":
    unittest.main()
