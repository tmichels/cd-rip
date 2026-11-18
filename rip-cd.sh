#!/usr/bin/env bash
set -euo pipefail

# Alle uitvoer en foutmeldingen verschijnen nu op de terminal én in het logbestand. Oude logfiles worden verwijderd
MAX_LOG_FILES=20
start_logging() {
    mkdir -p log
    find log -maxdepth 1 -type f -name '*.log' -print0 |
        LC_ALL=C sort -zr | tail -z -n +"$MAX_LOG_FILES" | xargs -0 -r rm --
    exec > >(tee -a "log/$(date '+%Y%m%d_%H:%M:%S').log") 2>&1
}

read_disc_info() {
    toc_output=$(.venv/bin/python read_disc.py)
    disc_id=$(jq -r '.disc_id' <<< "$toc_output")
    disc_toc=$(jq -r '.toc' <<< "$toc_output")
    printf 'Disc ID:\t%s\nDisc TOC:\t%s\n\n' "$disc_id" "$disc_toc"
}

find_matching_discs() {
    find "$OUTPUTDIR" -type f -name 'disc-info.json' \
        -exec jq -c --arg disc_id "$1" --arg toc "$2" '
            select(.disc_id == $disc_id and .toc == $toc)
            | (input_filename)
        ' {} +
}

handle_existing_disc() {
    printf 'Deze CD heeft dezelfde disc_id en disc_toc als deze cd uit de bibliotheek: %s. De cd wordt niet geript.\n' "$1"
    printf '\nDe metadata volgens abcde:\n'
    METADATA_ONLY=y abcde -c ./abcde.conf -a cddb,clean
}

abort_and_eject() {
    printf '%s\n' "$1" >&2
    eject "$CDROM" || true
    exit 1
}

download_cover() {
    local metadata_dir=$1

    rm -f "$metadata_dir/cover.jpg"
    if ! curl -sSfL -A 'cd-rip/1.0 (https://github.com/tmichels/cd-rip)' \
        -o "$metadata_dir/cover.jpg" \
        "https://coverartarchive.org/release/$(<"$metadata_dir/release-id")/front"; then
        rm -f "$metadata_dir/cover.jpg"
        printf '%s\n' 'Geen albumhoes gevonden bij de Cover Art Archive.'
        return
    fi

    export RIP_COVER_FILE="$PWD/$metadata_dir/cover.jpg"
}

prepare_metadata() {
    local disc_id=$1
    local toc_output=$2
    local metadata_dir="metadata/$disc_id"

    mkdir -p "$metadata_dir"
    rm -rf "$metadata_dir/cddb"
    printf '%s\n' "$toc_output" > "$metadata_dir/disc-info.json"
    .venv/bin/python fetch_metadata.py "$disc_id" > "$metadata_dir/musicbrainz.json" ||
        abort_and_eject 'Metadata ophalen mislukt; de rip wordt afgebroken.'

    if [[ ! -s "$metadata_dir/musicbrainz.json" ]]; then
        export RIP_CDDB_METHOD=cdtext
        printf '%s\n' 'Geen metadata beschikbaar. Het rippen wordt gestart zonder metadata.'
        return
    fi

    .venv/bin/python musicbrainz_to_cddb.py \
        "$metadata_dir/musicbrainz.json" "$metadata_dir/disc-info.json" \
        "$metadata_dir/cddb" "$metadata_dir/release-id" ||
        abort_and_eject 'Metadata omzetten mislukt; de rip wordt afgebroken.'
    export RIP_CDDB_DIR="$PWD/$metadata_dir/cddb"
    download_cover "$metadata_dir"
    printf 'Metadata opgeslagen in %s. Het rippen wordt gestart.\n' "$metadata_dir"
}

rip_disc() {
    TOC_OUTPUT="$1" abcde -c ./abcde.conf
}

main() {
    start_logging
    date '+%d-%m-%Y %H:%M:%S'
    source ./abcde.conf
    read_disc_info

    local matching_discs
    matching_discs=$(find_matching_discs "$disc_id" "$disc_toc")
    if [[ -n "$matching_discs" ]]; then
        handle_existing_disc "$matching_discs"
    else
        printf '%s\n' 'Geen bestaande rip van deze cd in de library gevonden. De metadata wordt opgehaald.'
        prepare_metadata "$disc_id" "$toc_output"
        rip_disc "$toc_output"
    fi

    date '+%d-%m-%Y %H:%M:%S'
}

main "$@"
