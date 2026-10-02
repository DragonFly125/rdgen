#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KEININSTALL 2026-10-02 -- eine Soforthilfe-Sitzung fragt nie nach einer
Installation.

DER BEFUND
----------
Masters Foto des ersten echten Kundenbaus (IT.EckSe GmbH, macOS, aus
/Applications gestartet) zeigt im Soforthilfe-Fenster ein pinkes Band:

    "Um mit System zu starten, muss der Systemdienst installiert sein."
    [Installieren]

Seine Ansage dazu: weder soll installiert werden, noch soll ueberhaupt
danach gefragt werden. Fuer eine EINGEHENDE, einmalige Hilfesitzung
(conn-type=incoming) ist eine Dauerinstallation des LaunchDaemon fachlich
falsch -- sie hinterlaesst auf dem Kundenrechner genau das, was die
Soforthilfe bewusst nicht hinterlaesst.

WO ES HERKOMMT -- GELESEN, NICHT VERMUTET
-----------------------------------------
flutter/lib/desktop/pages/desktop_home_page.dart, buildHelpCards(),
Z. 499-506 (rustdesk 1.4.9, Tag 6c57829):

    } else if (!isOutgoingOnly &&
        !svcStopped.value &&
        bind.mainIsInstalled() &&
        !bind.mainIsInstalledDaemon(prompt: false)) {
      return buildInstallCard("", "install_daemon_tip", "Install", () async {
        bind.mainIsInstalledDaemon(prompt: true);
      });
    }

Der Zweig kennt einen isOutgoingOnly-Vorbehalt, aber KEINEN fuer
isIncomingOnly -- upstream denkt hier an den Dauerclient, nicht an eine
Soforthilfe.

WIRD AUCH OHNE KLICK INSTALLIERT? NEIN -- VOLLSTAENDIG AUFGEZAEHLT
-------------------------------------------------------------------
  * mainIsInstalledDaemon kommt in flutter/lib/ an genau drei Stellen
    vor: Z. 502 (prompt:false, reines Lesen), Z. 504 (prompt:true, der
    Vorgang), und web/bridge.dart (UnimplementedError, nicht gebaut).
  * src/platform/macos.rs is_installed_daemon(prompt):
      prompt=false -> prueft nur, ob die beiden plist-Dateien unter
                      /Library/LaunchDaemons bzw. /Library/LaunchAgents
                      existieren. Keine Nebenwirkung.
      prompt=true  -> std::thread::spawn + osascript install.scpt, also
                      der Installationsvorgang mit Administrator-Abfrage.
  * install_service() (macos.rs Z. 182) gibt auf macOS NUR
    is_installed_daemon(false) zurueck, installiert also nichts. Seine
    Aufrufer: ui_interface.rs Z. 439 (liegt in einem cfg-Block fuer
    windows/linux, auf macOS nicht uebersetzt) und core_main.rs Z. 382
    (nur beim Startparameter --install-service).

=> Der Knopf ist der einzige Ausloeser. Wer die Karte verhindert,
   verhindert den Vorgang. Der Rueckruf wird hier trotzdem zusaetzlich
   abgeriegelt -- toter Code, aber ein Netz, falls eine kuenftige Fassung
   die Karte an anderer Stelle baut.

DMG-START GEGEN /Applications-START
-----------------------------------
macos.rs Z. 804: is_installed() ist wahr, wenn der Pfad der
ausfuehrbaren Datei mit /Applications/<AppName>.app beginnt. Aus der DMG
gestartet (/Volumes/...) ist er falsch -- deshalb sah Master die Karte
dort nicht. Die neue Bedingung !bind.isIncomingOnly() steht VOR
mainIsInstalled() und liest allein conn-type aus der eingebrannten
Konfiguration. Sie wirkt damit unabhaengig vom Startort, in beiden
Faellen.

VERHAELTNIS ZU DEN BESTEHENDEN PATCHES
--------------------------------------
beendenKnopfImmer.py (0007) umhuellt buildHelpCards und laesst den
Daemon-Zweig unberuehrt. gefuehrteBerechtigung.py (0006) ersetzt die drei
Berechtigungskarten und endet seinen Ersatz exakt auf der Zeile
"} else if (!isOutgoingOnly &&", die es wortgleich wieder ausgibt -- der
Daemon-Block dahinter bleibt Byte fuer Byte erhalten.

Dieses Skript laeuft deshalb NACH beiden und arbeitet auf dem Stand, den
sie hinterlassen:
  * Anker 1 ist der Daemon-Zweig (von beiden unberuehrt).
  * Anker 2 ist die hide-help-cards-Bedingung in buildInstallCard, die
    gefuehrteBerechtigung.py bereits um "&& !immerAnzeigen" verlaengert
    hat. Sie wird NICHT umgeschrieben; es wird eine eigene, vorgelagerte
    Abfrage davorgesetzt. immerAnzeigen und die Entscheidung von 0006/0007
    bleiben damit unveraendert gueltig.

WAS DER PATCH TUT
-----------------
1. Der Daemon-Zweig bekommt !bind.isIncomingOnly() als ERSTE Bedingung.
   Dart wertet && von links aus und kurzschliesst -- bei einer
   eingehenden Sitzung wird mainIsInstalled()/mainIsInstalledDaemon() gar
   nicht mehr aufgerufen, die Karte nicht gebaut, der Zweig faellt durch.
2. Der Rueckruf des Knopfes kehrt bei einer eingehenden Sitzung sofort
   zurueck, ohne prompt:true. Zweites Netz.
3. buildInstallCard gibt fuer content == 'install_daemon_tip' bei einer
   eingehenden Sitzung ein leeres SizedBox() zurueck -- VOR der
   hide-help-cards-Pruefung, deren upstream-Ausnahme fuer genau diesen
   Inhalt sonst dafuer sorgt, dass die Karte trotz hide-help-cards=Y
   sichtbar bliebe. Drittes Netz, rein optisch; der eigentliche Fix ist 1.

AUSDRUECKLICH NICHT ANGEFASST
-----------------------------
  * Der Windows-Zweig (Z. 463, "install_tip" / mainGotoInstall). Dort
    sperrt bereits isDisableInstallation() == Y, das in jeder
    Soforthilfe-Konfiguration dieses Hauses gesetzt ist.
  * Der Dauerclient (conn-type nicht 'incoming'). Dort bleibt das
    Verhalten unveraendert -- das ist der Fall, fuer den upstream die
    Karte gebaut hat.

HARTE ABNAHME
-------------
Jeder Anker muss genau einmal vorkommen, sonst Abbruch mit Exit 1. Nach
dem Schreiben wird von der Platte gegengelesen. Ein zweiter Lauf bricht
an der Marke ab.

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

MARKE = "KEININSTALL 2026-10-02"


def abbruch(text):
    sys.stderr.write("KEININSTALL FEHLER: %s\n" % text)
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
            % (pfad, wofuer, n, alt[:160])
        )
    return inhalt.replace(alt, neu, 1)


# --- Anker 1: der Daemon-Zweig in buildHelpCards/buildHelpCardsInhalt ------

ZWEIG_ALT = """      } else if (!isOutgoingOnly &&
          !svcStopped.value &&
          bind.mainIsInstalled() &&
          !bind.mainIsInstalledDaemon(prompt: false)) {
        return buildInstallCard("", "install_daemon_tip", "Install", () async {
          bind.mainIsInstalledDaemon(prompt: true);
        });
      }
"""

ZWEIG_NEU = """      } else if (!bind.isIncomingOnly() &&
          !isOutgoingOnly &&
          !svcStopped.value &&
          bind.mainIsInstalled() &&
          !bind.mainIsInstalledDaemon(prompt: false)) {
        // ===== KEININSTALL 2026-10-02 =====
        // Diese Karte fordert zur Dauerinstallation des LaunchDaemon auf
        // ("Um mit System zu starten, muss der Systemdienst installiert
        // sein."). Fuer eine eingehende, einmalige Hilfesitzung ist das
        // fachlich falsch: sie soll auf dem Kundenrechner nichts
        // zuruecklassen.
        //
        // !bind.isIncomingOnly() steht ABSICHTLICH als erste Bedingung.
        // Dart kurzschliesst &&: bei conn-type=incoming werden
        // mainIsInstalled() und mainIsInstalledDaemon() gar nicht erst
        // aufgerufen, die Karte wird nicht gebaut, der Zweig faellt durch.
        //
        // Damit ist es keine optische Unterdrueckung: der
        // Installationsvorgang haengt allein am Rueckruf unten
        // (prompt: true -> osascript install.scpt), und der Rueckruf
        // entsteht nicht mehr. Der zweite Riegel darin ist das Netz.
        return buildInstallCard("", "install_daemon_tip", "Install", () async {
          // KEININSTALL 2026-10-02: zweiter Riegel. Unerreichbar, solange
          // die Bedingung oben steht -- und genau deshalb hier, falls sie
          // einmal nicht mehr steht.
          if (bind.isIncomingOnly()) {
            return;
          }
          bind.mainIsInstalledDaemon(prompt: true);
        });
      }
"""

# --- Anker 2: buildInstallCard, VOR der hide-help-cards-Pruefung -----------
# Stand nach gefuehrteBerechtigung.py (0006). Die Bedingung selbst wird
# nicht veraendert, nur etwas davorgesetzt.

KARTE_ALT = """      bool immerAnzeigen = false}) {
    if (bind.mainGetBuildinOption(key: kOptionHideHelpCards) == 'Y' &&
        content != 'install_daemon_tip' &&
        !immerAnzeigen) {
      return const SizedBox();
    }
"""

KARTE_NEU = """      bool immerAnzeigen = false}) {
    // ===== KEININSTALL 2026-10-02 -- drittes Netz =====
    // Die Zeile darunter nimmt 'install_daemon_tip' ausdruecklich von der
    // hide-help-cards-Unterdrueckung AUS (so steht es bei upstream). Fuer
    // eine eingehende Soforthilfe-Sitzung ist diese Ausnahme falsch
    // herum: sie wuerde die eine Karte sichtbar halten, die hier gerade
    // nicht gewollt ist.
    //
    // Deshalb vorgelagert, nicht in die Bedingung hineingeflochten:
    // immerAnzeigen (GEFUEHRTE BERECHTIGUNG 2026-10-02) und die
    // upstream-Ausnahme bleiben unveraendert gueltig. Rein optisch -- der
    // eigentliche Riegel sitzt in buildHelpCards.
    if (content == 'install_daemon_tip' && bind.isIncomingOnly()) {
      return const SizedBox();
    }
    if (bind.mainGetBuildinOption(key: kOptionHideHelpCards) == 'Y' &&
        content != 'install_daemon_tip' &&
        !immerAnzeigen) {
      return const SizedBox();
    }
"""


def main():
    pfad = DART_DATEI
    print("KEININSTALL 2026-10-02 -- Patch laeuft")
    print("  cwd = %s" % os.getcwd())
    s = lies(pfad)
    if MARKE in s:
        abbruch("%s traegt die Marke %r schon -- zweiter Lauf." % (pfad, MARKE))

    # Vorbedingung: der Stand von gefuehrteBerechtigung.py muss da sein.
    # Ohne ihn passt Anker 2 nicht, und ein stilles Ueberspringen waere
    # genau die Klasse Fehler, die dieses Haus nicht mehr haben will.
    if "bool immerAnzeigen = false}) {" not in s:
        abbruch(
            "%s: 'immerAnzeigen' fehlt. gefuehrteBerechtigung.py (0006) ist "
            "nicht gelaufen oder hat sich geaendert -- dieser Patch laeuft "
            "ABSICHTLICH danach." % pfad
        )

    s = ersetze(s, ZWEIG_ALT, ZWEIG_NEU, pfad, "Daemon-Zweig install_daemon_tip")
    s = ersetze(s, KARTE_ALT, KARTE_NEU, pfad, "buildInstallCard-Kopf")

    with io.open(pfad, "w", encoding="utf-8", newline="") as f:
        f.write(s)

    # --- Gegenlesen von der Platte -----------------------------------------
    p = lies(pfad)
    fehler = []

    if p.count(MARKE) != 3:
        fehler.append("Marke %r kommt %d mal vor, erwartet 3." % (MARKE, p.count(MARKE)))

    # Der Zweig muss den neuen Vorbehalt tragen ...
    if p.count("} else if (!bind.isIncomingOnly() &&\n          !isOutgoingOnly &&") != 1:
        fehler.append("der neue isIncomingOnly-Vorbehalt steht nicht genau einmal im Zweig.")
    # ... und zwar VOR mainIsInstalled(), sonst waere die Kurzschluss-
    # Wirkung weg und mainIsInstalledDaemon() wuerde weiter aufgerufen.
    i_vorbehalt = p.find("} else if (!bind.isIncomingOnly() &&")
    i_installed = p.find("bind.mainIsInstalled() &&")
    if i_vorbehalt < 0 or i_installed < 0 or i_vorbehalt > i_installed:
        fehler.append("der Vorbehalt steht nicht vor bind.mainIsInstalled().")

    # Der Installationsaufruf darf es genau einmal geben, und er muss
    # hinter dem Riegel liegen.
    if p.count("bind.mainIsInstalledDaemon(prompt: true);") != 1:
        fehler.append(
            "mainIsInstalledDaemon(prompt: true) kommt %d mal vor, erwartet 1."
            % p.count("bind.mainIsInstalledDaemon(prompt: true);")
        )
    i_riegel = p.find("          if (bind.isIncomingOnly()) {\n            return;\n          }\n")
    i_prompt = p.find("bind.mainIsInstalledDaemon(prompt: true);")
    if i_riegel < 0:
        fehler.append("der Riegel im Rueckruf fehlt.")
    elif i_riegel > i_prompt:
        fehler.append("der Riegel steht HINTER dem Installationsaufruf.")

    # Drittes Netz vorhanden und vor der hide-help-cards-Pruefung.
    i_netz = p.find("if (content == 'install_daemon_tip' && bind.isIncomingOnly()) {")
    i_hide = p.find("if (bind.mainGetBuildinOption(key: kOptionHideHelpCards) == 'Y' &&")
    if i_netz < 0:
        fehler.append("das dritte Netz in buildInstallCard fehlt.")
    elif i_hide < 0 or i_netz > i_hide:
        fehler.append("das dritte Netz steht nicht vor der hide-help-cards-Pruefung.")

    # Die Entscheidung von 0006/0007 darf nicht verlorengegangen sein.
    if "!immerAnzeigen) {" not in p:
        fehler.append("immerAnzeigen aus GEFUEHRTE BERECHTIGUNG ist verschwunden.")
    if p.count("content != 'install_daemon_tip' &&\n        !immerAnzeigen) {") != 1:
        fehler.append("die hide-help-cards-Bedingung aus 0006 steht nicht mehr genau einmal da.")

    if fehler:
        abbruch("%s: " % pfad + " | ".join(fehler))

    print("  desktop_home_page  OK (Daemon-Karte fuer conn-type=incoming gesperrt)")
    print("KEININSTALL -- fertig und gegengelesen")


if __name__ == "__main__":
    main()
