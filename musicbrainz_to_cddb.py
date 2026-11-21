import argparse
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


def find_medium(metadata, disc_id, track_count, release_id=None, medium_number=None):
    if release_id:
        releases = [
            release for release in metadata.get("releases", [])
            if release["id"] == release_id
        ]
        if len(releases) != 1:
            raise ValueError("De opgegeven release ontbreekt in de MusicBrainz-data.")
        release = releases[0]
        media = release.get("media", [])
        if medium_number is not None:
            candidates = [medium for medium in media if medium["position"] == medium_number]
            if not candidates:
                raise ValueError(f"Discnummer {medium_number} bestaat niet in deze release.")
        else:
            matching_discs = [
                medium for medium in media
                if any(disc["id"] == disc_id for disc in medium.get("discs", []))
            ]
            if matching_discs:
                candidates = matching_discs
            else:
                candidates = [
                    medium for medium in media
                    if len(medium.get("tracks", [])) == track_count
                ]

        if len(candidates) > 1:
            raise ValueError(
                "Meerdere discs komen overeen; geef het discnummer als tweede parameter mee."
            )
        if not candidates:
            raise ValueError(
                "Geen disc gevonden die overeenkomt met de cd; controleer de release en het discnummer."
            )
        return release, candidates[0]

    for release in metadata.get("releases", []):
        for medium in release.get("media", []):
            if any(disc["id"] == disc_id for disc in medium.get("discs", [])):
                return release, medium
    return None, None


def build_cddb(metadata, disc_info, release_id=None, medium_number=None):
    release, medium = find_medium(
        metadata,
        disc_info["disc_id"],
        len(disc_info["tracks"]),
        release_id,
        medium_number,
    )
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
    return "\n".join(lines) + "\n", release["id"], medium["position"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata_file")
    parser.add_argument("disc_info_file")
    parser.add_argument("output_dir")
    parser.add_argument("release_id_file")
    parser.add_argument("disc_number_file")
    parser.add_argument("--release-id")
    parser.add_argument("--medium", type=int)
    args = parser.parse_args()
    if args.medium is not None and not args.release_id:
        parser.error("--medium vereist --release-id")
    try:
        metadata = json.loads(Path(args.metadata_file).read_text(encoding="utf-8"))
        disc_info = json.loads(Path(args.disc_info_file).read_text(encoding="utf-8"))
        cddb, release_id, disc_number = build_cddb(
            metadata, disc_info, args.release_id, args.medium
        )
    except (OSError, ValueError, KeyError) as error:
        print(f"Omzetten naar CDDB mislukt: {error}", file=sys.stderr)
        return 1

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / disc_info["cddb_id"]).write_text(cddb, encoding="utf-8")
    Path(args.release_id_file).write_text(release_id + "\n", encoding="utf-8")
    Path(args.disc_number_file).write_text(f"{disc_number}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
