import argparse
import sys
from pathlib import Path

from mutagen import MutagenError
from mutagen.id3 import ID3, ID3NoHeaderError, TXXX


def set_user_tag(path, description, value):
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
        v2_version = 3
    else:
        v2_version = 3 if tags.version[1] == 3 else 4

    tags.delall(f"TXXX:{description}")
    tags.add(TXXX(encoding=3, desc=description, text=[value]))
    tags.save(path, v2_version=v2_version)


def main():
    parser = argparse.ArgumentParser(
        description="Stel een ID3v2-gebruikerstag in op MP3-bestanden."
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="map met MP3-bestanden (doorzoekt ook submappen)",
    )
    parser.add_argument(
        "description",
        help="omschrijving van de TXXX-tag, bijvoorbeeld oorsprong",
    )
    parser.add_argument("value", help="waarde voor de tag")
    args = parser.parse_args()

    if not args.description.strip():
        parser.error("de tagomschrijving mag niet leeg zijn")
    if not args.directory.is_dir():
        parser.error(f"geen map: {args.directory}")

    files = sorted(
        path for path in args.directory.rglob("*")
        if path.is_file() and path.suffix.lower() == ".mp3"
    )
    if not files:
        print(
            f"Geen MP3-bestanden gevonden in {args.directory}.",
            file=sys.stderr,
        )
        return 1

    failures = 0
    for path in files:
        try:
            set_user_tag(path, args.description, args.value)
        except (OSError, MutagenError) as error:
            print(f"Mislukt voor {path}: {error}", file=sys.stderr)
            failures += 1
        else:
            print(f"Tag {args.description} ingesteld op {args.value} voor {path}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
