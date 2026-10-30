#!/usr/bin/env bash
set -euo pipefail

library_dir="/home/thomas/muziek"

toc_output=$(.venv/bin/python read_disc.py)
printf '%s\n' "$toc_output"

matching_discs=$(find "$library_dir" -type f -name 'disc-info.json' \
    -exec jq -r --argjson disc "$toc_output" '
        select(.disc_id == $disc.disc_id and .toc == $disc.toc)
        | "Overeenkomstige cd-layout: \(input_filename)"
    ' {} +)

if [[ -n "$matching_discs" ]]; then
    printf '%s\n' "$matching_discs"
else
    printf '%s\n' 'Geen rip van deze cd in de library gevonden. Het rippen wordt gestart.'
    abcde -N -x -o mp3
fi
