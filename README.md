# cd-rip

Ript audio-cd's naar losse mp3-bestanden en bewaart de cd-layout naast de
muziek. Een cd wordt overgeslagen als dezelfde layout al in de muziekbibliotheek
is geregistreerd
1. Plaats een cd en het script wordt automatisch opgestart (zie kopje hieronder).
2. Het script leest de cd-layout en gebruikt deze als een soort vingerafdruk.
2. Het vergelijkt de vingerafdruk van de cd met alle vingerafdrukken opgeslagen in de bibliotheek.
2. Is de cd al geregistreerd, dan wordt het rippen overgeslagen.
3. Anders haalt `fetch_metadata.py` de metadata op bij MusicBrainz (zie "Metadata"
   hieronder) en ript `abcde` de cd naar mp3's met die metadata, volgens `abcde.conf`.
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
- `glyrc` (pakket `glyrc`, voor het downloaden van albumhoezen)
- `eyeD3` (pakket `eyed3`, voor het insluiten van albumhoezen in mp3's)
- ImageMagick (voor herkenning en conversie van afbeeldingen)
- "De map $HOME/muziek"

Op Debian/Ubuntu kun je de benodigdheden als volgt installeren:

```bash
sudo apt install python3-venv libdiscid0 abcde lame id3v2 jq glyrc eyed3 imagemagick
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

De actie `playlist` maakt een `.m3u` in de albummap, ook bij verzamelalbums.
De playlist bevat de tracks in cd-volgorde met relatieve paden, zodat je de
hele albummap kunt verplaatsen.

`getalbumart` probeert automatisch een albumhoes te downloaden.
`embedalbumart` sluit deze met `eyeD3` in iedere mp3 in. In abcde 2.9.3 wordt
de losse afbeelding daarna bewaard in `albumart_backup/cover.jpg` in de
albummap. Als er geen hoes wordt gevonden, kan de rip zonder hoes doorgaan;
de uitvoer van `abcde` staat in het logbestand. Omdat het rippen niet-interactief
is, wordt niet gevraagd om een hoes te kiezen of te bevestigen.
Ook playlists en albumhoezen worden alleen bij nieuwe rips toegevoegd.

Voor een gewoon album ziet de indeling er bijvoorbeeld zo uit:

```text
~/muziek/
└── Artist/
    └── Album/
        ├── 01. Artist - First Song.mp3
        ├── 02. Artist - Second Song.mp3
        ├── Album.m3u
        ├── albumart_backup/
        │   └── cover.jpg
        └── disc-info.json
```

Bij een verzamelalbum kiest `abcde` zijn standaardimplementatie `VAOUTPUTFORMAT`:
`Various-${ALBUMFILE}/${TRACKNUM}.${ARTISTFILE}-${TRACKFILE}`, wordt dit:

```text
~/muziek/
└── Various-Summer Hits/
    ├── 01.Artist One-First Song.mp3
    ├── 02.Artist Two-Second Song.mp3
    ├── Summer Hits.m3u
    ├── albumart_backup/
    │   └── cover.jpg
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

## Metadata

Voor een nieuwe cd haalt `fetch_metadata.py` eerst de metadata op bij de
MusicBrainz-API, los van `abcde`. De uitkomst bepaalt of er geript wordt:

| Antwoord van MusicBrainz | Gevolg                                                             |
|--------------------------|--------------------------------------------------------------------|
| 200                      | Metadata wordt opgeslagen en gebruikt voor de rip                  |
| 404 (disc onbekend)      | De rip gaat door zonder metadata; `abcde` zoekt niet opnieuw       |
| 503 (server bezet)       | Elke 5 seconden opnieuw, 1 minuut lang; daarna wordt afgebroken    |
| 400 en alle andere fouten| De rip wordt afgebroken                                            |

Bij een afgebroken rip wordt de cd uitgeworpen.

De metadata staat in `metadata/<disc_id>/` in de projectmap:
`musicbrainz.json` (het antwoord), `disc-info.json` (de cd-layout) en
`cddb/<cddb_id>`. Dat laatste bestand maakt `musicbrainz_to_cddb.py` van de
JSON; `abcde` leest het via `CDDBLOCALDIR`, zodat de rip precies deze metadata
gebruikt. Als MusicBrainz meerdere releases voor de disc kent, wordt de eerste
gebruikt. Het genre wordt niet ingevuld. Ontbreekt de disc_id in het antwoord of
klopt het aantal tracks niet met de cd, dan wordt afgebroken.

## Aandachtspunten

- Een bestaande rip zonder `disc-info.json` wordt niet herkend.
- Bij een gevonden JSON controleert het script niet opnieuw of alle mp3's
  nog aanwezig en intact zijn. Bewaar of verwijder de JSON samen met de rip. 
  - TODO: controleer of alle bestanden bestaan en gezond zijn
- Een mislukte of onvolledige rip krijgt geen nieuwe JSON als de controles
  in de hook dat detecteren. 
