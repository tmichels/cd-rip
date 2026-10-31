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
    printf '%s\n' 'Geen bestaande rip van deze cd in de library gevonden. Het rippen wordt gestart.'
    TOC_OUTPUT="$toc_output" abcde -c ./abcde.conf
fi
date '+%d-%m-%Y %H:%M:%S'
