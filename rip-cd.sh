#!/usr/bin/env bash
set -euo pipefail

# Alle uitvoer en foutmeldingen verschijnen nu op de terminal én in het logbestand. Oude logfiles worden verwijderd
MAX_LOG_FILES=20
mkdir -p log
find log -maxdepth 1 -type f -name '*.log' -print0 |
    LC_ALL=C sort -zr | tail -z -n +"$MAX_LOG_FILES" | xargs -0 -r rm --
exec > >(tee -a "log/$(date '+%Y%m%d_%H:%M:%S').log") 2>&1

date '+%d-%m-%Y %H:%M:%S'
source ./abcde.conf

toc_output=$(.venv/bin/python read_disc.py)
disc_id=$(jq -r '.disc_id' <<< "$toc_output")
disc_toc=$(jq -r '.toc' <<< "$toc_output")
printf 'Disc ID:\t%s\nDisc TOC:\t%s\n\n' "$disc_id" "$disc_toc"

matching_discs=$(find "$OUTPUTDIR" -type f -name 'disc-info.json' \
    -exec jq -c --arg disc_id "$disc_id" --arg toc "$disc_toc" '
        select(.disc_id == $disc_id and .toc == $toc)
        | (input_filename)
    ' {} +)

if [[ -n "$matching_discs" ]]; then
    printf 'Deze CD heeft dezelfde disc_id en disc_toc als deze cd uit de bibliotheek: %s. De cd wordt niet geript.\n' "$matching_discs"
    printf '\nDe metadata volgens abcde:\n'
    METADATA_ONLY=y abcde -c ./abcde.conf -a cddb,clean
else
    printf '%s\n' 'Geen bestaande rip van deze cd in de library gevonden. De metadata wordt opgehaald.'

    # Metadata wordt eerst opgehaald en bewaard; zonder goede metadata wordt niet geript en de cd uitgeworpen
    abort_and_eject() {
        printf '%s\n' "$1" >&2
        eject "$CDROM" || true
        exit 1
    }
    metadata_dir="metadata/$disc_id"
    mkdir -p "$metadata_dir"
    rm -rf "$metadata_dir/cddb"
    printf '%s\n' "$toc_output" > "$metadata_dir/disc-info.json"
    .venv/bin/python fetch_metadata.py "$disc_id" > "$metadata_dir/musicbrainz.json" ||
        abort_and_eject 'Metadata ophalen mislukt; de rip wordt afgebroken.'

    if [[ -s "$metadata_dir/musicbrainz.json" ]]; then
        .venv/bin/python musicbrainz_to_cddb.py \
            "$metadata_dir/musicbrainz.json" "$metadata_dir/disc-info.json" "$metadata_dir/cddb" "$metadata_dir/release-id" ||
            abort_and_eject 'Metadata omzetten mislukt; de rip wordt afgebroken.'
        export RIP_CDDB_DIR="$PWD/$metadata_dir/cddb"

        # De hoes is optioneel: een ontbrekende hoes breekt de rip niet af
        rm -f "$metadata_dir/cover.jpg"
        if ! curl -sSfL -A 'cd-rip/1.0 (https://github.com/tmichels/cd-rip)' \
            -o "$metadata_dir/cover.jpg" \
            "https://coverartarchive.org/release/$(<"$metadata_dir/release-id")/front"; then
            rm -f "$metadata_dir/cover.jpg"
            printf '%s\n' 'Geen albumhoes gevonden bij de Cover Art Archive.'
        else
            export RIP_COVER_FILE="$PWD/$metadata_dir/cover.jpg"
        fi
        printf 'Metadata opgeslagen in %s. Het rippen wordt gestart.\n' "$metadata_dir"
    else
        # Onbekende disc (404): abcde mag niet nogmaals bij MusicBrainz zoeken
        export RIP_CDDB_METHOD=cdtext
        printf '%s\n' 'Geen metadata beschikbaar. Het rippen wordt gestart zonder metadata.'
    fi
    TOC_OUTPUT="$toc_output" abcde -c ./abcde.conf
fi
date '+%d-%m-%Y %H:%M:%S'
