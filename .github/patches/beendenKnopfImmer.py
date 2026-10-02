#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BEENDENKNOPF 2026-10-02 -- der "Beenden"-Knopf fehlt auf macOS.

DIE KETTE, GELESEN UND NICHT VERMUTET
-------------------------------------
flutter/lib/desktop/pages/desktop_home_page.dart, buildHelpCards():

  Z. 463  if (isWindows && !bind.isDisableInstallation()) { ... }
  Z. 479  } else if (isMacOS) { ... }
  Z. 557  if (bind.isIncomingOnly()) { return Align(... Quit ...); }

Der Beenden-Knopf steht GANZ AM ENDE der Funktion. Er wird nur erreicht,
wenn vorher kein Zweig mit return herausgesprungen ist.

Auf Windows ist das der Normalfall: disable-installation=Y laesst den
ganzen Windows-Zweig leer durchlaufen, und der Ablauf faellt bis Z. 557
durch. Der Knopf erscheint -- so kennt Master es.

Auf macOS ist Z. 463 IMMER falsch. Der Ablauf geht in den macOS-Zweig, und
der kehrt mit einer Berechtigungskarte zurueck, solange eine der drei
TCC-Freigaben fehlt. Auf einem frischen Mac fehlen sie alle. Der Knopf
wird deshalb NIE gezeichnet.

Verschaerfend, und das ist der groessere Mangel: buildInstallCard() gibt
bei hide-help-cards=Y ein leeres SizedBox() zurueck (Z. 583-585), und
genau dieser Schluessel steht in der eingebrannten Konfiguration dieses
Kundenbaus (override-settings.hide-help-cards = 'Y', aus der
ausgelieferten custom_.txt gelesen). Die Funktion kehrt also mit einem
UNSICHTBAREN Widget zurueck.

Ergebnis auf einem frischen Kunden-Mac: kein Hinweis, dass Freigaben
fehlen -- und kein Beenden-Knopf. Der Helfende sieht ein schwarzes Bild,
der Kunde findet keinen Weg aus der App.

WEG C -- WARUM DIESER UND NICHT DER OFFENSICHTLICHE
---------------------------------------------------
Der naheliegende Eingriff waere, jedes `return` im macOS-Zweig zu einem
gesammelten Widget umzubauen. Das ist viel Flaeche in einer Funktion, an
der im selben Zug auch der gefuehrte Freigabe-Ablauf arbeitet
(gefuehrteBerechtigung.py) -- zwei Patches auf denselben Zeilen sind ein
Konflikt, der sich erst im Ablauf zeigt.

Stattdessen wird die Funktion UMHUELLT:

  buildHelpCards(url)        -- neu, klein: Inneres + Beenden-Knopf
  buildHelpCardsInhalt(url)  -- der bisherige Rumpf, unveraendert

Damit ist der Knopf unabhaengig davon, welcher Zweig im Inneren
zurueckkehrt, und der Patch beruehrt keine Zeile, an der
gefuehrteBerechtigung.py arbeitet. Die beiden Patches sind in jeder
Reihenfolge anwendbar.

Der bisherige Beenden-Block am Ende des Rumpfes wird entfernt -- sonst
stuenden zwei Knoepfe da.

Die Ausnahme von hide-help-cards fuer die Berechtigungskarten gehoert
NICHT in dieses Skript: sie steckt bereits in gefuehrteBerechtigung.py
(Schalter immerAnzeigen an buildInstallCard). Hier waere sie eine zweite
Stelle fuer dieselbe Entscheidung.

HARTE ABNAHME
-------------
Anker muessen genau einmal vorkommen, sonst Abbruch. Nach dem Schreiben
wird gegengelesen. Ein zweiter Lauf bricht ab.

Umgebungsvariablen:
  DART_DATEI   flutter/lib/desktop/pages/desktop_home_page.dart
"""

import io
import os
import sys

DART_DATEI = os.environ.get(
    "DART_DATEI",
    os.path.join("flutter", "lib", "desktop", "pages", "desktop_home_page.dart"),
)

MARKE = "BEENDENKNOPF 2026-10-02"


def abbruch(text):
    sys.stderr.write("BEENDENKNOPF FEHLER: %s\n" % text)
    sys.exit(1)


def lies(pfad):
    if not os.path.isfile(pfad):
        abbruch("Datei nicht gefunden: %s (cwd=%s)" % (pfad, os.getcwd()))
    with io.open(pfad, "r", encoding="utf-8") as f:
        return f.read()


def ersetze(inhalt, alt, neu, pfad, wofuer):
    n = inhalt.count(alt)
    if n != 1:
        abbruch(
            "%s: Anker fuer %s kommt %d mal vor, erwartet genau 1.\n  Anker: %r"
            % (pfad, wofuer, n, alt[:140])
        )
    return inhalt.replace(alt, neu, 1)


# --- 1) Umhuellung: aus buildHelpCards wird buildHelpCardsInhalt ------------

KOPF_ALT = "  Widget buildHelpCards(String updateUrl) {\n"

KOPF_NEU = """  // ===== BEENDENKNOPF 2026-10-02 =====
  // Umhuellung. Der Beenden-Knopf haengt nicht mehr davon ab, ob der Rumpf
  // vorher mit einer Karte zurueckkehrt.
  //
  // Vorher stand er als letzte Anweisung IM Rumpf und war damit auf jedem
  // Mac unerreichbar, auf dem noch eine TCC-Freigabe fehlte: der
  // macOS-Zweig kehrt dann mit einer Berechtigungskarte zurueck -- bei
  // hide-help-cards=Y sogar mit einem unsichtbaren SizedBox(), also ohne
  // dass der Anwender ueberhaupt sieht, warum.
  //
  // Auf Windows aendert sich nichts: dort liess disable-installation=Y den
  // Rumpf schon vorher bis zum Ende durchlaufen. Der Knopf stand und steht.
  Widget buildHelpCards(String updateUrl) {
    final inneres = buildHelpCardsInhalt(updateUrl);
    if (!bind.isIncomingOnly()) {
      return inneres;
    }
    final beenden = Align(
      alignment: Alignment.centerRight,
      child: OutlinedButton(
        onPressed: () {
          SystemNavigator.pop(); // Close the application
          // https://github.com/flutter/flutter/issues/66631
          if (isWindows) {
            exit(0);
          }
        },
        child: Text(translate('Quit')),
      ),
    ).marginAll(14);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[inneres, beenden],
    );
  }

  Widget buildHelpCardsInhalt(String updateUrl) {
"""

# --- 2) Den alten Beenden-Block aus dem Rumpf nehmen -----------------------
# Sonst stuenden zwei Knoepfe da.

ALT_BLOCK_ALT = """    if (bind.isIncomingOnly()) {
      return Align(
        alignment: Alignment.centerRight,
        child: OutlinedButton(
          onPressed: () {
            SystemNavigator.pop(); // Close the application
            // https://github.com/flutter/flutter/issues/66631
            if (isWindows) {
              exit(0);
            }
          },
          child: Text(translate('Quit')),
        ),
      ).marginAll(14);
    }
    return Container();
  }
"""

ALT_BLOCK_NEU = """    // BEENDENKNOPF 2026-10-02: der Beenden-Knopf stand hier und war damit
    // unerreichbar, sobald ein Zweig darueber zurueckkehrte. Er sitzt jetzt
    // in der Umhuellung buildHelpCards() und wird immer gezeichnet.
    return Container();
  }
"""


def main():
    pfad = DART_DATEI
    print("BEENDENKNOPF 2026-10-02 -- Patch laeuft")
    print("  cwd = %s" % os.getcwd())
    s = lies(pfad)
    if MARKE in s:
        abbruch("%s traegt die Marke %r schon -- zweiter Lauf." % (pfad, MARKE))

    # Der Rumpf muss den Beenden-Block noch enthalten. Fehlt er, hat jemand
    # anderes die Funktion schon umgebaut, und diese Umhuellung waere
    # entweder doppelt oder wirkungslos.
    s = ersetze(s, KOPF_ALT, KOPF_NEU, pfad, "Funktionskopf buildHelpCards")
    s = ersetze(s, ALT_BLOCK_ALT, ALT_BLOCK_NEU, pfad, "alter Beenden-Block")

    with io.open(pfad, "w", encoding="utf-8", newline="") as f:
        f.write(s)

    # Gegenlesen von der Platte.
    p = lies(pfad)
    if p.count("Widget buildHelpCards(String updateUrl) {") != 1:
        abbruch("%s: buildHelpCards nicht genau einmal vorhanden." % pfad)
    if p.count("Widget buildHelpCardsInhalt(String updateUrl) {") != 1:
        abbruch("%s: buildHelpCardsInhalt nicht genau einmal vorhanden." % pfad)
    # Genau EIN Beenden-Knopf im ganzen Rumpf.
    if p.count("child: Text(translate('Quit')),") != 1:
        abbruch(
            "%s: Beenden-Knopf kommt %d mal vor, erwartet genau 1."
            % (pfad, p.count("child: Text(translate('Quit')),"))
        )
    if p.count("buildHelpCardsInhalt(updateUrl)") != 1:
        abbruch("%s: der Rumpf wird nicht genau einmal aufgerufen." % pfad)
    # Die Umhuellung muss VOR dem Rumpf stehen, sonst ruft sie sich selbst.
    if p.index("final inneres = buildHelpCardsInhalt(updateUrl);") > p.index(
        "Widget buildHelpCardsInhalt(String updateUrl) {"
    ):
        abbruch("%s: Umhuellung steht hinter dem Rumpf." % pfad)
    print("  desktop_home_page  OK (Beenden-Knopf aus dem Rumpf herausgezogen)")
    print("BEENDENKNOPF -- fertig und gegengelesen")


if __name__ == "__main__":
    main()
