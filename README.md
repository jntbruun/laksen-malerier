# Laksen malerier

Egne malerier på Laksen-serveren. Legg et vanlig maleri i en **stonecutter** og velg hvilket du vil ha.

## Legg til et maleri

1. Slipp bildet i `malerier/`. **Filnavnet blir navnet på maleriet.**
2. Vil du stå som kunstner: legg det i en undermappe med navnet ditt, f.eks. `malerier/Jason/Laksen.png`.
3. Størrelse velges automatisk (lengste side 4 blokker). Vil du bestemme selv: `Laksen (3x2).png` = 3 bredt, 2 høyt. Maks 16x16.
4. Dobbeltklikk **Publiser malerier.command**. Den bygger, pusher til GitHub, laster opp datapacken, oppdaterer `server.properties` og restarter serveren.

Vil du bare se resultatet lokalt først: **Bygg malerier.command**.

Bilder strekkes til formatet (ingenting kuttes bort) og skaleres ned til 128 px per blokk. Bruk png eller jpg (ikke HEIC).

### Første gang på en ny maskin

1. `git clone https://github.com/jntbruun/laksen-malerier`
2. Lag en API-nøkkel i [panelet](https://panel.spillhosting.no/account/api) og lim den inn i en fil `.panel-nokkel` i mappen. Den committes aldri.

## Rett på GitHub (uten å installere noe)

Alt som endres i `malerier/` på GitHub publiseres automatisk til serveren (Actions-fanen viser status, tar ca. ett minutt + restart).

- **Legge til:** åpne `malerier/` på GitHub → Add file → Upload files.
- **Gi nytt navn:** trykk `.` i repoet (åpner github.dev) → høyreklikk bildet → Rename → commit i Source Control-fanen.

Jobber du lokalt etterpå: kjør `git pull` først, Actionen committer tilbake.

## Endre navn eller bilde

- **Gi nytt navn:** bare endre filnavnet. Malerier som allerede henger oppdateres.
- **Bytt bilde:** behold filnavnet, erstatt bildet.
- **Slett:** malerier av den typen som henger i verden forsvinner. Tenk deg om.

`malerier.lock.json` husker hvilket bilde som er hvilket maleri. Ikke slett den, og commit den sammen med bildene.

## Hvor ting ligger

| Fil | Hvor |
| --- | --- |
| `dist/laksen-malerier-datapack.zip` | `world/datapacks/` på serveren |
| `dist/laksen-ressurspakke.zip` | GitHub, låst til en commit. `resource-pack` i `server.properties` peker dit |
| `dist/ressurspakke-sha1.txt` | `resource-pack-sha1` i `server.properties`. Uten den henter ikke klientene ny pakke |

Ressurspakken er hele Laksen-pakken (`base-resourcepack/`) pluss maleriene. Endrer dere noe annet i pakken (blader osv.), gjør det i `base-resourcepack/`.

## Innstillinger

Øverst i `build.py`:

- `PX_PER_BLOCK` (128): oppløsning. Høyere = skarpere, men tyngre pakke.
- `AUTO_LONGEST_SIDE` (4): standardstørrelse.
- `ONLY_OWN_PAINTINGS_WHEN_RANDOM` (True): et vanlig maleri som henges opp uten å velge, blir et av deres egne, aldri et vanilla-maleri.

## Gamle malerier

Denne datapacken erstatter **Splotch of Paint** og **REPO Paintings DP**. De kan slettes fra `world/datapacks/` når denne er lagt inn.

- Maleriene dere har byttet bilde på ligger i `malerier/` og beholder sine gamle ID-er (`splotch_of_paint:cozy_bay` osv.), så de som allerede henger, blir hengende. **Gi dem riktige navn ved å endre filnavnene.** Størrelsen i filnavnet må stå som den er; bygget stopper hvis den endres.
- De andre ~230 maleriene fra de gamle pakkene ligger i `gamle-malerier.json`. De registreres fortsatt, så ingenting som henger forsvinner, men de er ikke med i stonecutteren eller blant tilfeldige malerier.
