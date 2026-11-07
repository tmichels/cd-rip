# cd-rip

Ript audio-cd's naar losse mp3-bestanden en bewaart de cd-layout naast de
muziek. Een cd wordt overgeslagen als dezelfde layout al in de muziekbibliotheek
is geregistreerd
1. Plaats een cd en het script wordt automatisch opgestart (zie kopje hieronder).
2. Het script leest de cd-layout en gebruikt deze als een soort vingerafdruk.
2. Het vergelijkt de vingerafdruk van de cd met alle vingerafdrukken opgeslagen in de bibliotheek.
2. Is de cd al geregistreerd, dan wordt het rippen overgeslagen.
3. Anders ript `abcde` de cd naar mp3's met metadata, volgens `abcde.conf`.
4. Na controle op fouten en voltooide tracks wordt de vingerafdruk als
   `disc-info.json` naast de mp3's opgeslagen voor herkenning bij een volgende keer.

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
- `id3v2`
- "De map $HOME/muziek"

Op Debian/Ubuntu kun je de benodigdheden als volgt installeren:

```bash
sudo apt install python3-venv libdiscid0 abcde lame id3v2 jq
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
mkdir -p "$HOME/muziek"
```

## Automatisch starten bij het plaatsen van een cd

`99-cd-rip.rules` laat udev de systemd-service `cd-rip.service` starten zodra
een audio-cd in `/dev/sr0` wordt herkend. Data-cd's en lege stations starten
geen rip. Het rippen draait zonder terminal of interactieve vragen.

Installeer en laad de bestanden met:

```bash
sudo install -m 0644 cd-rip.service /etc/systemd/system/cd-rip.service
sudo install -m 0644 99-cd-rip.rules /etc/udev/rules.d/99-cd-rip.rules
sudo systemctl daemon-reload
sudo udevadm control --reload-rules
```

Bekijk de status en uitvoer met:

```bash
systemctl status cd-rip.service
journalctl -u cd-rip.service
```

## Logbestanden

Het script toont alle uitvoer en foutmeldingen op de terminal en schrijft ze
ook automatisch naar `log/YYYYMMDD_HH:MM:SS.log` in de projectmap. Oude logs worden automatisch opgeruimd, 
er is een instelbaar max aantal logbestanden.

## Configuratie en bestandsindeling

De projectspecifieke instellingen staan met inline toelichting in `abcde.conf`.
De actie `tag` schrijft de metadata die `abcde` heeft opgehaald met `id3v2`
als ID3v2.3-tags in iedere mp3: artiest, tracktitel, albumtitel, jaar, genre,
tracknummer en commentaar (indien beschikbaar). Het tracknummer bevat ook het
totale aantal tracks. Bij verzamelalbums krijgt iedere track zijn eigen artiest
en wordt de albumartiest `Various`.

Ontbrekende gegevens in de metadatabron, zoals het jaar, worden niet automatisch
aangevuld. Deze tags staan in de mp3 zelf, niet in `disc-info.json`.
Dit geldt voor nieuwe rips; bestaande rips worden nog steeds overgeslagen en
krijgen hiermee niet achteraf nieuwe tags.

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
