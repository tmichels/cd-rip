import json
import sys
from pathlib import Path

FRAMES_PER_SECOND = 75


def credit_name(artist_credit):
    return "".join(
        part["name"] + part.get("joinphrase", "") for part in artist_credit
    ).strip()


def clean(text):
    # abcde splitst DTITLE en track-titels op " / "
    return " ".join(text.replace(" / ", " - ").split())


def find_medium(metadata, disc_id):
    for release in metadata.get("releases", []):
        for medium in release.get("media", []):
            if any(disc["id"] == disc_id for disc in medium.get("discs", [])):
                return release, medium
    return None, None


def build_cddb(metadata, disc_info):
    release, medium = find_medium(metadata, disc_info["disc_id"])
    if medium is None:
        raise ValueError("Geen release met deze disc_id in de MusicBrainz-data.")

    tracks = sorted(medium["tracks"], key=lambda track: track["position"])
    if len(tracks) != len(disc_info["tracks"]):
        raise ValueError(
            f"Aantal tracks komt niet overeen: MusicBrainz {len(tracks)}, cd {len(disc_info['tracks'])}."
        )

    album_artist = credit_name(release["artist-credit"])
    various = album_artist.lower().startswith("various")
    lines = ["# xmcd", "#", "# Track frame offsets:"]
    lines += [f"#\t{track['offset_frames']}" for track in disc_info["tracks"]]
    lines += [
        "#",
        f"# Disc length: {disc_info['lead_out_frame'] // FRAMES_PER_SECOND} seconds",
        "#",
        "# Revision: 0",
        "# Submitted via: cd-rip (MusicBrainz)",
        "#",
        f"DISCID={disc_info['cddb_id']}",
        f"DTITLE={clean(album_artist)} / {clean(release['title'])}",
        f"DYEAR={release.get('date', '')[:4]}",
        "DGENRE=",
    ]
    for index, track in enumerate(tracks):
        title = clean(track["title"])
        if various:
            title = f"{clean(credit_name(track['artist-credit']))} / {title}"
        lines.append(f"TTITLE{index}={title}")
    lines += ["EXTD=", *[f"EXTT{index}=" for index in range(len(tracks))], "PLAYORDER="]
    return "\n".join(lines) + "\n", release["id"]


def main():
    if len(sys.argv) != 5:
        print("Gebruik: musicbrainz_to_cddb.py <metadata.json> <disc-info.json> <uitvoermap> <release-id-bestand>", file=sys.stderr)
        return 1

    metadata_file, disc_info_file, output_dir, release_id_file = sys.argv[1:]
    try:
        metadata = json.loads(Path(metadata_file).read_text(encoding="utf-8"))
        disc_info = json.loads(Path(disc_info_file).read_text(encoding="utf-8"))
        cddb, release_id = build_cddb(metadata, disc_info)
    except (OSError, ValueError, KeyError) as error:
        print(f"Omzetten naar CDDB mislukt: {error}", file=sys.stderr)
        return 1

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / disc_info["cddb_id"]).write_text(cddb, encoding="utf-8")
    Path(release_id_file).write_text(release_id + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
