#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
burnInSettings.py -- brennt die RDGen-Clientkonfiguration zur
UEBERSETZUNGSZEIT in libs/hbb_common/src/config.rs ein.

WARUM ES DIESEN SCHRITT GIBT
----------------------------
Der macOS-Client wertet die Laufzeitdatei `custom_.txt` nachweislich
nicht aus (bryangerlach/rdgen Issue #278, offen seit 2026-08-06; vier
unabhaengige Melder, zwei gescheiterte Blindkorrekturen). Ergebnis: eine
Soforthilfe-App zeigt die volle Standardoberflaeche, und einer
Dauerinstallation fehlt die Netzwerksperre (`hide-network-settings`).

Dieses Haus hat denselben Laufzeitweg am 2026-09-23 fuer Windows bereits
verworfen und auf Einbrennen umgestellt (EINGEBRANNTE-KONFIG,
bau-lokal.ps1 Schritt 3c, 5 Abnahmezyklen). Dieser Schritt ist die
macOS-Entsprechung -- mit dem Unterschied, dass die Werte hier NICHT fest
eingetragen, sondern aus `env.custom` abgeleitet werden. Damit bleiben die
RDGen-Parameter die eine Quelle der Wahrheit; es entsteht keine zweite
Liste, die veraltet.

GRUNDSATZ
---------
Der Schritt bildet `src/common.rs::read_custom_client()` nach, statt eine
eigene Einordnung zu erfinden. Die vier KEYS_-Listen werden ZUR BAUZEIT
aus config.rs gelesen und die Konstantenbezeichner aufgeloest -- nicht
abgeschrieben. Eine abgeschriebene Liste veraltet lautlos; genau diese
Fehlerklasse hat den ganzen Vorgang ausgeloest.

Jeder Fehlschlag ist ein HARTER ABBRUCH (Rueckgabewert != 0). Kein
`|| true`, keine Warnung: ein gruener Bau mit wirkungslosem Erzeugnis ist
schlimmer als ein roter Bau.
"""

import base64
import json
import os
import re
import sys

# --- Speicher, die read_custom_client() befuellt -----------------------
STORES = [
    "DEFAULT_SETTINGS",
    "OVERWRITE_SETTINGS",
    "DEFAULT_DISPLAY_SETTINGS",
    "OVERWRITE_DISPLAY_SETTINGS",
    "DEFAULT_LOCAL_SETTINGS",
    "OVERWRITE_LOCAL_SETTINGS",
    "HARD_SETTINGS",
    "BUILTIN_SETTINGS",
]

# BEWUSST NICHT EINGEBRANNT (uebernommen aus bau-lokal.ps1 Schritt 3c):
# src/common.rs get_api_server_() nimmt einen gesetzten `api-server`-Wert
# VOR dem einkompilierten Vorgabewert. Der Gruppenpfad `/s/<package_key>`
# der Soforthilfe-Variante waere damit still ueberschrieben -- also genau
# die Gruppenzuordnung, die QUICKSUPPORT-PROGRUPPE hergestellt hat.
# Server, Schluessel und API-Server bleiben ausschliesslich bei den
# Konstanten, die der Schritt "allow custom.txt" per sed setzt.
# Eine Quelle der Wahrheit, nicht zwei.
DEFAULT_EXCLUDE = ("api-server", "custom-rendezvous-server")


def abbruch(msg):
    print("FEHLER: %s" % msg, file=sys.stderr)
    print(
        "ABBRUCH. Ohne diesen Schritt traegt das Erzeugnis KEINE "
        "Clientkonfiguration: die Soforthilfe zeigt die volle "
        "Standardoberflaeche, der Dauerinstallation fehlt die "
        "Netzwerksperre. Ein gruener Bau waere hier schaedlicher als "
        "ein roter.",
        file=sys.stderr,
    )
    sys.exit(1)


def rust_str(s):
    """Rust-Zeichenkettenliteral. Escapen statt ablehnen -- ein
    Gruppen-/Anzeigename darf Leerzeichen und Umlaute enthalten.
    Steuerzeichen werden abgelehnt, die haetten in config.rs nichts
    zu suchen und deuten auf eine kaputte Uebertragung hin."""
    for ch in s:
        if ord(ch) < 0x20 or ord(ch) == 0x7F:
            abbruch(
                "Steuerzeichen (0x%02X) in einem Konfigurationswert. "
                "Das deutet auf eine beschaedigte Uebertragung hin." % ord(ch)
            )
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')


def literal(pairs):
    if not pairs:
        return "Default::default()"
    teile = ", ".join(
        "(%s.to_owned(), %s.to_owned())" % (rust_str(k), rust_str(v))
        for k, v in pairs.items()
    )
    return "RwLock::new(HashMap::from([%s]))" % teile


def ohne_kommentare(s):
    """Entfernt Rust-Kommentare, ohne Zeichenketten anzutasten.
    Noetig, weil in KEYS_LOCAL_SETTINGS ein '// Client-side: ...' steht --
    ein naiver Bezeichner-Treffer las daraus den Schluessel 'Client'.
    Gefunden, weil dieser Schritt gegen die ECHTE config.rs getestet
    wurde und nicht gegen ein ausgedachtes Beispiel."""
    out = []
    i, n = 0, len(s)
    in_str = False
    while i < n:
        c = s[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(s[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            while i < n and s[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "*":
            i += 2
            while i + 1 < n and not (s[i] == "*" and s[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def parse_keys_lists(src):
    """Loest die vier KEYS_-Listen aus config.rs auf. Die Listen bestehen
    aus Konstantenbezeichnern (OPTION_*), nicht aus Zeichenketten."""
    consts = dict(
        re.findall(r'pub const ([A-Z0-9_]+)\s*:\s*&str\s*=\s*"([^"]*)"\s*;', src)
    )
    if len(consts) < 50:
        abbruch(
            "Nur %d OPTION_*-Konstanten in config.rs gefunden (erwartet "
            ">= 50). Die Datei sieht nicht aus wie erwartet." % len(consts)
        )
    listen = {}
    for name in (
        "KEYS_DISPLAY_SETTINGS",
        "KEYS_LOCAL_SETTINGS",
        "KEYS_SETTINGS",
        "KEYS_BUILDIN_SETTINGS",
    ):
        m = re.search(
            r"pub const " + name + r"\s*:\s*&\[&str\]\s*=\s*&\[(.*?)\];", src, re.S
        )
        if not m:
            abbruch(
                "Liste %s steht nicht in config.rs. Ohne sie ist die "
                "Einordnung der Schluessel geraten -- und ein Schluessel "
                "im falschen Speicher wirkt LAUTLOS nicht." % name
            )
        werte = []
        for lit, ident in re.findall(
            r'"([^"]*)"|([A-Za-z_][A-Za-z0-9_]*)', ohne_kommentare(m.group(1))
        ):
            if lit:
                werte.append(lit)
            elif ident:
                if ident not in consts:
                    abbruch(
                        "Bezeichner %s aus %s laesst sich nicht aufloesen."
                        % (ident, name)
                    )
                werte.append(consts[ident])
        if not werte:
            abbruch("Liste %s ist leer -- das kann nicht stimmen." % name)
        # Abbildung wie read_custom_client(): JSON-Schreibweise mit "-",
        # gespeichert wird der Originalschluessel.
        listen[name] = {w.replace("_", "-"): w for w in werte}
    return listen


def main():
    b64 = os.environ.get("CUSTOM_B64", "").strip()
    if not b64:
        abbruch("CUSTOM_B64 ist leer. Es gibt nichts einzubrennen.")
    cfg_pfad = os.environ.get("CONFIG_RS", "./libs/hbb_common/src/config.rs")
    ausschluss = set(
        x.strip()
        for x in os.environ.get("BURNIN_EXCLUDE", ",".join(DEFAULT_EXCLUDE)).split(",")
        if x.strip()
    )

    try:
        roh = base64.b64decode(b64)
    except Exception as e:
        abbruch("CUSTOM_B64 ist kein gueltiges base64: %s" % e)
    try:
        daten = json.loads(roh)
    except Exception as e:
        abbruch("Der dekodierte Inhalt ist kein gueltiges JSON: %s" % e)
    if not isinstance(daten, dict):
        abbruch("Die oberste JSON-Ebene ist kein Objekt.")

    if not os.path.exists(cfg_pfad):
        abbruch("%s existiert nicht. Falsches Arbeitsverzeichnis?" % cfg_pfad)
    src = open(cfg_pfad, "r", encoding="utf-8").read()
    listen = parse_keys_lists(src)

    ziel = {n: {} for n in STORES}
    uebersprungen = []

    def advanced(settings, is_override):
        anzeige = "OVERWRITE_DISPLAY_SETTINGS" if is_override else "DEFAULT_DISPLAY_SETTINGS"
        lokal = "OVERWRITE_LOCAL_SETTINGS" if is_override else "DEFAULT_LOCAL_SETTINGS"
        server = "OVERWRITE_SETTINGS" if is_override else "DEFAULT_SETTINGS"
        for k, v in settings.items():
            if not isinstance(v, str):
                continue  # wie read_custom_client(): nur Zeichenketten
            if k in ausschluss:
                uebersprungen.append(k)
                continue
            if k in listen["KEYS_DISPLAY_SETTINGS"]:
                ziel[anzeige][listen["KEYS_DISPLAY_SETTINGS"][k]] = v
            elif k in listen["KEYS_LOCAL_SETTINGS"]:
                ziel[lokal][listen["KEYS_LOCAL_SETTINGS"][k]] = v
            elif k in listen["KEYS_SETTINGS"]:
                ziel[server][listen["KEYS_SETTINGS"][k]] = v
            elif k in listen["KEYS_BUILDIN_SETTINGS"]:
                # BUILTIN ist absichtlich NICHT nach is_override getrennt --
                # read_custom_client() macht das genauso.
                ziel["BUILTIN_SETTINGS"][listen["KEYS_BUILDIN_SETTINGS"][k]] = v
            else:
                # In keiner Liste: read_custom_client() schreibt so einen
                # Schluessel in alle vier Speicher, in BEIDEN Schreibweisen.
                k2 = k.replace("_", "-")
                k1 = k2.replace("-", "_")
                for store in (anzeige, lokal, server, "BUILTIN_SETTINGS"):
                    ziel[store][k1] = v
                    ziel[store][k2] = v

    rest = dict(daten)
    rest.pop("app-name", None)  # macht der Workflow bereits per sed
    for name, is_over in (("default-settings", False), ("override-settings", True)):
        sub = rest.pop(name, None)
        if isinstance(sub, dict):
            advanced(sub, is_over)
    for k, v in rest.items():
        if isinstance(v, str):
            if k in ausschluss:
                uebersprungen.append(k)
                continue
            ziel["HARD_SETTINGS"][k] = v

    # --- Stolperdraht QSKENNZEICHEN ------------------------------------
    # Der Server liefert fuer eine Soforthilfe-Sitzung "Quick Support" als
    # info.username; peer_card.dart baut daraus "<username>@<hostname>".
    # Steht hide-username-on-card auf Y, nimmt der Client den anderen Zweig
    # und zeigt nur den Rechnernamen -- die Kennzeichnung waere unsichtbar,
    # ohne dass irgendetwas fehlschlaegt.
    if ziel["BUILTIN_SETTINGS"].get("hide-username-on-card") == "Y":
        abbruch(
            "QSKENNZEICHEN: hide-username-on-card=Y macht die "
            "Quick-Support-Kennzeichnung im Gruppen-Reiter unsichtbar. "
            "Erst die Kennzeichnung verlegen, dann diesen Schalter setzen."
        )

    # --- Ersetzen ------------------------------------------------------
    neu = src
    for name in STORES:
        suche = (
            "pub static ref %s: RwLock<HashMap<String, String>> = "
            "Default::default();" % name
        )
        n = neu.count(suche)
        if n != 1:
            abbruch(
                "Die Deklaration von %s wurde %d mal gefunden (erwartet "
                "genau 1). Entweder hat sich config.rs geaendert, oder "
                "dieser Schritt lief schon. So oder so darf hier nicht "
                "weitergebaut werden." % (name, n)
            )
        ersatz = (
            "pub static ref %s: RwLock<HashMap<String, String>> = %s;"
            % (name, literal(ziel[name]))
        )
        neu = neu.replace(suche, ersatz, 1)

    open(cfg_pfad, "w", encoding="utf-8").write(neu)

    # --- Gegenpruefung AM ERGEBNIS, nicht am Rueckgabewert --------------
    # Dieselbe Regel wie in bau-lokal.ps1: der Rueckgabewert einer
    # Ersetzung sagt nichts darueber, ob das Ergebnis stimmt.
    kontrolle = open(cfg_pfad, "r", encoding="utf-8").read()
    fehlend = []
    for name in STORES:
        for k, v in ziel[name].items():
            paar = "(%s.to_owned(), %s.to_owned())" % (rust_str(k), rust_str(v))
            if paar not in kontrolle:
                fehlend.append("%s -> %s" % (name, k))
    if fehlend:
        abbruch(
            "Gegenpruefung fehlgeschlagen, %d Eintraege stehen nicht in "
            "config.rs: %s" % (len(fehlend), ", ".join(fehlend[:10]))
        )

    # --- Bericht (keine Werte, die ein Geheimnis sein koennten) ---------
    print("Eingebrannte Clientkonfiguration (%s):" % cfg_pfad)
    gesamt = 0
    for name in STORES:
        print("  %-28s %2d Eintraege" % (name, len(ziel[name])))
        gesamt += len(ziel[name])
    if uebersprungen:
        print(
            "  bewusst ausgelassen: %s (wuerden die einkompilierten "
            "Serverkonstanten ueberschreiben)" % ", ".join(sorted(set(uebersprungen)))
        )
    ct = ziel["HARD_SETTINGS"].get("conn-type", "<nicht gesetzt>")
    print("  conn-type = %s" % ct)
    print(
        "  Bauart: %s"
        % (
            "SOFORTHILFE (Minimalansicht, nur eingehend)"
            if ct == "incoming"
            else "DAUERINSTALLATION / beidseitig"
        )
    )
    print("  hide-network-settings = %s"
          % ziel["BUILTIN_SETTINGS"].get("hide-network-settings", "<nicht gesetzt>"))
    if gesamt == 0:
        abbruch("Null Eintraege eingebrannt -- der Schritt waere wirkungslos.")
    print("OK: %d Eintraege eingebrannt und am Ergebnis gegengeprueft." % gesamt)


if __name__ == "__main__":
    main()
