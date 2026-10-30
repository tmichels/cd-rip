# CD ripper command line tool

Een lokale commandlinetool die een audio-cd herkent, controleert of er al een
complete rip in de muziekbibliotheek staat en alleen ript wanneer dat nodig is.
De uitvoer bestaat uit MP3-bestanden, gemaakt met abcde en LAME.

Dit document beschrijft het te bouwen proces. De scripts en helpers zijn nog
niet volledig geimplementeerd.

Voer het script uit vanuit de projectmap.
De eerste stap is beschikbaar: `bash rip-cd.sh` leest `/dev/sr0` uit via
`read_disc.py` en toont de MusicBrainz Disc ID en TOC als JSON. De bibliotheekmap staat vast op
`/home/thomas/muziek`. Na het uitlezen zoekt `find` recursief naar
`disc-info.json` en roept via `-exec` de commandlinetool `jq` aan.
Deze vergelijkt de waarden van `disc_id` en `toc` met die van de ingelegde cd
en toont alleen overeenkomende paden. JSON-opmaak en veldvolgorde maken niet uit.
De Bash-variabele `matching_discs` bevat de overeenkomstmeldingen en is leeg
als er geen overeenkomst is. Dit zegt alleen iets over de cd-layout, niet over
compleetheid.
Er wordt uitgegaan van bestaande manifesten met geldige JSON.
Bij een overeenkomst wordt het rippen overgeslagen, nog zonder controle op
compleetheid. Zonder overeenkomst haalt het script eerst metadata op
met `abcde -a cddb -N` en toont de uitvoer van abcde. Daarna voert het script
`abcde -a cddb,read,encode,tag,move -N -x -o mp3` uit:
non-interactief rippen naar MP3 en uitwerpen zodra alle tracks zijn uitgelezen.
Er is geen projectspecifieke abcde-configuratie. Uitvoermap, naamgeving, drive
en encoderinstellingen volgen de bestaande systeem- en gebruikersconfiguratie
van abcde. Het Bash-script leest de vertrouwde `~/.abcde.conf` ook in om het
uitvoerpad en de naamopschoning te gebruiken. `library_dir` bepaalt waar naar
bestaande manifesten wordt gezocht.
Na de rip controleert het script abcde's foutenbestand en de verplaatsstatus
van iedere verwachte track. Vervolgens schrijft het `toc_output` als
`disc-info.json` in de albummap. De JSON bevat ook `cddb_id` om abcde's
werksessie terug te vinden; de MusicBrainz-identificatie blijft `disc_id`.
De actie `clean` is bewust weggelaten zodat de werkbestanden en status voor deze
controle en voor hervatten behouden blijven. De werkmap is standaard de
projectmap, tenzij `WAVOUTPUTDIR` in `~/.abcde.conf` is ingesteld.
Het albumpad volgt de hieronder vastgelegde naamgeving
`<artiest>/<album>`, met `mungefilename` uit de gebruikersconfiguratie.
Als die naamgeving verandert, moet het script worden aangepast.
Verzamelalbums worden voorlopig met een foutmelding gestopt voordat het
rippen begint, omdat daarvoor een andere naamgeving geldt.
Extra MP3-identificatietags en controle van de daadwerkelijke audiobestanden
zijn nog niet geimplementeerd.
Het script gebruikt Python uit de lokale `.venv`;
installeer de dependencies met
`.venv/bin/python -m pip install -r requirements.txt`.
Dit is de PyPI-pakketnaam van python-discid. De native library libdiscid moet
ook op het systeem aanwezig zijn. Trackoffsets zijn absolute cd-frameposities,
doorgaans 150 frames hoger dan de relatieve posities in `cdparanoia -Q`.

## Technische keuzes

- Bash stuurt het proces en de externe programma's aan.
- abcde verzorgt het rippen en encoderen met LAME.
- Een kleine Python-helper gebruikt python-discid met de native library
  libdiscid om de cd-identificatie uit te lezen.
- Een Python-helper met Mutagen leest en schrijft ID3v2-tags.
- JSON-metadata wordt met jq of Python verwerkt, niet met tekstfilters in Bash.
- Code en identifiers zijn Engels; documentatie en communicatie zijn Nederlands.
- Scripts en functies blijven kort en hebben elk een duidelijke
  verantwoordelijkheid. Herkenning, bibliotheekcontrole, rippen en tagging blijven
  gescheiden.

## Identificatie van een cd

Lees voor het rippen de Table of Contents (TOC) uit en bereken daarmee de
MusicBrainz Disc ID. Dit werkt lokaal, zonder metadata-opzoeking via internet en
zonder eerst de audio te rippen.

Bewaar de Disc ID samen met de volledige TOC, inclusief de eerste en laatste
track, de startposities en de lead-outpositie in cd-frames. Leg voor de opslag
een vast, versieerbaar formaat vast. Bewaar ook welke tracks audiotracks zijn,
zodat een eventuele datatrack niet als ontbrekende MP3 wordt behandeld.

Gebruik geen willekeurige UUID als herkenningssleutel: die kun je bij een
volgende keer inleggen niet opnieuw uit de cd afleiden. Verwar ook abcde's
CDDB-ID niet met de MusicBrainz Disc ID; dat zijn verschillende identifiers.

**Beperking:** Disc ID en TOC identificeren de trackindeling, niet gegarandeerd
de audio-inhoud. Andere persingen van hetzelfde album kunnen andere IDs hebben.
Verschillende cd's kunnen dezelfde TOC en dus hetzelfde ID hebben. Het proces
herkent daarom dezelfde cd-layout, niet gegarandeerd dezelfde opname of uitgave.
Een hash van dezelfde TOC lost deze beperking niet op.

## Voorbereiding

1. Installeer op het doelsysteem Bash, abcde, LAME, een ondersteunde cd-reader
   zoals cdparanoia, jq, Python 3 en libdiscid. Installeer de Python-packages
   python-discid en Mutagen, bij voorkeur in een eigen virtual environment.
   Pakketnamen en installatiecommando's verschillen per Linux-distributie.
2. Controleer of de gebruiker toegang heeft tot de cd-drive, bijvoorbeeld
   `/dev/sr0`, en schrijf toegang heeft tot de bibliotheek en werkmap.
3. Configureer het drivepad, de bibliotheekmap en een aparte werkmap. Plaats de
   werkmap bij voorkeur op hetzelfde bestandssysteem als de bibliotheek, zodat
   een complete rip met een atomaire hernoeming kan worden gepubliceerd.
4. Maak een eigen abcde-configuratie met MP3 als uitvoerformaat, LAME als encoder,
   de gewenste kwaliteit, bestandsnamen en metadata-opzoeking. Bepaal expliciet
   wat er moet gebeuren als metadata ontbreekt of meerdere resultaten oplevert.
5. Controleer vooraf of alle tools beschikbaar zijn. Test de herkenning en
   MP3-tagging afzonderlijk voordat het volledige proces wordt geautomatiseerd.

De MP3-kwaliteit is ingesteld op LAME `-V 2` (variabele bitrate).
Het beleid voor onzekere metadata moet nog worden gekozen.
Gebruik bij metadata-opzoekingen geen willekeurig zoekresultaat als bevestigde
albumidentiteit.

## Bestaande gebruikersconfiguratie van abcde

De configuratie staat in `~/.abcde.conf`, niet in de projectmap. abcde leest
dit bestand automatisch in:

```bash
OUTPUTDIR="$HOME/muziek"
OUTPUTFORMAT='${ARTISTFILE}/${ALBUMFILE}/${TRACKNUM}. ${ARTISTFILE} - ${TRACKFILE}'

mungefilename() {
    printf '%s\n' "$@" |
        sed 's|[<>:"/\\?*]|_|g; s/[. ]*$//'
}

LAMEOPTS='-V 2'
```

Voor gewone albums wordt het uitvoerpad hiermee:

```text
/home/thomas/muziek/<artiest>/<album>/<tracknummer>. <artiest> - <tracktitel>.mp3
```

`mungefilename` vervangt de tekens `<>:"/\?*` door underscores en verwijdert
punten en spaties aan het einde van namen. Spaties binnen namen blijven behouden.
LAME gebruikt met `-V 2` VBR-kwaliteitsniveau 2; dit is geen vaste bitrate.

De backslash na `OUTPUTDIR="$HOME/muziek"` uit de aangeleverde configuratie is
hier weggelaten: de twee instellingen kunnen op afzonderlijke regels staan.
`VAOUTPUTFORMAT` is niet ingesteld in dit fragment; voor verzamelalbums kan
abcde dus een ander pad gebruiken via de systeemconfiguratie of zijn standaard.
Het latere schrijven van `disc-info.json` moet dezelfde naamgeving volgen als
de daadwerkelijke uitvoer van abcde.

## Proces per ingelegde cd

### 1. Voorkom gelijktijdige verwerking

Neem een lock op de drive en op wijzigingen aan de bibliotheek, bijvoorbeeld met
`flock`. Voorkom dat twee processen dezelfde drive gebruiken of dezelfde rip
tegelijk publiceren. Geef een duidelijke melding als de benodigde lock bezet is.

### 2. Lees de cd-identificatie uit

Lees via de libdiscid-helper de MusicBrainz Disc ID, de volledige TOC en de
verwachte audiotracks. Bewaar dit als gestructureerde gegevens voor de rest van
de run. MCN en ISRC's kunnen als aanvullende informatie worden opgeslagen als
drive en cd die beschikbaar stellen.

Stop met een duidelijke foutmelding bij een lege drive, een onleesbare cd of
een disc zonder ondersteunde audiotracks. Een leesfout betekent niet dat de cd
nog niet in de bibliotheek staat.

### 3. Zoek de cd op in de bibliotheek

Scan de bibliotheek recursief op `disc-info.json` en vergelijk Disc ID en TOC.
Zoek op identifiers, niet op artiestnaam, albumtitel of mapnaam.

Controleer bij een match:

- Is de rip als compleet geregistreerd?
- Zijn alle verwachte audiotracks aanwezig, precies eenmaal per track?
- Zijn de bestanden leesbare MP3's met de afgesproken identificatietags?
- Komen de oorspronkelijke cd-tracknummers en de Disc ID overeen?

Een bestand met een passende tag, een bestaande albummap of alleen een manifest
is niet voldoende om een complete rip vast te stellen. Volledigheid betekent
hier ook niet dat de rip bit-perfect of met AccurateRip geverifieerd is.

### 4. Beslis of rippen nodig is

| Situatie | Actie |
|---|---|
| Complete rip met passende Disc ID en TOC | Sla het rippen over en meld de bestaande locatie. |
| Geen match | Start een nieuwe rip. |
| Gedeeltelijke of beschadigde rip | Meld het probleem; hervat of vervang alleen volgens een expliciet gekozen herstelbeleid. |
| Onzekere match of tegenstrijdige metadata | Vraag om een beslissing; sla niet stilzwijgend over. |
| Bibliotheek kan niet betrouwbaar worden gelezen | Stop met een foutmelding; behandel dit niet als een ontbrekende rip. |

Het beleid voor gedeeltelijke rips moet nog worden gekozen. Overschrijf
bestaande bestanden nooit automatisch.

### 5. Rip met abcde naar een werkmap

Maak een afzonderlijke werkmap voor deze run en laat abcde daar de audio
uitlezen en naar MP3 encoderen. Geef drive, eigen configuratie en uitvoerlocatie
expliciet door. abcde ondersteunt onder meer `-d` voor de drive, `-c` voor een
aanvullende configuratie en `-o mp3` voor het uitvoerformaat.

Gebruik non-interactieve modus (`-N`) alleen wanneer de keuzes rond metadata
vooraf zijn afgedekt. Bewaar stdout, stderr en de exitcode voor foutmeldingen en
diagnose. Gebruik geen debugmodus `-z` voor echte rips: die produceert slechts
korte fragmenten en kan bestaande uitvoer overschrijven.

Zorg dat de identificatie en de rip bij dezelfde ingelegde cd horen. Controleer
de identiteit opnieuw direct voor het lezen en voorkom wisselen of uitwerpen
tijdens het uitlezen waar het systeem dit ondersteunt.

### 6. Controleer de uitvoer

Ga alleen verder als abcde succesvol is afgesloten en alle verwachte
audiotracks als leesbare, niet-lege MP3's aanwezig zijn. Controleer de koppeling
tussen brontracknummer en uitvoerbestand; leid die niet alleen af uit alfabetisch
gesorteerde bestandsnamen. Gebruik een decodercontrole om kapotte MP3-streams op
te sporen; alleen geldige ID3-tags bewijzen niet dat de audio geldig is.

Laat bij een mislukking de bruikbare werkbestanden en logs staan voor diagnose
of hervatten. Publiceer de rip niet als compleet.

### 7. Schrijf identificatietags

Schrijf met Mutagen op iedere MP3 dezelfde disc-identificatie, zonder de audio
opnieuw te encoderen:

| ID3v2-veld | Inhoud |
|---|---|
| `TXXX:MusicBrainz Disc Id` | De uit de fysieke cd berekende MusicBrainz Disc ID. |
| `TXXX:CDRIP_TOC` | De volledige TOC in het afgesproken, versieerbare formaat. |
| `TXXX:CDRIP_SOURCE_TRACK` | Het oorspronkelijke tracknummer op de cd. |
| `TXXX:CDRIP_AUDIO_TRACK_COUNT` | Het verwachte aantal audiotracks van deze cd. |

Behoud bestaande muziekmetadata en albumafbeeldingen. Lees de tags na het
schrijven opnieuw uit en controleer de waarden. abcde's `-w` schrijft een
commentaarveld; gebruik dat niet als vervanging voor deze expliciete
identificatietags.

### 8. Schrijf het manifest en publiceer de rip

Maak in de werkmap een `disc-info.json` met minimaal:

- Schemaversie, MusicBrainz Disc ID en volledige TOC.
- De verwachte audiotracks en hun oorspronkelijke tracknummers.
- Een mapping van die tracknummers naar relatieve MP3-bestandspaden.
- De gebruikte encoderinstellingen en het tijdstip van de rip.
- Een expliciete status die pas na alle controles op compleet wordt gezet.

Verplaats de complete uitvoermap daarna naar de bibliotheek zonder bestaande
rips te overschrijven. Gebruik op hetzelfde bestandssysteem een atomaire
hernoeming. Is dat niet mogelijk, kopieer dan eerst naar een stagingmap op het
doelbestandssysteem, controleer de kopie en publiceer die pas daarna.

Werk pas na publicatie een eventuele lokale index bij. Werp de cd desgewenst
uit na een geslaagde verwerking.

## MP3-tags, manifesten en index

De identificatietags reizen mee als MP3's worden verplaatst of hernoemd.
`disc-info.json` maakt snel zoeken mogelijk zonder iedere keer alle tags te
lezen. Een optionele lokale index versnelt dat verder, maar is een cache en
moet opnieuw op te bouwen zijn.

Als manifestpaden niet meer kloppen, zoek dan de bestanden opnieuw op via de
tags en herstel het manifest pas na controle van alle tracks. Bij ontbrekende
of tegenstrijdige gegevens wordt een rip niet automatisch als compleet
beschouwd. Een manifest en een index mogen nooit als enig bewijs dienen dat de
MP3's nog aanwezig zijn.

## Bestaande rips opnemen

1. Inventariseer bestaande MP3-tags, cue-sheets en riplogs.
2. Importeer een expliciet opgeslagen MusicBrainz Disc ID en volledige TOC als
   die beschikbaar en consistent zijn. Een CDDB-ID is hiervoor geen vervanging.
3. Controleer of alle verwachte tracks aanwezig zijn voordat tags en een compleet
   manifest worden toegevoegd.
4. Behandel herkenning op alleen titels en afgeronde speelduur als onzeker.
   De oorspronkelijke TOC is daaruit niet altijd exact te reconstrueren.
5. Gebruik zo nodig de originele cd om de identiteit vast te leggen en laat de
   koppeling met een bestaande rip bevestigen. Alleen het inleggen van die cd
   bewijst niet dat een willekeurige bestaande map de juiste audio bevat.

## Foutafhandeling en controles

- Controleer exitcodes van externe programma's en geef fouten expliciet door.
- Quote paden en argumenten; ondersteun spaties en speciale tekens in namen.
- Voer metadata niet als shellcode uit. Houd de abcde-configuratie vertrouwd:
  abcde leest deze als shellconfiguratie in.
- Gebruik traps voor het vrijgeven van locks en houd incomplete uitvoer buiten
  de gepubliceerde bibliotheek.
- Verwijder bij opruimen uitsluitend de bekende tijdelijke bestanden van de
  betreffende run, nooit bestaande rips.
- Test dubbele cd's, ontbrekende tracks, foutieve tags, verplaatste bestanden,
  een lege drive, leesfouten, een volle schijf en onderbroken runs.
- Controleer Bash-code met ShellCheck en test helpers en beslislogica met
  fixtures, zodat hiervoor niet telkens een fysieke cd nodig is.

## Bronnen

- [abcde-handleiding](https://manpages.debian.org/testing/abcde/abcde.1.en.html)
- [libdiscid](https://musicbrainz.org/doc/libdiscid)
- [MusicBrainz Disc ID en beperkingen](https://musicbrainz.org/doc/Disc_ID)
- [python-discid](https://python-discid.readthedocs.io/)
- [Mutagen](https://mutagen.readthedocs.io/)