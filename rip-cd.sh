#!/usr/bin/env bash
set -euo pipefail

source ./abcde.conf

toc_output=$(.venv/bin/python read_disc.py)
printf '%s\n' "$toc_output"

matching_discs=$(find "$OUTPUTDIR" -type f -name 'disc-info.json' \
    -exec jq -r --argjson disc "$toc_output" '
        select(.disc_id == $disc.disc_id and .toc == $disc.toc)
        | "Deze CD heeft dezelfde properties als deze uit de library en wordt niet geript: \(input_filename)"
    ' {} +)

if [[ -n "$matching_discs" ]]; then
    printf '%s\n' "$matching_discs"
else
    printf '%s\n' 'Geen rip van deze cd in de library gevonden. Het rippen wordt gestart.'
    TOC_OUTPUT="$toc_output" abcde -c ./abcde.conf
fi
