#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MACCUSTOMPFAD -- leitet den Ablageort der Laufzeit-Konfigurationsdatei
AUS DEM QUELLTEXT ab, statt ihn abzuschreiben.

Hintergrund (2026-10-01, belegt in
projekte/mac-minimalansicht-belege/BEENDEN-X86-FIX-2026-10-01.md):

  src/common.rs load_custom_client() sucht die Datei auf macOS unter
      <Verzeichnis der ausfuehrbaren Datei>/../Resources/custom_.txt
  also  <App>.app/Contents/Resources/custom_.txt

  Der Ablauf legte sie aber nach
      <App>.app/Contents/MacOS/custom_.txt

  Falscher Ordner, und zwar seit jeher. Auf Windows faellt das nicht auf,
  weil es dort kein "../Resources" gibt -- die Datei liegt dort direkt
  neben der EXE und wird gefunden. Das ist die Ursache von
  bryangerlach/rdgen Issue #278 ("macOS wertet custom_.txt nicht aus").

Dieses Skript laeuft NACH allowCustom.py (das custom.txt -> custom_.txt
umbenennt) und VOR dem Bau. Es liest den tatsaechlichen Suchpfad aus der
Funktion heraus und schreibt ihn nach $GITHUB_ENV, damit der Einbett-
Schritt ihn benutzt statt ihn zu raten.

Harter Abbruch bei jeder Abweichung. Ein gruener Bau mit einer Datei am
falschen Ort ist genau der Fehler, der hier behoben wird.
"""

import os
import re
import sys

COMMON_RS = os.environ.get("COMMON_RS", "./src/common.rs")


def abbruch(msg):
    print("FEHLER (MACCUSTOMPFAD): %s" % msg, file=sys.stderr)
    sys.exit(1)


def funktionsrumpf(src, name):
    """Rumpf von `pub fn <name>(` bis zur schliessenden Klammer auf
    Spalte 0. Reicht fuer diese Datei; eine echte Rust-Zerlegung waere
    hier unverhaeltnismaessig."""
    m = re.search(r"^pub fn %s\s*\(" % re.escape(name), src, re.M)
    if not m:
        abbruch("Funktion %s() nicht in %s gefunden." % (name, COMMON_RS))
    rest = src[m.start():]
    ende = re.search(r"^\}", rest[1:], re.M)
    if not ende:
        abbruch("Ende von %s() nicht gefunden." % name)
    return rest[: ende.end() + 1]


def main():
    if not os.path.exists(COMMON_RS):
        abbruch("%s existiert nicht. Falsches Arbeitsverzeichnis?" % COMMON_RS)
    src = open(COMMON_RS, "r", encoding="utf-8").read()
    rumpf = funktionsrumpf(src, "load_custom_client")

    # Nur der Release-Zweig zaehlt. Der #[cfg(debug_assertions)]-Zweig am
    # Anfang liest "./custom_.txt" relativ zum Arbeitsverzeichnis und ist
    # fuer ein ausgeliefertes Buendel ohne Bedeutung.
    dbg = rumpf.find("#[cfg(debug_assertions)]")
    if dbg != -1:
        # bis zum Ende des debug-Blocks ueberspringen: der Release-Teil
        # beginnt bei "let Some(path) = std::env::current_exe()"
        pos = rumpf.find("current_exe")
        if pos == -1:
            abbruch("Der Release-Zweig von load_custom_client() fehlt.")
        rumpf = rumpf[pos:]

    joins = re.findall(r'path\.join\(\s*"([^"]+)"\s*\)', rumpf)
    if not joins:
        abbruch(
            "In load_custom_client() wurde kein path.join(\"...\") gefunden. "
            "Der Quelltext hat sich geaendert -- der Ablageort muss neu "
            "bestimmt werden, bevor hier weitergebaut wird."
        )

    macos_relativ = "../Resources" in joins
    dateiname = joins[-1]

    if not dateiname.endswith(".txt"):
        abbruch("Letztes path.join() ist kein Dateiname: %r" % dateiname)
    if not macos_relativ:
        abbruch(
            "load_custom_client() enthaelt kein path.join(\"../Resources\") "
            "mehr. Auf macOS liegt die ausfuehrbare Datei in "
            "Contents/MacOS; ohne diesen Sprung waere der Ablageort ein "
            "anderer. Gefundene Joins: %r" % (joins,)
        )

    # Contents/MacOS/../Resources/<datei>  ->  Contents/Resources/<datei>
    ziel = "Contents/Resources/%s" % dateiname

    print("MACCUSTOMPFAD: load_custom_client() sucht %r" % ("/".join(joins),))
    print("MACCUSTOMPFAD: Ablageort im Buendel = %s" % ziel)

    ausgabe = os.environ.get("GITHUB_ENV")
    if ausgabe:
        with open(ausgabe, "a", encoding="utf-8") as f:
            f.write("CUSTOM_BUNDLE_PATH=%s\n" % ziel)
            f.write("CUSTOM_FILE_NAME=%s\n" % dateiname)
    else:
        print("CUSTOM_BUNDLE_PATH=%s" % ziel)


if __name__ == "__main__":
    main()
