#!/usr/bin/env bash
# Vervangt glyrc voor abcde: kopieert de al opgehaalde hoes ($RIP_COVER_FILE) naar het bestand
# dat abcde opgeeft via --write. Zonder hoes geeft het exit 1, dan gaat abcde door zonder hoes.

target=""
while [[ $# -gt 0 ]]; do
    if [[ "$1" == "--write" ]]; then
        target="${2:-}"
        break
    fi
    shift
done

[[ -n "$target" && -s "${RIP_COVER_FILE:-}" ]] || exit 1
cp "$RIP_COVER_FILE" "$target"
