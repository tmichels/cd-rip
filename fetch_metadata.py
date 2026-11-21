import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from uuid import UUID

MUSICBRAINZ_DISC_URL = "https://musicbrainz.org/ws/2/discid/{disc_id}?fmt=json&inc=recordings+artist-credits"
MUSICBRAINZ_RELEASE_URL = "https://musicbrainz.org/ws/2/release/{release_id}?fmt=json&inc=recordings+artist-credits+discids"
USER_AGENT = "cd-rip/1.0 (https://github.com/tmichels/cd-rip)"
TIMEOUT_SECONDS = 30
RETRY_INTERVAL_SECONDS = 5
RETRY_PERIOD_SECONDS = 60

EXIT_CONTINUE = 0
EXIT_ABORT = 1


def main(argv=None):
    args = parse_arguments(argv)
    try:
        musicbrainz_response = fetch_musicbrainz_metadata_with_retries(
            args.disc_id, args.release_id
        )
    except urllib.error.HTTPError as error:
        return report_http_error(error)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"Metadata ophalen mislukt: {error}", file=sys.stderr)
        return EXIT_ABORT

    return output_release_metadata(musicbrainz_response, args.release_id)


def parse_arguments(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("disc_id")
    parser.add_argument("--release-id", type=UUID)
    return parser.parse_args(argv)


def fetch_musicbrainz_metadata_with_retries(disc_id, release_id=None):
    deadline = time.monotonic() + RETRY_PERIOD_SECONDS
    while True:
        try:
            return fetch_musicbrainz_metadata(disc_id, release_id)
        except urllib.error.HTTPError as error:
            if error.code != 503 or time.monotonic() + RETRY_INTERVAL_SECONDS > deadline:
                raise
            print(
                f"MusicBrainz is bezet (503); nieuwe poging over {RETRY_INTERVAL_SECONDS} seconden.",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(RETRY_INTERVAL_SECONDS)


def fetch_musicbrainz_metadata(disc_id, release_id=None):
    musicbrainz_url = (
        MUSICBRAINZ_RELEASE_URL.format(release_id=release_id)
        if release_id else MUSICBRAINZ_DISC_URL.format(disc_id=disc_id)
    )
    request = urllib.request.Request(
        musicbrainz_url, headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)


def report_http_error(error):
    if error.code == 404:
        print("Geen release gevonden in MusicBrainz; afbreken.", file=sys.stderr)
    else:
        print(f"MusicBrainz gaf HTTP-status {error.code}; afbreken.", file=sys.stderr)
    return EXIT_ABORT


def output_release_metadata(musicbrainz_response, release_id):
    if release_id:
        musicbrainz_response = {"releases": [musicbrainz_response]}
    if not musicbrainz_response.get("releases"):
        print("Geen releases gevonden in MusicBrainz; afbreken.", file=sys.stderr)
        return EXIT_ABORT
    print(json.dumps(musicbrainz_response, indent=2, ensure_ascii=False))
    return EXIT_CONTINUE


if __name__ == "__main__":
    sys.exit(main())
