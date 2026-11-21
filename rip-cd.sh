#!/usr/bin/env bash
set -euo pipefail

# Alle uitvoer en foutmeldingen verschijnen nu op de terminal én in het logbestand. Oude logfiles worden verwijderd
MAX_LOG_FILES=20

main() {
    if ! validate_arguments "$@"; then
        return 1
    fi
    local musicbrainz_release_id="${1:-}"
    start_logging
    date '+%d-%m-%Y %H:%M:%S'
    source ./abcde.conf
    read_disc_info_json

    local matching_disc_info_files
    matching_disc_info_files=$(find_matching_disc_info_files "$disc_id" "$disc_toc")
    if [[ -n "$matching_disc_info_files" ]]; then
        show_existing_disc_metadata "$matching_disc_info_files"
    else
        printf '%s\n' 'Geen bestaande rip van deze cd in de library gevonden. De metadata wordt opgehaald.'
        prepare_rip_metadata "$disc_id" "$disc_info_json" "${musicbrainz_release_id,,}" "${2:-}"
        rip_disc "$disc_info_json"
    fi

    date '+%d-%m-%Y %H:%M:%S'
}

validate_arguments() {
    if [[ $# -gt 2 ]]; then
        print_usage
        return 1
    fi
    if [[ $# -ge 1 ]] &&
        [[ ! "$1" =~ ^[[:xdigit:]]{8}-[[:xdigit:]]{4}-[[:xdigit:]]{4}-[[:xdigit:]]{4}-[[:xdigit:]]{12}$ ]]; then
        print_usage
        return 1
    fi
    if [[ $# -eq 2 ]] && [[ ! "$2" =~ ^[1-9][0-9]*$ ]]; then
        print_usage
        return 1
    fi
    return 0
}

print_usage() {
    printf 'Gebruik: %s [MusicBrainz-release-ID [discnummer]]\n' "$0" >&2
}

start_logging() {
    mkdir -p log
    find log -maxdepth 1 -type f -name '*.log' -print0 |
        LC_ALL=C sort -zr | tail -z -n +"$MAX_LOG_FILES" | xargs -0 -r rm --
    exec > >(tee -a "log/$(date '+%Y%m%d_%H:%M:%S').log") 2>&1
}

read_disc_info_json() {
    disc_info_json=$(.venv/bin/python read_disc.py)
    disc_id=$(jq -r '.disc_id' <<< "$disc_info_json")
    disc_toc=$(jq -r '.toc' <<< "$disc_info_json")
    printf 'Disc ID:\t%s\nDisc TOC:\t%s\n\n' "$disc_id" "$disc_toc"
}

find_matching_disc_info_files() {
    find "$OUTPUTDIR" -type f -name 'disc-info.json' \
        -exec jq -c --arg disc_id "$1" --arg toc "$2" '
            select(.disc_id == $disc_id and .toc == $toc)
            | (input_filename)
        ' {} +
}

show_existing_disc_metadata() {
    printf 'Deze CD heeft dezelfde disc_id en disc_toc als deze cd uit de bibliotheek: %s. De cd wordt niet geript.\n' "$1"
    printf '\nDe metadata volgens abcde:\n'
    METADATA_ONLY=y abcde -c ./abcde.conf -a cddb,clean
}

prepare_rip_metadata() {
    local disc_id=$1
    local disc_info_json=$2
    local musicbrainz_release_id="${3:-}"
    local medium_number="${4:-}"
    local disc_metadata_dir="metadata/$disc_id"
    local release_id_args=()
    local medium_args=()
    if [[ -n "$musicbrainz_release_id" ]]; then
        release_id_args=(--release-id "$musicbrainz_release_id")
    fi
    if [[ -n "$medium_number" ]]; then
        medium_args=(--medium "$medium_number")
    fi

    mkdir -p "$disc_metadata_dir"
    rm -rf "$disc_metadata_dir/cddb"
    printf '%s\n' "$disc_info_json" > "$disc_metadata_dir/disc-info.json"
    .venv/bin/python fetch_metadata.py "$disc_id" "${release_id_args[@]}" > "$disc_metadata_dir/musicbrainz.json" ||
        abort_and_eject 'Metadata ophalen mislukt; de rip wordt afgebroken.'

    if [[ ! -s "$disc_metadata_dir/musicbrainz.json" ]]; then
        abort_and_eject 'Geen metadata beschikbaar; de rip wordt afgebroken.'
    fi

    .venv/bin/python musicbrainz_to_cddb.py \
        "$disc_metadata_dir/musicbrainz.json" "$disc_metadata_dir/disc-info.json" \
        "$disc_metadata_dir/cddb" "$disc_metadata_dir/release-id" \
        "${release_id_args[@]}" "${medium_args[@]}" ||
        abort_and_eject 'Metadata omzetten mislukt; de rip wordt afgebroken.'
    export RIP_CDDB_DIR="$PWD/$disc_metadata_dir/cddb"
    download_release_front_cover "$disc_metadata_dir"
    printf 'Metadata opgeslagen in %s. Het rippen wordt gestart.\n' "$disc_metadata_dir"
}

abort_and_eject() {
    printf '%s\n' "$1" >&2
    eject "$CDROM" || true
    exit 1
}

download_release_front_cover() {
    local disc_metadata_dir=$1

    rm -f "$disc_metadata_dir/cover.jpg"
    if ! curl -sSfL -A 'cd-rip/1.0 (https://github.com/tmichels/cd-rip)' \
        -o "$disc_metadata_dir/cover.jpg" \
        "https://coverartarchive.org/release/$(<"$disc_metadata_dir/release-id")/front"; then
        rm -f "$disc_metadata_dir/cover.jpg"
        printf '%s\n' 'Geen albumhoes gevonden bij de Cover Art Archive.'
        return
    fi

    export RIP_COVER_FILE="$PWD/$disc_metadata_dir/cover.jpg"
}

rip_disc() {
    TOC_OUTPUT="$1" abcde -c ./abcde.conf
}

main "$@"
