#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BUENDELKENNZEICHNER 2026-10-02 -- CFBundleIdentifier bleibt
com.carriez.rustdesk, obwohl der Ablauf ihn umschreiben will.

AM AUSGELIEFERTEN ERZEUGNIS GEMESSEN, NICHT GESCHLOSSEN
-------------------------------------------------------
Aus dem Kundenbau IT.EckSe GmbH vom 02.10.2026, 12:28 UTC+2,
it-eckse-gmbh-soforthilfe-x86_64.dmg
(SHA-256 b51d33f2752ef6e7...45808199), Contents/Info.plist mit
plistlib gelesen:

    CFBundleIdentifier        = 'com.carriez.rustdesk'
    CFBundleName              = 'IT.EckSe GmbH Soforthilfe'
    CFBundleExecutable        = 'IT.EckSe GmbH Soforthilfe'
    LSMinimumSystemVersion    = '10.14'

Der Name ist also angekommen, die Kennung nicht.

DIE URSACHE -- EIN sed, DER EINE ANFUEHRUNGSZEICHEN-FORM VERLANGT,
DIE DIE DATEI NICHT HAT
------------------------------------------------------------------
generator-macos.yml Z. 175:

    sed -i '' -e 's/PRODUCT_BUNDLE_IDENTIFIER = ".*"/...= "com.APPNAME.app"/' \\
        ./flutter/macos/Runner.xcodeproj/project.pbxproj

Das Muster verlangt = "..." MIT doppelten Anfuehrungszeichen.
In project.pbxproj steht aber (Z. 448, 593, 630 -- Profile, Debug,
Release des Ziels Runner):

    PRODUCT_BUNDLE_IDENTIFIER = com.carriez.rustdesk;

OHNE Anfuehrungszeichen, mit Semikolon. Das Muster trifft nie, der sed
ersetzt nichts, der Bau bleibt gruen.

Das ist woertlich dieselbe Fehlerklasse wie der urlLink-sed aus Patch
0005 (ersetzte rustdesk.com durch rustdesk.com) und wie die Funde vom
30.09. und 01.10.: eine Ersetzung, die nicht sehen kann, wonach sie
sucht, und die deshalb schweigend nichts tut.

WARUM Z. 160 NICHT GENUEGT -- UND DER BEWEIS STEHT IM ERZEUGNIS
---------------------------------------------------------------
Z. 160 schreibt AppInfo.xcconfig um, und dort trifft das Muster
(s|PRODUCT_BUNDLE_IDENTIFIER = .*|). Wirksam ist es trotzdem nicht:
Xcode gibt einer Einstellung, die IM ZIEL steht (project.pbxproj),
Vorrang vor derselben Einstellung aus einer xcconfig-Datei.

Das ist hier nicht Lehrbuchwissen, sondern am Erzeugnis abgelesen.
Die drei Konfigurationen des Ziels Runner (Z. 427 Profile, Z. 573 Debug,
Z. 603 Release -- alle drei mit baseConfigurationReference auf
AppInfo.xcconfig) verhalten sich bei den ZWEI Angaben verschieden:

  PRODUCT_NAME              steht in den Runner-Konfigurationen NICHT
                            -> kommt aus AppInfo.xcconfig
                            -> der sed dort trifft
                            -> ausgeliefert: CFBundleName = <appname>  RICHTIG

  PRODUCT_BUNDLE_IDENTIFIER steht in allen drei Runner-Konfigurationen
                            -> ueberschreibt AppInfo.xcconfig
                            -> der sed auf pbxproj trifft nicht (Anfuehrungs-
                               zeichen), der auf xcconfig ist wirkungslos
                            -> ausgeliefert: com.carriez.rustdesk     FALSCH

Zwei Angaben, derselbe Ablauf, dieselbe Datei -- eine kommt an, die
andere nicht. Genau dieser Unterschied zeigt, wo der Vorrang liegt.
(Die Zeilen mit PRODUCT_NAME = "$(TARGET_NAME)" bei Z. 456/639/647
gehoeren zum Ziel RunnerTests: keine Basis-Konfiguration, keine Kennung.)

Nebenbei erklaert das auch, warum der dritte Versuch -- Z. 156, direkt
auf Info.plist -- nicht greifen kann: dort steht
<string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>, also ein Platzhalter, den
Xcode erst beim Bauen einsetzt. Ausserdem stehen Schluessel und Wert auf
ZWEI Zeilen, und sed arbeitet zeilenweise -- das Muster
`<key>...</key>.*<string>.*</string>` kann eine zweizeilige Stelle nie
treffen. Drei Versuche, denselben Wert zu setzen; der einzige, der
wirken koennte, ist der auf pbxproj.

WARUM DAS MEHR IST ALS KOSMETIK
-------------------------------
Der Buendelkennzeichner ist die Kennung, an der macOS eine Anwendung
systemweit festmacht: LaunchServices, die Voreinstellungsdomaene und der
TCC-Eintrag (Bedienungshilfen, Bildschirmaufnahme) haengen daran.

Solange alle Kundenbauten com.carriez.rustdesk tragen, sind sie fuer
macOS NICHT UNTERSCHEIDBAR -- weder voneinander noch von einem
offiziellen RustDesk, das derselbe Anwender eventuell installiert hat.
Fuer den gefuehrten Freigabe-Ablauf (Patch 0006) ist das unmittelbar
relevant: er fuehrt den Anwender zu einem Listeneintrag, der nicht
eindeutig zu unserer App gehoert.

EHRLICHE GRENZE: dass zwei ad-hoc signierte Bauten sich einen
TCC-Eintrag tatsaechlich TEILEN, ist damit NICHT bewiesen. TCC wertet
neben der Kennung auch die Designated Requirement aus, und die ist bei
einer Ad-hoc-Signatur der cdhash, der je Uebersetzung verschieden ist.
Die Kennung gleichzuziehen ist richtig und notwendig; welches Verhalten
sich am Ende zeigt, entscheidet ein echter Mac.

ZUSAETZLICH: DER NAME WIRD GEPRUEFT
-----------------------------------
Ein Buendelkennzeichner darf laut Apple nur A-Z a-z 0-9 . und -
enthalten. Der IT.EckSe-Bau lief mit appname
"IT.EckSe GmbH Soforthilfe" -- zwei Leerzeichen und ein zusaetzlicher
Punkt. Daraus waere com.IT.EckSe GmbH Soforthilfe.app geworden: keine
gueltige Kennung.

Dieses Skript bricht deshalb ab, wenn appname Zeichen enthaelt, die in
einer Kennung nicht zulaessig sind. Mit dieser Pruefung waere der
IT.EckSe-Bau ROT geworden, statt ein Buendel mit Leerzeichen im
Programmnamen auszuliefern -- dieselbe Absicherung, die Patch 0005 fuer
den Anzeigenamen eingefuehrt hat, hier fuer die Kennung.

Umgebungsvariablen:
  APPNAME      Pflicht. Der appname des Bauauftrags.
  PBX_DATEI    flutter/macos/Runner.xcodeproj/project.pbxproj
  XCCONFIG     flutter/macos/Runner/Configs/AppInfo.xcconfig
"""

import io
import os
import re
import sys

PBX_DATEI = os.environ.get(
    "PBX_DATEI", os.path.join("flutter", "macos", "Runner.xcodeproj", "project.pbxproj")
)
XCCONFIG = os.environ.get(
    "XCCONFIG", os.path.join("flutter", "macos", "Runner", "Configs", "AppInfo.xcconfig")
)

# Apple: nur A-Z a-z 0-9 Bindestrich und Punkt.
ERLAUBT = re.compile(r"^[A-Za-z0-9.-]+$")


def abbruch(text):
    sys.stderr.write("BUENDELKENNZEICHNER FEHLER: %s\n" % text)
    sys.exit(1)


def lies(pfad):
    if not os.path.isfile(pfad):
        abbruch("Datei nicht gefunden: %s (cwd=%s)" % (pfad, os.getcwd()))
    with io.open(pfad, "r", encoding="utf-8") as f:
        return f.read()


def schreib(pfad, inhalt):
    with io.open(pfad, "w", encoding="utf-8", newline="") as f:
        f.write(inhalt)


def main():
    appname = os.environ.get("APPNAME", "").strip()
    print("BUENDELKENNZEICHNER 2026-10-02 -- Patch laeuft")
    print("  cwd = %s" % os.getcwd())

    if not appname:
        abbruch("APPNAME ist nicht gesetzt. Ohne den Namen keine Kennung.")
    if not ERLAUBT.match(appname):
        abbruch(
            "appname %r enthaelt Zeichen, die in einem Buendelkennzeichner\n"
            "  nicht zulaessig sind (erlaubt: A-Z a-z 0-9 . -).\n"
            "  Genau daran ist der IT.EckSe-Bau vom 02.10. gescheitert.\n"
            "  Der im Haus dokumentierte Wert ist IT-Labuhn-Soforthilfe." % appname
        )
    if appname.startswith("-") or appname.endswith("-"):
        abbruch("appname %r faengt mit - an oder endet damit." % appname)

    kennung = "com.%s.app" % appname
    print("  appname  = %s" % appname)
    print("  Kennung  = %s" % kennung)

    # --- project.pbxproj: ALLE Vorkommen, mit und ohne Anfuehrungszeichen ---
    pfad = PBX_DATEI
    s = lies(pfad)
    # Nicht gegen eine Kennung pruefen, sondern gegen das Feld: der Patch
    # muss auch dann abbrechen, wenn upstream die Kennung mal aendert.
    muster = re.compile(r'PRODUCT_BUNDLE_IDENTIFIER = (?:"[^"\n]*"|[^;\n]*);')
    treffer = muster.findall(s)
    if not treffer:
        abbruch(
            "%s: kein einziges PRODUCT_BUNDLE_IDENTIFIER-Feld gefunden.\n"
            "  Upstream hat die Datei umgebaut -- hier wird nicht geraten." % pfad
        )
    # Im Stand 1.4.9 sind es genau drei (Profile, Debug, Release des Ziels
    # Runner). Weicht die Zahl ab, ist das eine Aenderung, die ein Mensch
    # ansehen muss, und kein Fall fuer eine stille Ersetzung.
    if len(treffer) != 3:
        abbruch(
            "%s: %d PRODUCT_BUNDLE_IDENTIFIER-Felder gefunden, erwartet 3.\n"
            "  Gefunden: %r" % (pfad, len(treffer), treffer)
        )
    s_neu = muster.sub("PRODUCT_BUNDLE_IDENTIFIER = %s;" % kennung, s)
    if s_neu == s:
        abbruch("%s: Ersetzung hat nichts geaendert." % pfad)
    schreib(pfad, s_neu)

    # --- AppInfo.xcconfig: wirkt nicht, wird aber mitgezogen --------------
    # Zwei Staende derselben Angabe, die auseinanderlaufen, sind die
    # naechste Fehlerquelle. Deshalb beide gleich.
    pfad2 = XCCONFIG
    s2 = lies(pfad2)
    muster2 = re.compile(r"^PRODUCT_BUNDLE_IDENTIFIER = .*$", re.M)
    if len(muster2.findall(s2)) != 1:
        abbruch("%s: PRODUCT_BUNDLE_IDENTIFIER nicht genau einmal vorhanden." % pfad2)
    s2_neu = muster2.sub("PRODUCT_BUNDLE_IDENTIFIER = %s" % kennung, s2)
    schreib(pfad2, s2_neu)

    # --- Gegenlesen von der Platte ----------------------------------------
    p = lies(pfad)
    if p.count("PRODUCT_BUNDLE_IDENTIFIER = %s;" % kennung) != 3:
        abbruch(
            "%s: neue Kennung steht %d mal drin, erwartet 3."
            % (pfad, p.count("PRODUCT_BUNDLE_IDENTIFIER = %s;" % kennung))
        )
    if "com.carriez" in p:
        abbruch("%s: com.carriez steht noch drin." % pfad)
    p2 = lies(pfad2)
    if "PRODUCT_BUNDLE_IDENTIFIER = %s" % kennung not in p2:
        abbruch("%s: neue Kennung fehlt." % pfad2)
    if "com.carriez" in p2:
        abbruch("%s: com.carriez steht noch drin." % pfad2)

    print("  project.pbxproj    OK (3 Felder, ohne Anfuehrungszeichen erfasst)")
    print("  AppInfo.xcconfig   OK (gleichgezogen)")
    print("BUENDELKENNZEICHNER -- fertig und gegengelesen")


if __name__ == "__main__":
    main()
