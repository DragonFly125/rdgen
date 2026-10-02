#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KEINMIKROFON 2026-10-02 -- der macOS-Client fragt nicht mehr nach dem
Mikrofon.

MASTERS BEFUND
--------------
Beim Test des ersten echten Kundenbaus (IT.EckSe GmbH, 02.10.) auf seinem
eigenen Mac: "und nach dem microfon soll nicht gefragt werden von der app
das wird nicht benoetigt."

WOHER DIE ABFRAGE KOMMT -- GELESEN, NICHT VERMUTET
--------------------------------------------------
Zwei Dinge muessen zusammenkommen, damit macOS den Mikrofon-Dialog zeigt:

1) flutter/macos/Runner/Info.plist traegt
     <key>NSMicrophoneUsageDescription</key>
   Ohne diesen Schluessel gibt es keinen Dialog -- die App wird beim
   Zugriff stattdessen vom System ABGESCHOSSEN. Der Schluessel allein
   loest aber nichts aus; er ist die Erlaubnis zu fragen, nicht die
   Frage.

2) src/server/audio_service.rs oeffnet tatsaechlich einen Eingabestrom.
   RustDesk ruft dafuer KEIN AVCaptureDevice.requestAccess auf -- der
   Dialog entsteht passiv, sobald CoreAudio den Strom aufmacht
   (build_input_stream, Z. 423).

   Die Kette dorthin, in dieser Fassung (1.4.9):

     cpal_impl::play()  ->  get_device()  ->  get_audio_input(..)

   und in get_audio_input() steht als letzter Rueckfall

     let device = device.unwrap_or(
         HOST.default_input_device()...

   HOST ist cpal::default_host(), auf macOS also CoreAudio. Das
   Standard-EINGABE-Geraet eines Macs ist das MIKROFON. Auf dem
   x86_64-Bau (ohne --screencapturekit) wird dieser Zweig IMMER genommen,
   auf dem aarch64-Bau immer dann, wenn ScreenCaptureKit nicht verfuegbar
   ist (get_device(), Z. 269-270: `return get_audio_input("")`).

   Der Kommentar in Zeile 1-7 derselben Datei sagt es selbst: cpal kennt
   auf dem Mac kein Loopback. Was dort als "Ton des Rechners" uebertragen
   wird, ist in Wahrheit das Mikrofon.

WAS DIESES SKRIPT TUT
---------------------
A) audio_service.rs: Auf macOS wird das Standard-Eingabegeraet NICHT mehr
   genommen. Fehlt ein Geraet, gibt get_audio_input() einen Fehler zurueck
   statt zum Mikrofon zu greifen. Der ScreenCaptureKit-Weg (Systemton,
   haengt an der Bildschirmaufnahme-Freigabe, nicht am Mikrofon) bleibt
   unveraendert.
   Auch die Suche nach einem NAMENTLICH eingestellten Geraet im
   CoreAudio-Host entfaellt auf macOS -- sie koennte wieder ein Mikrofon
   treffen.

B) common.rs: get_default_sound_input() fasst auf macOS cpal gar nicht
   mehr an und liefert None. Die Funktion wird nur fuer den Sprachanruf
   gebraucht, der ueber denselben Dienst laeuft und nach A) ohnehin kein
   Mikrofon mehr bekommt.

C) Info.plist: NSMicrophoneUsageDescription wird entfernt.

Die Reihenfolge ist nicht beliebig, und C) ist NICHT fuer sich allein
zulaessig: Ohne A) und B) wuerde das Entfernen des Schluessels aus einer
Abfrage einen ABSTURZ machen. Erst wenn kein Pfad mehr zugreift, ist das
Entfernen gefahrlos -- und dann ist es der Nachweis am Erzeugnis, dass
nicht mehr gefragt werden KANN.

WAS SICH DAMIT AM VERHALTEN AENDERT -- ehrlich benannt
------------------------------------------------------
* aarch64 (Apple Silicon): Systemton ueber ScreenCaptureKit wie bisher.
  Kein Unterschied, ausser dass der Rueckfall aufs Mikrofon wegfaellt.
* x86_64 (Intel-Mac): dieser Bau hat kein ScreenCaptureKit. Dort wurde
  bisher das MIKROFON uebertragen -- genau das, was weg soll. Ab jetzt
  kommt von einem Intel-Mac kein Ton mehr. Das ist beabsichtigt.
* Windows/Linux: nicht beruehrt. Dieses Skript laeuft nur im
  macOS-Bauablauf, und die Aenderungen in A) haengen zusaetzlich an
  cfg(target_os = "macos").

HARTE ABNAHME
-------------
Zweistufig: erst werden ALLE Anker in ALLEN Dateien gesucht, ohne etwas zu
schreiben. Fehlt einer oder kommt er mehrfach vor -> Abbruch, keine Datei
angefasst. Erst danach wird geschrieben und von der Platte gegengelesen.
Ein zweiter Lauf bricht ab.

Umgebungsvariablen (nur zum Testen, sonst Vorgabe):
  AUDIO_RS    src/server/audio_service.rs
  COMMON_RS   src/common.rs
  MAC_PLIST   flutter/macos/Runner/Info.plist
"""

import io
import os
import sys

AUDIO_RS = os.environ.get("AUDIO_RS", os.path.join("src", "server", "audio_service.rs"))
COMMON_RS = os.environ.get("COMMON_RS", os.path.join("src", "common.rs"))
MAC_PLIST = os.environ.get(
    "MAC_PLIST", os.path.join("flutter", "macos", "Runner", "Info.plist")
)

MARKE = "KEINMIKROFON 2026-10-02"


def abbruch(text):
    sys.stderr.write("KEINMIKROFON FEHLER: %s\n" % text)
    sys.exit(1)


def lies(pfad):
    if not os.path.isfile(pfad):
        abbruch("Datei nicht gefunden: %s (cwd=%s)" % (pfad, os.getcwd()))
    with io.open(pfad, "r", encoding="utf-8") as f:
        return f.read()


def schreib(pfad, inhalt):
    with io.open(pfad, "w", encoding="utf-8", newline="") as f:
        f.write(inhalt)


def pruefe_anker(inhalt, anker, pfad, wofuer):
    n = inhalt.count(anker)
    if n != 1:
        abbruch(
            "%s: Anker fuer %s kommt %d mal vor, erwartet genau 1.\n  Anker: %r"
            % (pfad, wofuer, n, anker[:160])
        )


def ersetze(inhalt, alt, neu, pfad, wofuer):
    pruefe_anker(inhalt, alt, pfad, wofuer)
    return inhalt.replace(alt, neu, 1)


# ---------------------------------------------------------------------------
# A) src/server/audio_service.rs
# ---------------------------------------------------------------------------

# A1 -- die Schaltgroesse direkt hinter die lazy_static-Gruppe von cpal_impl.
A1_ALT = """    lazy_static::lazy_static! {
        static ref HOST: Host = cpal::default_host();
        static ref INPUT_BUFFER: Arc<Mutex<std::collections::VecDeque<f32>>> = Default::default();
    }
"""

A1_NEU = """    lazy_static::lazy_static! {
        static ref HOST: Host = cpal::default_host();
        static ref INPUT_BUFFER: Arc<Mutex<std::collections::VecDeque<f32>>> = Default::default();
    }

    // ===== KEINMIKROFON 2026-10-02 =====
    // Auf macOS ist HOST der CoreAudio-Host, und dessen Standard-EINGABE-
    // Geraet ist das Mikrofon. Ein Fernwartungswerkzeug braucht das nicht;
    // Master: "nach dem microfon soll nicht gefragt werden von der app das
    // wird nicht benoetigt."
    //
    // Die Abfrage entsteht nicht durch einen Aufruf, sondern passiv, sobald
    // CoreAudio den Eingabestrom aufmacht. Deshalb wird hier der WEG zum
    // Geraet abgeschnitten, nicht eine Abfrage unterdrueckt.
    //
    // Der ScreenCaptureKit-Weg (Systemton, haengt an der Freigabe
    // "Bildschirm- & Systemaudioaufnahme") bleibt unangetastet.
    #[cfg(target_os = "macos")]
    const KEIN_MIKROFON: bool = true;
    #[cfg(not(target_os = "macos"))]
    const KEIN_MIKROFON: bool = false;
"""

# A2 -- die Suche nach einem namentlich eingestellten Geraet im CoreAudio-Host.
A2_ALT = """        if device.is_none() && !audio_input.is_empty() {
            for d in HOST
                .devices()
                .with_context(|| "Failed to get audio devices")?
            {
"""

A2_NEU = """        // KEINMIKROFON 2026-10-02: auf macOS uebersprungen -- ein
        // namentlich eingestelltes Geraet aus dem CoreAudio-Host kann ein
        // Mikrofon sein. Auf allen anderen Systemen unveraendert.
        if !KEIN_MIKROFON && device.is_none() && !audio_input.is_empty() {
            for d in HOST
                .devices()
                .with_context(|| "Failed to get audio devices")?
            {
"""

# A3 -- der Rueckfall aufs Standard-Eingabegeraet.
#
# unwrap_or() wertet sein Argument IMMER aus, auch wenn device bereits
# Some ist. HOST.default_input_device() wuerde also selbst dann laufen,
# wenn der Wert gar nicht gebraucht wird. Deshalb ein match statt eines
# Wenn-dann vor der Zeile.
A3_ALT = """        let device = device.unwrap_or(
            HOST.default_input_device()
                .with_context(|| "Failed to get default input device for loopback")?,
        );
"""

A3_NEU = """        // KEINMIKROFON 2026-10-02: Hier stand
        //     let device = device.unwrap_or(HOST.default_input_device()?);
        // Das ist auf macOS der Griff zum Mikrofon -- und zwar immer, weil
        // unwrap_or sein Argument auch dann auswertet, wenn es nicht
        // gebraucht wird. Auf macOS wird jetzt stattdessen abgebrochen.
        let device = match device {
            Some(d) => d,
            None => {
                if KEIN_MIKROFON {
                    return Err(anyhow!(
                        "KEINMIKROFON: no system-audio device available; the microphone is deliberately not used in this build"
                    ));
                }
                HOST.default_input_device()
                    .with_context(|| "Failed to get default input device for loopback")?
            }
        };
"""

# ---------------------------------------------------------------------------
# B) src/common.rs
# ---------------------------------------------------------------------------

B1_ALT = """pub fn get_default_sound_input() -> Option<String> {
    #[cfg(not(target_os = "linux"))]
    {
        use cpal::traits::{DeviceTrait, HostTrait};
        let host = cpal::default_host();
        let dev = host.default_input_device();
"""

B1_NEU = """pub fn get_default_sound_input() -> Option<String> {
    // KEINMIKROFON 2026-10-02: Auf macOS wird cpal hier gar nicht mehr
    // angefasst. Die Funktion liefert nur den NAMEN des Standard-
    // Eingabegeraets und wird ausschliesslich fuer den Sprachanruf
    // gebraucht; der bekommt nach dem Patch in audio_service.rs ohnehin
    // kein Mikrofon mehr. Dass hier nichts mehr angefasst wird, ist die
    // Voraussetzung dafuer, NSMicrophoneUsageDescription gefahrlos aus der
    // Info.plist nehmen zu koennen.
    #[cfg(target_os = "macos")]
    {
        return None;
    }
    #[cfg(all(not(target_os = "linux"), not(target_os = "macos")))]
    {
        use cpal::traits::{DeviceTrait, HostTrait};
        let host = cpal::default_host();
        let dev = host.default_input_device();
"""

# ---------------------------------------------------------------------------
# C) flutter/macos/Runner/Info.plist
# ---------------------------------------------------------------------------

C1_ALT = """\t<key>NSMicrophoneUsageDescription</key>
\t<string>Record the sound from microphone for the purpose of the remote desktop.</string>
"""

C1_NEU = ""


def main():
    print("KEINMIKROFON 2026-10-02 -- Patch laeuft")
    print("  cwd = %s" % os.getcwd())

    audio = lies(AUDIO_RS)
    common = lies(COMMON_RS)
    plist = lies(MAC_PLIST)

    for pfad, inhalt in ((AUDIO_RS, audio), (COMMON_RS, common), (MAC_PLIST, plist)):
        if MARKE in inhalt or "KEINMIKROFON" in inhalt:
            abbruch("%s traegt die Marke %r schon -- zweiter Lauf." % (pfad, MARKE))

    # --- Stufe 1: alle Anker pruefen, NICHTS schreiben ---------------------
    pruefe_anker(audio, A1_ALT, AUDIO_RS, "lazy_static-Gruppe in cpal_impl")
    pruefe_anker(audio, A2_ALT, AUDIO_RS, "CoreAudio-Geraetesuche nach Namen")
    pruefe_anker(audio, A3_ALT, AUDIO_RS, "Rueckfall auf default_input_device")
    pruefe_anker(common, B1_ALT, COMMON_RS, "get_default_sound_input")
    pruefe_anker(plist, C1_ALT, MAC_PLIST, "NSMicrophoneUsageDescription")
    print("  Stufe 1: alle 5 Anker gefunden, nichts geschrieben")

    # --- Stufe 2: schreiben -----------------------------------------------
    audio = ersetze(audio, A1_ALT, A1_NEU, AUDIO_RS, "lazy_static-Gruppe")
    audio = ersetze(audio, A2_ALT, A2_NEU, AUDIO_RS, "CoreAudio-Geraetesuche")
    audio = ersetze(audio, A3_ALT, A3_NEU, AUDIO_RS, "Rueckfall")
    schreib(AUDIO_RS, audio)

    common = ersetze(common, B1_ALT, B1_NEU, COMMON_RS, "get_default_sound_input")
    schreib(COMMON_RS, common)

    plist = ersetze(plist, C1_ALT, C1_NEU, MAC_PLIST, "NSMicrophoneUsageDescription")
    schreib(MAC_PLIST, plist)

    # --- Stufe 3: von der Platte gegenlesen -------------------------------
    a = lies(AUDIO_RS)
    if a.count('const KEIN_MIKROFON: bool = true;') != 1:
        abbruch("%s: KEIN_MIKROFON=true nicht genau einmal vorhanden." % AUDIO_RS)
    if a.count('const KEIN_MIKROFON: bool = false;') != 1:
        abbruch("%s: KEIN_MIKROFON=false nicht genau einmal vorhanden." % AUDIO_RS)
    # Gegen den ANKER pruefen, nicht gegen eine Teilzeichenkette: der
    # Erklaerkommentar oben zitiert den alten Aufruf absichtlich woertlich,
    # eine Suche nach "device.unwrap_or(" wuerde ihn selbst finden und
    # einen Fehlschlag melden, obwohl der Code richtig ist. Genau in diese
    # Falle ist dieses Skript beim ersten Probelauf getreten.
    if A3_ALT in a:
        abbruch("%s: der unwrap_or-Rueckfall steht noch im Code." % AUDIO_RS)
    # default_input_device darf nur noch EINMAL vorkommen (im
    # Nicht-macOS-Zweig). Die zweite Fundstelle gehoert zu
    # HOST_SCREEN_CAPTURE_KIT und ist ein anderer Host.
    # Nur ECHTE Codezeilen zaehlen. Die Erklaerkommentare dieses Patches
    # nennen den alten Aufruf absichtlich beim Namen; wer die ganze Datei
    # durchsucht, zaehlt sie mit und bekommt eine falsche Zahl.
    code_zeilen = [
        z for z in a.splitlines() if not z.lstrip().startswith("//")
    ]
    n_dflt = sum(z.count("HOST.default_input_device()") for z in code_zeilen)
    if n_dflt != 1:
        abbruch(
            "%s: HOST.default_input_device() kommt in %d Codezeilen vor, erwartet 1."
            % (AUDIO_RS, n_dflt)
        )
    if a.count("if !KEIN_MIKROFON && device.is_none()") != 1:
        abbruch("%s: die CoreAudio-Geraetesuche ist nicht abgesichert." % AUDIO_RS)
    print("  audio_service.rs   OK (Mikrofon-Rueckfall entfernt, Namenssuche abgesichert)")

    c = lies(COMMON_RS)
    if c.count('#[cfg(target_os = "macos")]\n    {\n        return None;\n    }') != 1:
        abbruch("%s: macOS-Zweig in get_default_sound_input fehlt." % COMMON_RS)
    if c.count('#[cfg(all(not(target_os = "linux"), not(target_os = "macos")))]') != 1:
        abbruch("%s: der alte Zweig ist nicht auf nicht-macOS eingeschraenkt." % COMMON_RS)
    print("  common.rs          OK (get_default_sound_input fasst cpal auf macOS nicht an)")

    p = lies(MAC_PLIST)
    if "NSMicrophoneUsageDescription" in p:
        abbruch("%s: NSMicrophoneUsageDescription steht noch drin." % MAC_PLIST)
    # Die Datei muss weiterhin eine gueltige, vollstaendige plist sein.
    for pflicht in ("<key>CFBundleIdentifier</key>", "</dict>", "</plist>"):
        if pflicht not in p:
            abbruch("%s: %r fehlt nach dem Schnitt." % (MAC_PLIST, pflicht))
    try:
        import plistlib
        plistlib.loads(p.encode("utf-8"))
    except Exception as e:
        abbruch("%s: ist nach dem Schnitt keine gueltige plist mehr: %s" % (MAC_PLIST, e))
    print("  Info.plist         OK (NSMicrophoneUsageDescription entfernt, plist gueltig)")

    print("KEINMIKROFON -- alle 3 Dateien geaendert und gegengelesen")


if __name__ == "__main__":
    main()
