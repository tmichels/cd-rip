import json
import sys
import time
import urllib.error
import urllib.request

API_URL = "https://musicbrainz.org/ws/2/discid/{disc_id}?fmt=json&inc=recordings+artist-credits"
USER_AGENT = "cd-rip/1.0 (https://github.com/tmichels/cd-rip)"
TIMEOUT_SECONDS = 30
RETRY_INTERVAL_SECONDS = 5
RETRY_PERIOD_SECONDS = 60

EXIT_CONTINUE = 0  # 200 of 404: ga door met rippen
EXIT_ABORT = 1


def fetch(disc_id):
    request = urllib.request.Request(
        API_URL.format(disc_id=disc_id), headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)


def main():
    if len(sys.argv) != 2:
        print("Gebruik: fetch_metadata.py <disc_id>", file=sys.stderr)
        return EXIT_ABORT

    deadline = time.monotonic() + RETRY_PERIOD_SECONDS
    while True:
        try:
            data = fetch(sys.argv[1])
        except urllib.error.HTTPError as error:
            if error.code == 404:
                print("Geen release gevonden voor deze disc_id; doorgaan zonder metadata.", file=sys.stderr)
                return EXIT_CONTINUE
            if error.code == 503 and time.monotonic() + RETRY_INTERVAL_SECONDS <= deadline:
                print(
                    f"MusicBrainz is bezet (503); nieuwe poging over {RETRY_INTERVAL_SECONDS} seconden.",
                    file=sys.stderr,
                    flush=True,
                )
                time.sleep(RETRY_INTERVAL_SECONDS)
                continue
            print(f"MusicBrainz gaf HTTP-status {error.code}; afbreken.", file=sys.stderr)
            return EXIT_ABORT
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            print(f"Metadata ophalen mislukt: {error}", file=sys.stderr)
            return EXIT_ABORT

        print(json.dumps(data, indent=2, ensure_ascii=False))
        return EXIT_CONTINUE


if __name__ == "__main__":
    sys.exit(main())
