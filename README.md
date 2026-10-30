# cd-rip

Ript audio-cd's naar losse mp3-bestanden en bewaart de cd-layout naast de
muziek. Een cd wordt overgeslagen als dezelfde layout al in de muziekbibliotheek
is geregistreerd.

## Installatie

Het project gebruikt:

- Linux
- Bash
- Python 3
- `libdiscid`
- `abcde`
- `jq`
- `LAME`
- `abcde`

Op Debian/Ubuntu kun je de benodigdheden als volgt installeren:

```bash
sudo apt install python3-venv libdiscid0 abcde lame jq
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Het cd-station is `/dev/sr0`. Indien dit afwijkt: 
- pas read_disc.py aan
- pas abcde.conf aan (`CDROM=/dev/sr0`)

## Gebruik

Voer het script uit vanuit de projectmap: de paden naar de configuratie,
Python-omgeving en het Python-script zijn relatief.

```bash
mkdir -p "$HOME/muziek"
bash rip-cd.sh
```

## Werking

1. Het script leest de cd-layout als vingerafdruk en zoekt of die al voorkomt in de bibliotheek.
2. Is de cd al geregistreerd, dan wordt het rippen overgeslagen.
3. Anders ript `abcde` de cd naar mp3's met metadata, volgens `abcde.conf`.
4. Na controle op fouten en voltooide tracks wordt de vingerafdruk als
   `disc-info.json` naast de mp3's opgeslagen voor herkenning bij een volgende keer.

## Configuratie en bestandsindeling

De projectspecifieke instellingen staan met inline toelichting in `abcde.conf`.
Voor een gewoon album ziet de indeling er bijvoorbeeld zo uit:

```text
~/muziek/
└── Artist/
    └── Album/
        ├── 01. Artist - First Song.mp3
        ├── 02. Artist - Second Song.mp3
        └── disc-info.json
```

Bij een verzamelalbum kiest `abcde` zijn standaardimplementatie `VAOUTPUTFORMAT`:
`Various-${ALBUMFILE}/${TRACKNUM}.${ARTISTFILE}-${TRACKFILE}`, wordt dit:

```text
~/muziek/
└── Various-Summer Hits/
    ├── 01.Artist One-First Song.mp3
    ├── 02.Artist Two-Second Song.mp3
    └── disc-info.json
```

## Inhoud van disc-info.json

De JSON bevat de gegevens uit `read_disc.py`:

| Veld                        | Betekenis                                               |
|-----------------------------|---------------------------------------------------------|
| `disc_id`                   | MusicBrainz-disc-ID                                     |
| `cddb_id`                   | FreeDB/CDDB-disc-ID                                     |
| `toc`                       | Table of Contents: de cd-layout als tekst               |
| `first_track`, `last_track` | Eerste en laatste tracknummer                           |
| `lead_out_frame`            | Lead-outpositie in cd-frames                            |
| `tracks`                    | Per track: `number`, `length_frames` en `offset_frames` |

De JSON bevat geen artiest- of albumtitels en geen controlegetallen van de
mp3-bestanden. De herkenning is gebaseerd op de cd-layout, niet op vergelijking
van de audio.

## Aandachtspunten

- Een bestaande rip zonder `disc-info.json` wordt niet herkend.
- Bij een gevonden JSON controleert het script niet opnieuw of alle mp3's
  nog aanwezig en intact zijn. Bewaar of verwijder de JSON samen met de rip. 
  - TODO: controleer of alle bestanden bestaan en gezond zijn
- Een mislukte of onvolledige rip krijgt geen nieuwe JSON als de controles
  in de hook dat detecteren. 
