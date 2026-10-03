#!/usr/bin/env python3
"""OPTIONC / KXFAEHIGKEIT -- baut die gelernte Schluesseltausch-Faehigkeit
in src/common.rs ein (RustDesk 1.4.9).

Zweck: secure_tcp_impl bricht heute nach READ_TIMEOUT (18 000 ms) mit
"Failed to secure tcp: deadline has elapsed" ab, wenn der Rendezvous-Server
den Schluesseltausch gar nicht anbietet -- und genau das tut hbbs 1.1.16.
Das ist die Stoerung SECURETCP0924 vom 24.09.2026.

Diese Aenderung gehoert ZWINGEND zu DELAYFIXPRAEZISE (Patch 0012): jener
Schritt stellt die beiden secure_tcp-Waechter in src/client.rs wieder her,
die der alte grobe sed stillgelegt hatte. Ohne diese Datei hier kaeme damit
der 18-Sekunden-Abbruch zurueck, sobald im Client ein Konto angemeldet ist.

Gemessen am 03.10.2026 auf vm302 gegen das echte hbbs 1.1.16:
1515 ms beim Erstkontakt, danach 153/154 ms, kein Abbruch.
Nachweise: projekte/RDGEN-DELAYFIX-OPTIONC-2026-10-03.md
           projekte/RDGEN-DELAYFIX-AC2-BAUTEST-2026-10-03.md

Harte Anker, dreistufige Abnahme, Abbruch mit Exit 1 statt stiller Erfolg.
Kein continue-on-error, kein "|| true": ein verfehlter Anker MUSS den Lauf
abbrechen (WUPFAD0926).
"""
import sys, pathlib

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "src/common.rs")
if not ZIEL.is_file():
    print(f"OPTIONC FEHLER: {ZIEL} nicht gefunden (cwd={pathlib.Path.cwd()})",
          file=sys.stderr)
    sys.exit(1)

# Zeilenenden erhalten. read_text()/write_text() normalisieren still auf LF;
# auf einem Windows-Laeufer steht der Baum aber auf CRLF (core.autocrlf=true).
# Das Ergebnis waere ein Diff ueber JEDE Zeile der Datei statt ueber ~100 --
# der Uebersetzer stoert sich nicht daran, ein spaeteres `git apply` eines
# weiteren Schrittes aber sehr wohl. Gefunden am 03.10.2026 auf vm302.
_roh = ZIEL.read_bytes()
_crlf = _roh.count(b"\r\n") > 0
src = _roh.decode("utf-8").replace("\r\n", "\n")

ANKER_FN = "async fn secure_tcp_impl(conn: &mut Stream, key: &str, log_on_success: bool) -> ResultType<()> {"
ANKER_MATCH = "    match timeout(READ_TIMEOUT, conn.next()).await? {"
ANKER_SETKEY = "                        conn.set_key(key);"

VORSPANN = r'''// ===== OPTIONC (IT-Labuhn, 2026-10-03) ===================================
// Warum es hier steht und nicht an den Aufrufstellen: secure_tcp() UND
// secure_tcp_silent() laufen beide durch secure_tcp_impl. Ein Eingriff deckt
// alle vier Aufrufstellen ab (client.rs 431/860/4033,
// rendezvous_mediator.rs:428) und zusaetzlich den API-Ersatzweg ueber den
// TCP-Proxy (common.rs:1223).
//
// Warum gelernt und nicht gefragt: rendezvous.proto kennt KEIN Feld, mit dem
// ein Server seine Faehigkeiten ankuendigt, und der Schluesseltausch ist
// selbst das erste Byte auf der Leitung. Eine Vorab-Abfrage ist damit nicht
// baubar. Die einzige verfuegbare Auskunft ist die eigene Erfahrung mit genau
// diesem Server.
//
// Was damit NICHT mehr passieren kann: der 18-Sekunden-Abbruch vom 24.09.2026
// (SECURETCP0924). Diese Funktion bricht in KEINEM Zweig mehr wegen einer
// abgelaufenen Frist ab.
#[derive(Clone, Copy, PartialEq, Eq)]
enum KxFaehigkeit {
    Unbekannt,
    Vorhanden,
    Fehlt,
}

lazy_static::lazy_static! {
    static ref KX_FAEHIGKEIT: Arc<Mutex<HashMap<String, (KxFaehigkeit, Instant)>>> =
        Default::default();
}

// Erstkontakt: grosszuegig, damit ein echter Schluesseltausch auf einer
// langsamen Leitung nicht faelschlich als "kann es nicht" gewertet wird.
const KX_WARTE_UNBEKANNT: u64 = 1_500;
// Server hat schon geschwiegen: nur noch kurz nachfragen. Kostet fast nichts
// und erkennt ein spaeteres Server-Upgrade bereits bei der naechsten
// Verbindung, ohne Neustart und ohne Neubau.
const KX_WARTE_FEHLT: u64 = 150;
// Server hat den Tausch nachweislich schon einmal geleistet: dann ist langes
// Warten richtig, denn ein stiller Rueckfall waere hier eine unbemerkte
// Verschlechterung der Sicherheit. Bewusst kuerzer als READ_TIMEOUT (18 s) --
// ein Server, der vor Minuten noch getauscht hat und jetzt 5 s schweigt, ist
// defekt, und ein 18-Sekunden-Stillstand vor dem Anwender ist selbst ein
// Fehler.
const KX_WARTE_VORHANDEN: u64 = 5_000;
// "Kann es nicht" gilt nur auf Zeit. Danach wird wieder grosszuegig gefragt --
// so heilt eine Fehlmessung auf einer kurzzeitig schlechten Leitung von
// selbst, und ein Serverwechsel auf eine Fassung MIT Schluesseltausch wird
// innerhalb dieser Frist erkannt.
const KX_FEHLT_GUELTIG_MS: u128 = 600_000;

fn kx_lesen(server: &str) -> KxFaehigkeit {
    let Ok(m) = KX_FAEHIGKEIT.lock() else {
        return KxFaehigkeit::Unbekannt;
    };
    match m.get(server) {
        Some((KxFaehigkeit::Fehlt, seit)) if seit.elapsed().as_millis() > KX_FEHLT_GUELTIG_MS => {
            KxFaehigkeit::Unbekannt
        }
        Some((f, _)) => *f,
        None => KxFaehigkeit::Unbekannt,
    }
}

fn kx_merken(server: &str, f: KxFaehigkeit) {
    if let Ok(mut m) = KX_FAEHIGKEIT.lock() {
        m.insert(server.to_owned(), (f, Instant::now()));
    }
}

'''

NEUER_MATCH = r'''    let kx_server = Config::get_rendezvous_server();
    let kx_vorher = kx_lesen(&kx_server);
    let kx_warte = match kx_vorher {
        KxFaehigkeit::Vorhanden => KX_WARTE_VORHANDEN,
        KxFaehigkeit::Fehlt => KX_WARTE_FEHLT,
        KxFaehigkeit::Unbekannt => KX_WARTE_UNBEKANNT,
    };
    let kx_erste = match timeout(kx_warte, conn.next()).await {
        Ok(v) => v,
        Err(_) => {
            // NIE abbrechen -- genau dieses `?` war der 18-Sekunden-Ausfall.
            if kx_vorher == KxFaehigkeit::Vorhanden {
                log::warn!(
                    "Rendezvous server {} did offer key exchange before but stayed silent for {} ms; continuing on the plain channel",
                    kx_server,
                    kx_warte
                );
                kx_merken(&kx_server, KxFaehigkeit::Unbekannt);
            } else {
                log::info!(
                    "Rendezvous server {} offers no key exchange, continuing on the plain channel",
                    kx_server
                );
                kx_merken(&kx_server, KxFaehigkeit::Fehlt);
            }
            return Ok(());
        }
    };
    match kx_erste {'''

NEUER_SETKEY = '''                        conn.set_key(key);
                        kx_merken(&kx_server, KxFaehigkeit::Vorhanden);'''


def zaehle(nadel):
    """Zaehlt den Anker als GANZE Zeile.

    Teilstring-Zaehlung reicht nicht: eine veraenderte Zeile, die den Anker
    noch als Teilstring enthaelt (z.B. ein angehaengter Kommentar), waere
    sonst unbemerkt durchgegangen -- im Schlechtfall-Test genau passiert.
    """
    return sum(1 for z in src.splitlines() if z.rstrip() == nadel.rstrip())


# --- Stufe 1: Anker genau einmal? --------------------------------------
fehler = []
for name, nadel in (
    ("Funktionskopf", ANKER_FN),
    ("READ_TIMEOUT-match", ANKER_MATCH),
    ("conn.set_key(key)", ANKER_SETKEY),
):
    n = zaehle(nadel)
    print(f"OPTIONC Anker {name}: {n}x")
    if n != 1:
        fehler.append(f"Anker {name} kommt {n}x vor, erwartet genau 1")

# Gegenprobe: laeuft hier schon eine Option C?
if "OPTIONC" in src:
    fehler.append("src/common.rs traegt bereits eine OPTIONC-Aenderung")

if fehler:
    for f in fehler:
        print("OPTIONC FEHLER: " + f, file=sys.stderr)
    sys.exit(1)

# --- Stufe 2: anwenden -------------------------------------------------
neu = src.replace(ANKER_FN, VORSPANN + ANKER_FN, 1)
neu = neu.replace(ANKER_MATCH, NEUER_MATCH, 1)
neu = neu.replace(ANKER_SETKEY, NEUER_SETKEY, 1)

# --- Stufe 3: Abnahme am Ergebnis --------------------------------------
pruef = [
    ("alter abbrechender Zeitzaun weg", neu.count(ANKER_MATCH) == 0),
    ("neuer Zeitzaun da", neu.count("match timeout(kx_warte, conn.next()).await") == 1),
    ("kein `?` mehr am Zeitzaun", "timeout(kx_warte, conn.next()).await?" not in neu),
    ("Zustand wird gesetzt (Vorhanden)", neu.count("KxFaehigkeit::Vorhanden)") >= 1),
    ("Zustand wird gesetzt (Fehlt)", neu.count("kx_merken(&kx_server, KxFaehigkeit::Fehlt)") == 1),
    ("secure_tcp-Waechter unberuehrt",
     neu.count("if !key.is_empty() && !token.is_empty() {") == src.count("if !key.is_empty() && !token.is_empty() {")),
    ("Klammern ausgeglichen", neu.count("{") - neu.count("}") == src.count("{") - src.count("}")),
]
schlecht = [n for n, ok in pruef if not ok]
for n, ok in pruef:
    print(f"OPTIONC Abnahme {'OK  ' if ok else 'FEHL'} {n}")
if schlecht:
    sys.exit(1)

_aus = neu.replace("\n", "\r\n") if _crlf else neu
ZIEL.write_bytes(_aus.encode("utf-8"))
print(f"OPTIONC OK -- {ZIEL} umgestellt (Zeilenenden: {'CRLF' if _crlf else 'LF'})")
