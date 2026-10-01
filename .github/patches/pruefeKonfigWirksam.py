#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MACCUSTOMPFAD -- Abnahme AM ERZEUGNIS, nicht an der Absicht.

Am 2026-10-01 hat ein vollstaendig gruener macOS-Bau einen Client
ausgeliefert, in dem KEINE einzige der 15 Minimalansicht-Einstellungen
angekommen war -- auf x86_64, waehrend aarch64 aus derselben Quelle in
Ordnung war. Aufgefallen ist es erst am Geraet des Betreibers.

Belegt in projekte/mac-minimalansicht-belege/BEENDEN-X86-FIX-2026-10-01.md:
die eingebrannten Zeichenketten fehlen im x86_64-Erzeugnis vollstaendig,
obwohl der Einbrenn-Schritt seine eigene Gegenprobe an der QUELLE
bestanden hat. Eine Gegenprobe an der Quelle kann einen Verlust beim
Uebersetzen/Binden grundsaetzlich nicht sehen.

Dieser Schritt prueft deshalb das FERTIGE App-Buendel und fragt die
einzige Frage, auf die es ankommt:

    Traegt dieses Buendel die Kundenkonfiguration auf mindestens EINEM
    Weg, der zur Laufzeit wirklich gelesen wird?

Zwei Wege, beide werden gemessen:

  Weg 1 (offiziell, Laufzeit): die Datei an dem Ort, den
         load_custom_client() tatsaechlich durchsucht. Der Ort wird von
         pruefeKonfigPfad.py aus dem Quelltext abgeleitet und ueber
         CUSTOM_BUNDLE_PATH hereingereicht -- nicht hier abgeschrieben.

  Weg 2 (Guertel, Uebersetzungszeit): die von burnInSettings.py
         eingebrannten Zeichenketten, gemessen im ausgelieferten
         liblibrustdesk.dylib. Geprueft wird nur mit Markern, die im
         unveraenderten Quelltext NICHT vorkommen -- ein Schluessel, der
         ohnehin als OPTION_*-Konstante im Binaerstamm steht, beweist
         nichts.

Faellt genau ein Weg aus, ist das ein lautes WARN mit Zahlen. Fallen
BEIDE aus, bricht der Bau ab: dann ginge ein Client raus, der die volle
Standardoberflaeche zeigt.
"""

import base64
import json
import os
import sys

DYLIB = "Contents/Frameworks/liblibrustdesk.dylib"


def melde(zeilen):
    txt = "\n".join(zeilen)
    print(txt)
    pfad = os.environ.get("GITHUB_STEP_SUMMARY")
    if pfad:
        try:
            with open(pfad, "a", encoding="utf-8") as f:
                f.write(txt + "\n")
        except OSError:
            pass


def pruefe_laufzeitdatei(app, relpfad):
    """(ok, text)"""
    if not relpfad:
        return False, "CUSTOM_BUNDLE_PATH nicht gesetzt -- Weg 1 ungeprueft"
    p = os.path.join(app, relpfad)
    if not os.path.isfile(p):
        return False, "FEHLT: %s" % relpfad
    roh = open(p, "rb").read()
    if not roh.strip():
        return False, "leer: %s" % relpfad
    try:
        daten = json.loads(base64.b64decode(roh.strip()))
    except Exception as e:
        return False, "%s ist kein base64-JSON: %s" % (relpfad, e)
    if not isinstance(daten, dict) or not daten:
        return False, "%s enthaelt kein gefuelltes JSON-Objekt" % relpfad
    return True, "%s, %d B, %d Schluessel oberste Ebene" % (
        relpfad,
        len(roh),
        len(daten),
    )


def pruefe_einbrennung(app, markerdatei):
    """(ok, text)"""
    if not markerdatei or not os.path.isfile(markerdatei):
        return False, "keine Markerdatei -- Weg 2 ungeprueft"
    marker = [
        z.strip() for z in open(markerdatei, "r", encoding="utf-8") if z.strip()
    ]
    if not marker:
        return False, "Markerdatei ist leer -- Weg 2 ungeprueft"
    p = os.path.join(app, DYLIB)
    if not os.path.isfile(p):
        return False, "%s fehlt im Buendel" % DYLIB
    blob = open(p, "rb").read()
    treffer = {m: blob.count(m.encode("utf-8")) for m in marker}
    gefunden = sum(1 for n in treffer.values() if n > 0)
    text = ", ".join("%s=%d" % (m, n) for m, n in sorted(treffer.items()))
    return gefunden > 0, "%d/%d Marker im Dylib (%s)" % (
        gefunden,
        len(marker),
        text,
    )


def main():
    if len(sys.argv) < 2:
        print("Aufruf: pruefeKonfigWirksam.py <App-Buendel>", file=sys.stderr)
        sys.exit(2)
    app = sys.argv[1]
    if not os.path.isdir(app):
        print("FEHLER: %s ist kein Verzeichnis." % app, file=sys.stderr)
        sys.exit(1)

    ok1, t1 = pruefe_laufzeitdatei(app, os.environ.get("CUSTOM_BUNDLE_PATH", ""))
    ok2, t2 = pruefe_einbrennung(app, os.environ.get("BURNIN_MARKER_FILE", ""))

    zeilen = [
        "Wirksamkeitspruefung der Kundenkonfiguration (%s):" % os.path.basename(app),
        "  Weg 1  Laufzeitdatei      %-4s  %s" % ("OK" if ok1 else "NEIN", t1),
        "  Weg 2  Einbrennung        %-4s  %s" % ("OK" if ok2 else "NEIN", t2),
    ]

    if ok1 and ok2:
        zeilen.append("ERGEBNIS: beide Wege tragen die Konfiguration.")
    elif ok1 or ok2:
        zeilen.append(
            "ERGEBNIS: WARN -- nur EIN Weg traegt die Konfiguration. Der "
            "Client ist richtig eingestellt, aber die zweite Sicherung "
            "fehlt. Gehoert angesehen, nicht ignoriert."
        )
    else:
        zeilen.append(
            "ERGEBNIS: ABBRUCH -- dieses Buendel traegt die "
            "Kundenkonfiguration auf KEINEM Weg. Ein solcher Client zeigt "
            "die volle Standardoberflaeche (keine Minimalansicht, keine "
            "Netzwerksperre) und darf nicht ausgeliefert werden."
        )
    melde(zeilen)
    sys.exit(0 if (ok1 or ok2) else 1)


if __name__ == "__main__":
    main()
