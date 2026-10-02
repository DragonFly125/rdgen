#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UNTERSTUETZTVON 2026-10-02 — der Markenlink unter der ID.

Die Zeile „Unterstuetzt von <Name>" unter dem ID-Feld ist ein
unterstrichener Link. Sie entsteht aus zwei voneinander unabhaengigen
Stellen:

  Text  : src/lang/<sprache>.rs, Eintrag ("powered_by_me", ...).
          Den ersetzt der Ablaufschritt „Update macOS Info.plist and
          settings" bereits mit `appname` (RustDesk -> appname).
          Bemerkenswert: src/lang.rs schliesst `powered_by_me`
          ausdruecklich von der LAUFZEIT-Ersetzung aus (Z. 228) — der
          Text haengt also ALLEIN an diesem sed zur Bauzeit.
  Ziel  : flutter/lib/common.dart, loadPowered() ->
          launchUrl(Uri.parse('https://rustdesk.com'))

Warum der Ablauf das Ziel bisher nicht korrigiert hat: RDGen setzt einen
fehlenden Parameter `urlLink` SELBST auf "https://rustdesk.com"
(rdgenerator/views.py Z. 53-54). Der sed im Ablauf ersetzt dann
rustdesk.com durch rustdesk.com — ein gruener Bau mit unveraendertem
Erzeugnis. Genau diese Fehlerklasse (gruener Bau, wirkungsloses
Erzeugnis) hat dieses Haus hier schon mehrfach getroffen.

Dieses Skript macht den Markenlink deshalb unabhaengig davon, ob der
Parameter gesetzt wurde — dieselbe Begruendung, aus der `bau-lokal.ps1`
seine Branding-Vorgabewerte fest eingebaut hat („damit ein Aufruf OHNE
diese Parameter trotzdem korrekt gebrandet baut, statt versehentlich
wieder unbebrandet zu sein").

Zusaetzlich prueft es den Anzeigenamen gegen die dokumentierte
Hausregel „RDGen Custom App Name darf KEIN Leerzeichen enthalten"
(produkte/rustdesk-cortendesk.md). Haette diese Pruefung am 2026-10-02
schon gelaufen, waere der Kundenbau fuer IT.EckSe GmbH ROT geworden,
statt den Endkundennamen als Anzeigenamen auszuliefern.

Umgebungsvariablen
  APPNAME         RDGens `appname` (Pflicht)
  MARKEN_URL      Linkziel der Hausmarke (Pflicht, https://...)
  URLLINK         RDGens `urlLink`, darf leer oder rustdesk.com sein
  MARKEN_PRAEFIX  erwarteter Anfang von APPNAME; leer = Pruefung aus

Rueckgabewert 0 nur, wenn danach nachweislich das Markenziel im
Quelltext steht. Jeder andere Fall ist Exit 1 — es wird erst
geschrieben, wenn alle Vorbedingungen gehalten haben.
"""

import os
import re
import sys

ZIELDATEI = "flutter/lib/common.dart"
FUNKTION = "Widget loadPowered(BuildContext context) {"
# Bewusst eng: genau der Aufruf, den loadPowered beim Antippen ausloest.
AUFRUF = re.compile(r"launchUrl\(Uri\.parse\('([^']*)'\)\);")


def fehler(text):
    print(f"FEHLER: {text}", file=sys.stderr)
    sys.exit(1)


def main():
    appname = os.environ.get("APPNAME", "").strip()
    marken_url = os.environ.get("MARKEN_URL", "").strip()
    urllink = os.environ.get("URLLINK", "").strip()
    praefix = os.environ.get("MARKEN_PRAEFIX", "").strip()

    # ---- Teil 1: Anzeigename gegen die Hausregel pruefen --------------
    if not appname:
        fehler("APPNAME ist leer. Ohne Anzeigenamen ist der Bau nicht beurteilbar.")
    if " " in appname:
        fehler(
            f"Anzeigename '{appname}' enthaelt ein Leerzeichen. "
            "Hausregel (produkte/rustdesk-cortendesk.md): RDGens Custom App Name "
            "darf KEIN Leerzeichen enthalten — es bricht sc create/sc stop/"
            "taskkill (RustDesk #14541) und erzeugt auf macOS einen "
            "Buendelkennzeichner mit Leerzeichen."
        )
    if praefix:
        if not appname.startswith(praefix):
            fehler(
                f"Anzeigename '{appname}' beginnt nicht mit '{praefix}'. "
                "Der angezeigte Name soll die Hausmarke tragen, nicht den "
                "Endkundennamen (die Gruppenbindung laeuft ueber apiServer, "
                "nicht ueber den Namen). MARKEN_PRAEFIX leeren, wenn ein "
                "bewusst anders benannter Vergleichsbau gewollt ist."
            )
    else:
        print("HINWEIS: MARKEN_PRAEFIX ist leer — Praefixpruefung uebersprungen.")
    print(f"Anzeigename geprueft: {appname}")

    # ---- Teil 2: wirksames Linkziel bestimmen -------------------------
    if not marken_url:
        fehler("MARKEN_URL ist leer.")
    if not marken_url.startswith("https://"):
        fehler(f"MARKEN_URL '{marken_url}' ist kein https-Ziel.")
    if "rustdesk.com" in marken_url:
        fehler(f"MARKEN_URL '{marken_url}' zeigt auf rustdesk.com.")

    rustdesk_vorgaben = ("", "https://rustdesk.com", "https://rustdesk.com/")
    if urllink in rustdesk_vorgaben:
        ziel = marken_url
        grund = (
            "urlLink war leer bzw. der von RDGen eingesetzte Vorgabewert "
            "rustdesk.com -> Hausmarke eingesetzt"
        )
    elif "rustdesk.com" in urllink:
        fehler(
            f"urlLink '{urllink}' zeigt auf rustdesk.com, ist aber nicht der "
            "bekannte Vorgabewert. Das ist kein Fall, den dieses Skript "
            "stillschweigend ueberschreiben darf."
        )
    elif not urllink.startswith("https://"):
        fehler(f"urlLink '{urllink}' ist kein https-Ziel.")
    else:
        ziel = urllink
        grund = "urlLink war ausdruecklich gesetzt -> uebernommen"
    print(f"Linkziel: {ziel}  ({grund})")

    # ---- Teil 3: Vorbedingungen an der Zieldatei ----------------------
    if not os.path.isfile(ZIELDATEI):
        fehler(f"{ZIELDATEI} fehlt. Falsches Arbeitsverzeichnis?")

    with open(ZIELDATEI, "r", encoding="utf-8") as f:
        zeilen = f.readlines()

    start = None
    for i, z in enumerate(zeilen):
        if FUNKTION in z:
            if start is not None:
                fehler(f"'{FUNKTION}' steht mehr als einmal in {ZIELDATEI}.")
            start = i
    if start is None:
        fehler(
            f"'{FUNKTION}' nicht gefunden. loadPowered() wurde umbenannt oder "
            "verschoben — der Markenlink muss neu bestimmt werden."
        )

    # Funktionsende an der ersten Zeile suchen, die genau "}" ist.
    ende = None
    for i in range(start + 1, len(zeilen)):
        if zeilen[i].rstrip("\n") == "}":
            ende = i
            break
    if ende is None:
        fehler("Ende von loadPowered() nicht gefunden.")

    # Gezaehlt werden VORKOMMEN, nicht Zeilen. Beides zu verwechseln war
    # ein echter Fehler in der ersten Fassung dieses Skripts: zwei
    # launchUrl-Aufrufe in EINER Zeile sahen wie einer aus, die Datei
    # wurde geschrieben und erst die Gegenprobe danach brach ab — die
    # Datei blieb veraendert zurueck. Aufgefallen ist das nur, weil der
    # Schlechtfall wirklich ausgeloest wurde.
    rumpf_vorher = "".join(zeilen[start:ende + 1])
    anzahl = len(AUFRUF.findall(rumpf_vorher))
    if anzahl == 0:
        fehler(
            "In loadPowered() gibt es keinen launchUrl(Uri.parse('...'))-Aufruf. "
            "Der Link wird dort nicht mehr geoeffnet."
        )
    if anzahl > 1:
        fehler(
            f"In loadPowered() gibt es {anzahl} launchUrl-Aufrufe. "
            "Eindeutig war genau einer erwartet."
        )

    treffer = [i for i in range(start, ende + 1) if AUFRUF.search(zeilen[i])]
    nr = treffer[0]
    vorher = AUFRUF.search(zeilen[nr]).group(1)
    neue_zeile = AUFRUF.sub(f"launchUrl(Uri.parse('{ziel}'));", zeilen[nr], count=1)

    print(f"Datei : {ZIELDATEI}")
    print(f"Zeile : {nr + 1}  (loadPowered: Z. {start + 1}-{ende + 1})")
    print(f"vorher: {vorher!r}")
    print(f"jetzt : {ziel!r}")

    if vorher == ziel:
        print("Bereits korrekt — keine Aenderung geschrieben.")
    else:
        zeilen[nr] = neue_zeile
        with open(ZIELDATEI, "w", encoding="utf-8") as f:
            f.writelines(zeilen)

    # ---- Teil 4: Gegenprobe NACH dem Schreiben ------------------------
    # Nicht der Speicherinhalt wird geprueft, sondern die Datei auf der
    # Platte. Fall 9 aus der 0004-Abnahme hat gezeigt, dass genau diese
    # Pruefung etwas unterscheidet und nicht nur mitlaeuft.
    with open(ZIELDATEI, "r", encoding="utf-8") as f:
        neu = f.readlines()

    if len(neu) != len(zeilen):
        fehler("Zeilenzahl hat sich geaendert.")

    rumpf = "".join(neu[start:ende + 1])
    if f"launchUrl(Uri.parse('{ziel}'));" not in rumpf:
        fehler("Gegenprobe: das Markenziel steht nach dem Schreiben NICHT in loadPowered().")
    if "rustdesk.com" in rumpf:
        fehler("Gegenprobe: in loadPowered() steht weiterhin rustdesk.com.")
    if len(AUFRUF.findall(rumpf)) != 1:
        fehler("Gegenprobe: loadPowered() enthaelt nicht mehr genau einen launchUrl-Aufruf.")

    print("Gegenprobe am Ergebnis bestanden (Markenziel gesetzt, kein rustdesk.com, 1 Aufruf, Zeilenzahl gleich)")

    # ---- Teil 5: ehrliche Restmeldung, OHNE Abbruch -------------------
    # Diese Stellen bleiben absichtlich unberuehrt: sie liegen hinter
    # Einstellungsseiten, die in der Soforthilfe ausgeblendet sind
    # (hide-general-settings/hide-security-settings). Sie werden
    # genannt, damit niemand glaubt, die Datei sei jetzt frei von
    # rustdesk.com.
    rest = [
        (i + 1, neu[i].strip())
        for i in range(len(neu))
        if "rustdesk.com" in neu[i] and not (start <= i <= ende)
    ]
    print(f"Verbleibende rustdesk.com-Stellen in {ZIELDATEI}: {len(rest)}")
    for nr_, txt in rest:
        print(f"  Z. {nr_}: {txt[:110]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
