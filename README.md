# cd-rip

Ript audio-cd's naar losse mp3-bestanden en bewaart de cd-layout naast de
muziek. Een cd wordt overgeslagen als deze al in de muziekbibliotheek
is geregistreerd
1. Plaats een cd en het script wordt automatisch opgestart.
2. Het script leest de cd-layout en gebruikt deze als een soort vingerafdruk.
3. Het vergelijkt de vingerafdruk van de cd met alle vingerafdrukken opgeslagen in de bibliotheek.
4. Is de cd al geregistreerd, dan wordt het rippen overgeslagen.
5. Anders haalt `fetch_metadata.py` de metadata op bij MusicBrainz (zie "Metadata"
   hieronder) en ript `abcde` de cd naar mp3's met die metadata, volgens `abcde.conf`.
6. Na controle op fouten en voltooide tracks wordt de gebruikte MusicBrainz-release
   als `musicbrainz.json` en de vingerafdruk als `disc-info.json` naast de mp3's
   opgeslagen; de release-ID staat ook in elke mp3 als de ID3-tag
   `MusicBrainz Album Id`. De vingerafdruk dient voor herkenning bij een volgende keer.

## Installatie

Het project gebruikt:

- Linux
- Bash
- `flock` (pakket `util-linux`, voor het voorkomen van gelijktijdige rips)
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
sudo apt install python3-venv libdiscid0 abcde lame id3v2 jq glyrc eyed3 imagemagick util-linux
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
Een poging die wordt geweigerd omdat een andere rip al bezig is, meldt dat op
de terminal of in het systemd-journal en krijgt geen eigen logbestand.

Als de rip automatisch via `cd-rip.service` is gestart, staat de uitvoer ook in
het systemd-journal. Vraag die op met:

```bash
journalctl -u cd-rip.service
```

## Bestandsindeling

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
        ├── disc-info.json
        └── musicbrainz.json
```
Bij een album met meerdere cd's krijgt elke cd een eigen submap. 

## Metadata

Voor een nieuwe cd haalt `fetch_metadata.py` eerst de metadata op bij de
MusicBrainz-API, los van `abcde`. De uitkomst bepaalt of er geript wordt:

| Antwoord van MusicBrainz | Gevolg                                                             |
|--------------------------|--------------------------------------------------------------------|
| 200                      | Metadata wordt opgeslagen en gebruikt voor de rip                  |
| 404 (disc onbekend)      | De rip wordt afgebroken en de cd blijft in het station            |
| 503 (server bezet)       | Elke 5 seconden opnieuw, 1 minuut lang; daarna wordt afgebroken    |
| 400 en alle andere fouten| De rip wordt afgebroken                                            |

### Handmatig een MusicBrainz-release kiezen

Als de cd niet wordt herkend, blijft hij in het station. Zoek zelf de juiste
**release-ID** op MusicBrainz (de UUID in `/release/...`, niet een
release-group-ID). Wacht tot de automatische poging is afgelopen en start
vanuit de projectmap, bijvoorbeeld:

```bash
./rip-cd.sh e925ed61-5bbf-41d8-a352-e31f2ef53f8e
```

Het script haalt deze release op en geeft de metadata via het lokale
CDDB-bestand door aan `abcde`, inclusief de bestaande tag-, bestandsnaam- en
albumhoesverwerking.

Bij meerdere cds kiest het script eerst op disc-ID, anders op een uniek
overeenkomend aantal tracks. Is dat niet eenduidig, geef dan ook het discnummer
binnen de release op:

```bash
./rip-cd.sh e925ed61-5bbf-41d8-a352-e31f2ef53f8e 2
```

Het aantal tracks moet altijd overeenkomen; anders stopt de rip en blijft de cd
in het station. 
