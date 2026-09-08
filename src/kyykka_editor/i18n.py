"""Application translations and the persisted interface language."""

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QSettings, QTranslator

LANGUAGES = {"en": "English", "fi": "Suomi"}
_language = "en"
_qt_translator: QTranslator | None = None

FINNISH = {
    "Undo latest change": "Kumoa viimeisin muutos",
    "Undo: {action}": "Kumoa: {action}",
    "Undid: {action}": "Kumottu: {action}",
    "Delete events": "Tapahtumien poisto",
    "Edit round 1 end": "Ensimmäisen puolen lopun muokkaus",
    "Edit game end": "Ottelun lopun muokkaus",
    "Override": "Oma arvo",
    "Uncheck Override to use the main timing settings.": "Poista Oma arvo -valinta käyttääksesi yleisiä aika-asetuksia.",
    " (custom timing)": " (oma ajoitus)",
    "Preparing export…": "Valmistellaan vientiä…",
    "Finalizing video…": "Viimeistellään videota…",
    "Elapsed: {time}": "Kulunut aika: {time}",
    "Export unavailable: round 1 ends after the game ends. Edit either end marker to fix the order.": "Vienti ei ole mahdollista: 1. puoli päättyy ottelun lopun jälkeen. Korjaa järjestys muokkaamalla jompaakumpaa loppumerkkiä.",
    "Edit throw": "Muokkaa heittoa",
    "Edit event": "Muokkaa tapahtumaa",
    "Edit selected…": "Muokkaa valittua…",
    "Edit selected event": "Muokkaa valittua tapahtumaa",
    "Thrower": "Heittäjä",
    "Use current playback position": "Käytä nykyistä toistokohtaa",
    "Enter a timestamp between {start} and {end} (hh:mm:ss.mmm).": "Anna aikaleima väliltä {start}-{end} (tt:mm:ss.mmm).",
    "Kyykkä Editor\nCopyright © 2026 jburn and contributors.\nLicensed under the GNU General Public License, version 3 or later (GPL-3.0-or-later). You may use, study, share, and modify the application under those terms. There is no warranty. See LICENSE in the application directory for the complete license.\n\nFFmpeg and FFprobe\nThe packaged Gyan full build is GPL-enabled. The exact obligations depend on the included build. See THIRD_PARTY_NOTICES.md in the application directory.\n\nPySide6 / Qt for Python\nAvailable under LGPLv3, GPLv3, and commercial licensing terms.": "Kyykkä Editor\nTekijänoikeus © 2026 jburn ja muut tekijät.\nSovellus on lisensoitu GNU General Public License -lisenssin versiolla 3 tai uudemmalla (GPL-3.0-or-later). Saat käyttää, tutkia, jakaa ja muokata sovellusta lisenssin ehtojen mukaisesti. Sovelluksella ei ole takuuta. Koko lisenssi on sovelluksen hakemiston LICENSE-tiedostossa.\n\nFFmpeg ja FFprobe\nPaketoitu Gyan-kooste käyttää GPL-lisenssiä. Tarkat velvoitteet riippuvat mukana toimitetusta koosteesta. Katso sovelluksen hakemiston THIRD_PARTY_NOTICES.md.\n\nPySide6 / Qt for Python\nSaatavilla LGPLv3-, GPLv3- ja kaupallisilla lisenssiehdoilla.",
    "About Kyykkä Editor": "Tietoja Kyykkä Editorista",
    "Packaged Windows application": "Paketoitu Windows-sovellus",
    "Development build": "Kehitysversio",
    "<h2>Kyykkä Editor</h2><p><b>Version:</b> {version}<br><b>Build:</b> {build}</p>": "<h2>Kyykkä Editor</h2><p><b>Versio:</b> {version}<br><b>Kooste:</b> {build}</p>",
    '<p><b>Contact and project:</b> <a href="{url}">{url}</a></p>': '<p><b>Yhteystiedot ja projekti:</b> <a href="{url}">{url}</a></p>',
    "License information": "Lisenssitiedot",
    "Match details": "Ottelun tiedot",
    "Match details…": "Ottelun tiedot…",
    "Browse…": "Selaa…",
    "One player per line": "Yksi pelaaja riville",
    "Match title": "Ottelun otsikko",
    "Video": "Video",
    "Team 1": "Joukkue 1",
    "Team 2": "Joukkue 2",
    "Team 1 players": "Joukkueen 1 pelaajat",
    "Team 2 players": "Joukkueen 2 pelaajat",
    "Round 1": "1. puoli",
    "Round 2": "2. puoli",
    "Scores": "Pisteet",
    "Open video": "Avaa video",
    "Video files (*.mp4 *.mov *.mkv *.avi *.m4v);;All files (*)": "Videotiedostot (*.mp4 *.mov *.mkv *.avi *.m4v);;Kaikki tiedostot (*)",
    "No video selected": "Videota ei ole valittu",
    "Rendering highlights": "Koostevideon luonti",
    "Rendering video. This can take several minutes…": "Luodaan videota. Tämä voi kestää useita minuutteja…",
    "Cancel": "Peruuta",
    "Cancelling render…": "Peruutetaan videon luontia…",
    "Play": "Toista",
    "Pause": "Tauko",
    "Mark impact": "Merkitse osuma",
    "Undo": "Kumoa",
    "Before impact": "Ennen osumaa",
    "After impact": "Osuman jälkeen",
    ",=next  .=previous": ",=seuraava  .=edellinen",
    "Current thrower": "Nykyinen heittäjä",
    "Mark round 1 end": "Merkitse 1. puolen loppu",
    "Mark game end": "Merkitse ottelun loppu",
    "Timeline events": "Aikajanan tapahtumat",
    "Event": "Tapahtuma",
    "Timestamp": "Aikaleima",
    "Remove selected": "Poista valitut",
    "Export highlights…": "Vie koostevideo…",
    "Estimated video length, including title/results and transitions. Highlights after the game-end marker are excluded.": "Arvioitu videon kesto sisältää otsikon, tulokset ja siirtymät. Ottelun loppumerkin jälkeiset heitot jätetään pois.",
    "Play or pause": "Toista tai keskeytä",
    "Next thrower": "Seuraava heittäjä",
    "Previous thrower": "Edellinen heittäjä",
    "Undo latest mark": "Kumoa viimeisin osuma",
    "Seek backward 3 seconds": "Siirry 3 sekuntia taaksepäin",
    "Seek forward 5 seconds": "Siirry 5 sekuntia eteenpäin",
    "Remove selected event": "Poista valitut tapahtumat",
    "&File": "&Tiedosto",
    "New match…": "Uusi ottelu…",
    "&Help": "&Ohje",
    "&Hotkeys": "&Pikanäppäimet",
    "&Language": "&Kieli",
    "&About Kyykkä Editor…": "&Tietoja Kyykkä Editorista…",
    "Video not found": "Videota ei löydy",
    "The video file does not exist:\n{path}": "Videotiedostoa ei löydy:\n{path}",
    "Loading {name}…": "Ladataan: {name}…",
    "Loaded: {name}": "Ladattu: {name}",
    "Playing: {name}": "Toistetaan: {name}",
    "Could not load video": "Videon lataaminen epäonnistui",
    "Qt could not decode this video file.": "Qt ei pystynyt avaamaan tämän videotiedoston sisältöä.",
    "Playback error": "Toistovirhe",
    "{detail}\n\nFile: {path}": "{detail}\n\nTiedosto: {path}",
    "No video": "Ei videota",
    "Open a video before marking impacts.": "Avaa video ennen osumien merkitsemistä.",
    "Open a video before marking events.": "Avaa video ennen tapahtumien merkitsemistä.",
    "Impact": "Osuma",
    "Impact: {name}": "Osuma: {name}",
    "Round 1 end": "1. puolen loppu",
    "Game end": "Ottelun loppu",
    "{count} highlight · Estimated video: {duration}": "{count} heitto · Arvioitu kesto: {duration}",
    "{count} highlights · Estimated video: {duration}": "{count} heittoa · Arvioitu kesto: {duration}",
    "unavailable": "ei saatavilla",
    "No impacts": "Ei osumia",
    "Mark at least one impact before exporting.": "Merkitse vähintään yksi osuma ennen vientiä.",
    "Round 1 end (round-one result screen)": "1. puolen loppu (ensimmäisen puolen tulosruutu)",
    "Game end (final result/winner screen)": "Ottelun loppu (lopputulos ja voittaja)",
    "Missing end markers": "Loppumerkkejä puuttuu",
    "The following markers have not been added:\n\n": "Seuraavia merkkejä ei ole lisätty:\n\n",
    "\n\nProceed without these markers and their result screens?": "\n\nJatketaanko ilman näitä merkkejä ja niiden tulosruutuja?",
    "Export highlights": "Vie koostevideo",
    "MP4 video (*.mp4)": "MP4-video (*.mp4)",
    "Rendering…": "Luodaan videota…",
    "Rendering highlights…": "Luodaan koostevideota…",
    "Export complete": "Vienti valmis",
    "Saved highlights to:\n{path}": "Koostevideo tallennettu:\n{path}",
    "Export failed": "Vienti epäonnistui",
    "Export cancelled": "Vienti peruutettu",
    "Final result": "Lopputulos",
    "Kyykka highlights": "Kyykkäkooste",
    "Round 1 result": "1. puolen tulos",
    "FFprobe was not found in the application bundle or on PATH": "FFprobe-ohjelmaa ei löytynyt sovelluksesta eikä PATH-ympäristömuuttujan hakemistoista",
    "FFmpeg was not found in the application bundle or on PATH": "FFmpeg-ohjelmaa ei löytynyt sovelluksesta eikä PATH-ympäristömuuttujan hakemistoista",
    "Could not determine the source video's dimensions": "Lähdevideon kokoa ei voitu selvittää",
    "Could not determine the source video's frame rate": "Lähdevideon kuvataajuutta ei voitu selvittää",
    "Could not create the title screen image": "Otsikkoruudun luonti epäonnistui",
    "Could not create the score screen image": "Tulosruudun luonti epäonnistui",
    "Could not create the thrower overlay": "Heittäjän nimitekstin luonti epäonnistui",
    "The export file must be different from the source video": "Vietävän tiedoston on oltava eri tiedosto kuin lähdevideo",
    "No source video is selected": "Lähdevideota ei ole valittu",
    "The game-end marker must be after the round-one marker": "Ottelun loppumerkin on oltava ensimmäisen puolen loppumerkin jälkeen",
    "Mark at least one impact before exporting": "Merkitse vähintään yksi osuma ennen vientiä",
    "Unknown FFmpeg error": "Tuntematon FFmpeg-virhe",
    "\n\nFull log: {path}": "\n\nKoko loki: {path}",
    "FFmpeg failed:\n{detail}{log_note}": "FFmpeg epäonnistui:\n{detail}{log_note}",
    "FFmpeg failed. Full log: {path}\n{detail}": "FFmpeg epäonnistui. Koko loki: {path}\n{detail}",
}


def tr(source: str, **values: object) -> str:
    text = FINNISH.get(source, source) if _language == "fi" else source
    return text.format(**values) if values else text


def language() -> str:
    return _language


def saved_language(settings: QSettings | None = None) -> str:
    settings = settings if settings is not None else QSettings("KyykkaEditor", "KyykkaEditor")
    value = settings.value("language", "en")
    return value if isinstance(value, str) and value in LANGUAGES else "en"


def set_language(code: str, *, persist: bool = False, settings: QSettings | None = None) -> None:
    global _language, _qt_translator
    if code not in LANGUAGES:
        raise ValueError(f"Unsupported language: {code}")
    app = QCoreApplication.instance()
    if app is not None and _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator.deleteLater()
    _qt_translator = None
    if app is not None and code == "fi":
        translator = QTranslator(app)
        directories = [
            Path(__file__).with_name("translations"),
            Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)),
        ]
        for directory in directories:
            if translator.load(str(directory / "qtbase_fi.qm")):
                app.installTranslator(translator)
                _qt_translator = translator
                break
    _language = code
    if persist:
        settings = settings if settings is not None else QSettings("KyykkaEditor", "KyykkaEditor")
        settings.setValue("language", code)
