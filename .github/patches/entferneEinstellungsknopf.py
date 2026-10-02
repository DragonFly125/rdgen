#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DREIPUNKTEMENUE 2026-10-02 -- das Drei-Punkte-Symbol (:) neben der ID
entfernen.

WARUM DAS EIN QUELLTEXT-PATCH IST UND KEIN KONFIGURATIONSSCHLUESSEL
------------------------------------------------------------------
In RustDesk 1.4.9 (und in 1.3.9 / 1.4.0 / 1.4.5 / 1.4.8, alle geprueft)
steht der Aufruf

    buildPopupMenu(context)

in flutter/lib/desktop/pages/desktop_home_page.dart, Funktion
buildIDBoard(), **ohne jede Bedingung**. Es gibt keinen hide-*-Schluessel,
kein isIncomingOnly(), kein isDisableSettings(), das dieses Symbol
verbergen koennte. Die zwei Schluessel, die man dafuer gehalten hat
(hide-general-settings, hide-group-panel), kommen im gesamten Quelltext
-- Rust wie Dart -- ueberhaupt nicht vor; sie sind wirkungslos.

Der Windows-Zweig dieses Hauses loest es seit dem 2026-09-22 genau so:
bau-lokal.ps1, Schalter -KeinEinstellungsknopf (Vorgabewert $true),
ersetzt dieselbe Aufrufstelle durch SizedBox.shrink(). Das Erzeugnis ist
5 Zyklen lang abgenommen worden (FAMILIE-NETZWERKSPERRE-progress.md) und
ist die Referenz, die Master kennt. Dieses Skript zieht den macOS-Zweig
auf denselben Stand -- gleiche Datei, gleiche Zeichenkette, gleicher
Ersatz.

HARTE ABNAHME, KEIN "|| true"
-----------------------------
Ein gruener Bau mit wirkungslosem Erzeugnis ist genau die Fehlerklasse,
die dieses Haus hier schon zweimal getroffen hat. Deshalb:
  * genau EINE Aufrufstelle wird erwartet, sonst Abbruch,
  * die Funktionsdefinition muss vorhanden sein, sonst Abbruch
    (sie beweist, dass wir die richtige Datei vor uns haben),
  * die Aufrufstelle muss zwischen buildIDBoard() und der Definition
    liegen, sonst Abbruch,
  * nach dem Schreiben wird die Datei ERNEUT GELESEN und das Ergebnis
    geprueft -- der Rueckgabewert einer Ersetzung sagt nichts darueber,
    ob das Ergebnis stimmt,
  * ein zweiter Lauf auf derselben Datei bricht ab (nicht wiederholbar).

Umgebungsvariablen (alle optional):
  DART_HOME_PAGE   Pfad zur desktop_home_page.dart
                   (Vorgabe: flutter/lib/desktop/pages/desktop_home_page.dart)
"""

import os
import sys

VORGABE_DATEI = os.path.join(
    "flutter", "lib", "desktop", "pages", "desktop_home_page.dart"
)

AUFRUF = "buildPopupMenu(context)"
ERSATZ = "SizedBox.shrink()"
DEFINITION = "Widget buildPopupMenu(BuildContext context)"
UMGEBENDE_FUNKTION = "buildIDBoard(BuildContext context)"


def abbruch(text):
    print("FEHLER: %s" % text, file=sys.stderr)
    print(
        "Der Bau wird abgebrochen. Ein Erzeugnis, in dem das "
        "Drei-Punkte-Menue stehen bleibt, waere von einem richtigen "
        "nicht zu unterscheiden -- genau deshalb gibt es hier kein "
        "'|| true'.",
        file=sys.stderr,
    )
    sys.exit(1)


def main():
    pfad = os.environ.get("DART_HOME_PAGE") or VORGABE_DATEI

    if not os.path.isfile(pfad):
        abbruch(
            "Datei nicht gefunden: %s\n"
            "Laeuft dieser Schritt wirklich im Wurzelverzeichnis des "
            "rustdesk-Checkouts?" % pfad
        )

    with open(pfad, "r", encoding="utf-8") as f:
        inhalt = f.read()

    # --- Vorbedingungen, bevor irgendetwas geschrieben wird ------------
    anzahl_aufruf = inhalt.count(AUFRUF)
    anzahl_def = inhalt.count(DEFINITION)
    anzahl_idboard = inhalt.count(UMGEBENDE_FUNKTION)

    if anzahl_def != 1:
        abbruch(
            "Die Funktionsdefinition '%s' kommt %d-mal vor, erwartet 1.\n"
            "Entweder ist das die falsche Datei, oder RustDesk hat den "
            "Aufbau geaendert. In beiden Faellen darf hier nicht blind "
            "ersetzt werden." % (DEFINITION, anzahl_def)
        )

    if anzahl_idboard != 1:
        abbruch(
            "'%s' kommt %d-mal vor, erwartet 1. Der Aufbau der ID-Karte "
            "hat sich geaendert." % (UMGEBENDE_FUNKTION, anzahl_idboard)
        )

    if anzahl_aufruf == 0:
        abbruch(
            "Die Aufrufstelle '%s' steht nicht (mehr) in der Datei.\n"
            "Zwei moegliche Ursachen, beide muessen gesehen werden:\n"
            "  (1) dieser Schritt ist bereits gelaufen -- er ist "
            "absichtlich NICHT wiederholbar;\n"
            "  (2) RustDesk hat die Aufrufstelle umbenannt oder bereits "
            "selbst mit einer Bedingung versehen. Dann gehoert dieser "
            "Patch neu bewertet, nicht uebersprungen." % AUFRUF
        )

    if anzahl_aufruf != 1:
        abbruch(
            "Die Aufrufstelle '%s' kommt %d-mal vor, erwartet genau 1. "
            "Eine Mehrfachersetzung waere eine Vermutung, keine "
            "Aenderung." % (AUFRUF, anzahl_aufruf)
        )

    pos_idboard = inhalt.index(UMGEBENDE_FUNKTION)
    pos_aufruf = inhalt.index(AUFRUF)
    pos_def = inhalt.index(DEFINITION)

    if not (pos_idboard < pos_aufruf < pos_def):
        abbruch(
            "Die Aufrufstelle liegt nicht zwischen buildIDBoard() und der "
            "Definition von buildPopupMenu(). Der Aufbau der Datei ist "
            "anders als angenommen -- hier wird nichts geraten.\n"
            "Fundstellen (Byteversatz): buildIDBoard=%d, Aufruf=%d, "
            "Definition=%d" % (pos_idboard, pos_aufruf, pos_def)
        )

    zeile_vorher = inhalt[:pos_aufruf].count("\n") + 1

    # --- Ersetzen ------------------------------------------------------
    neu = inhalt.replace(AUFRUF, ERSATZ, 1)

    if neu == inhalt:
        abbruch("Die Ersetzung hat die Datei nicht veraendert.")

    with open(pfad, "w", encoding="utf-8") as f:
        f.write(neu)

    # --- Gegenprobe AM ERGEBNIS, nicht am Rueckgabewert ---------------
    with open(pfad, "r", encoding="utf-8") as f:
        kontrolle = f.read()

    fehler = []
    if kontrolle.count(AUFRUF) != 0:
        fehler.append(
            "'%s' steht nach dem Schreiben immer noch in der Datei" % AUFRUF
        )
    if kontrolle.count(DEFINITION) != 1:
        fehler.append(
            "die Funktionsdefinition ist beim Schreiben verlorengegangen "
            "(%d-mal statt 1)" % kontrolle.count(DEFINITION)
        )

    # Der Ersatz muss GENAU an der Stelle stehen, an der der Aufruf stand:
    # in der Zeile, die vorher die Aufrufstelle trug.
    zeilen = kontrolle.splitlines()
    if zeile_vorher - 1 >= len(zeilen):
        fehler.append("die erwartete Zeile %d existiert nicht mehr" % zeile_vorher)
    elif ERSATZ not in zeilen[zeile_vorher - 1]:
        fehler.append(
            "in Zeile %d steht nicht '%s', sondern: %r"
            % (zeile_vorher, ERSATZ, zeilen[zeile_vorher - 1].strip())
        )

    # Die Zeilenzahl darf sich nicht geaendert haben -- eine einzeilige
    # Ersetzung, die Zeilen hinzufuegt oder entfernt, hat etwas anderes
    # getroffen als gedacht.
    if len(kontrolle.splitlines()) != len(inhalt.splitlines()):
        fehler.append(
            "die Zeilenzahl hat sich geaendert (%d -> %d)"
            % (len(inhalt.splitlines()), len(kontrolle.splitlines()))
        )

    if fehler:
        abbruch("Gegenprobe am Ergebnis fehlgeschlagen:\n  - " + "\n  - ".join(fehler))

    print("Drei-Punkte-Menue neben der ID entfernt:")
    print("  Datei : %s" % pfad)
    print("  Zeile : %d" % zeile_vorher)
    print("  vorher: %s" % AUFRUF)
    print("  jetzt : %s" % ERSATZ)
    print(
        "  Gegenprobe am Ergebnis bestanden "
        "(0 Aufrufstellen, Definition unveraendert, Zeilenzahl gleich)."
    )
    print(
        "HINWEIS: Das Zahnrad in der Registerleiste bleibt davon "
        "unberuehrt. Es haengt an isIncomingOnly()/isDisableSettings() "
        "(desktop_tab_page.dart) und ist in der Soforthilfe ohnehin "
        "ausgeblendet, in der Dauerinstallation weiterhin erreichbar -- "
        "genau wie im Windows-Erzeugnis vom 2026-09-23."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
