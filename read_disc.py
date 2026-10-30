import json
import sys

import discid


def main():
    try:
        disc = discid.read("/dev/sr0")
    except discid.DiscError as error:
        print(f"Kan de cd niet uitlezen: {error}", file=sys.stderr)
        return 1

    data = {
        "disc_id": disc.id,
        "cddb_id": disc.freedb_id,
        "toc": disc.toc_string,
        "first_track": disc.first_track_num,
        "last_track": disc.last_track_num,
        "lead_out_frame": disc.sectors,
        "tracks": [
            {
                "number": track.number,
                "length_frames": track.sectors,
                "offset_frames": track.offset,
            }
            for track in disc.tracks
        ],
    }
    print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
