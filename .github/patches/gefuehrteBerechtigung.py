#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GEFUEHRTE BERECHTIGUNG 2026-10-02 -- die beiden macOS-Freigaben
(Bedienungshilfen + Bildschirmaufnahme, dazu Eingabeueberwachung) als
gefuehrten Ablauf: automatischer Sprung in die zustaendige Unterseite,
lebendige Erkennung der Erteilung, automatisches Weiterspringen,
sichtbarer Fortschritt.

WAS DER UNVERAENDERTE QUELLTEXT SCHON HAT -- UND WO ER AUFHOERT
---------------------------------------------------------------
RustDesk 1.4.9 hat bereits eine Berechtigungspruefung. Sie wurde NICHT
neu erfunden, sondern erweitert. Vorhanden ist:

  * drei FFI-Funktionen (src/flutter_ffi.rs Z. 2328-2338):
    main_is_process_trusted / main_is_can_screen_recording /
    main_is_can_input_monitoring, je mit einem prompt-Schalter,
  * je eine Hinweiskarte in buildHelpCards()
    (flutter/lib/desktop/pages/desktop_home_page.dart Z. 479-498),
    nacheinander, jede mit einem Knopf "Configure",
  * eine 1-Sekunden-Abfrageschleife in initState() mit den Merkern
    watchIsCanScreenRecording / watchIsProcessTrust /
    watchIsInputMonitoring,
  * einen Direktsprung in die Systemeinstellungen -- aber nur fuer die
    Eingabeueberwachung (Privacy_ListenEvent, src/platform/macos.mm
    Z. 56).

Es fehlen genau die Punkte aus Masters Auftrag:
  1. Der Sprung passiert nicht von selbst. Der Anwender muss je Freigabe
     auf "Configure" klicken.
  2. Fuer Bildschirmaufnahme und Bedienungshilfen gibt es keinen
     Direktsprung, sondern nur den Systemdialog -- darin ist noch ein
     Klick auf "Systemeinstellungen oeffnen" faellig.
  3. Es gibt keinen Fortschritt ("Schritt 1 von 2").
  4. Nach der Erteilung verschwindet die Karte und die naechste erscheint;
     der Anwender muss das bemerken und erneut klicken. Es wird nicht
     weitergesprungen.

DER FEHLER, DER DABEI GEFUNDEN WURDE -- UND OHNE DEN DER REST NICHT TRAEGT
--------------------------------------------------------------------------
Die vorhandene Abfrageschleife auf die Bildschirmaufnahme kann auf
macOS 11 und neuer NIEMALS umschlagen.

  src/platform/macos.rs  unsafe_is_can_screen_recording():
      if CanUseNewApiForScreenCaptureCheck() == YES {   // >= macOS 11
          return IsCanScreenRecording(...) == YES;
      }
  src/platform/macos.mm  IsCanScreenRecording():
      bool res = CGPreflightScreenCaptureAccess();

CGPreflightScreenCaptureAccess() ist pro PROZESSLAUF zwischengespeichert.
Wird die Freigabe erteilt, waehrend die App laeuft, antwortet die Funktion
weiter mit "denied" -- bis zum Neustart. Der Merker
watchIsCanScreenRecording wird deshalb nie geloescht.

Das ist kein Schoenheitsfehler, sondern die Grundlage des Auftrags: ein
automatisches Weiterspringen nach der Bildschirmaufnahme-Freigabe ist auf
dieser Pruefung BAULICH UNMOEGLICH. Deshalb wird hier eine lebendige
Messung ueber SCShareableContent (ScreenCaptureKit) daneben gestellt.
Der alte, gespeicherte Wert bleibt als billige Vorab-Antwort erhalten --
wenn er "erteilt" sagt, ist das richtig; nur sein "nicht erteilt" ist
nicht mehr das letzte Wort.

Die Bedienungshilfen haben dieses Problem nicht: AXIsProcessTrusted()
liest ohne Zwischenspeicher. Genau darum steht dieser Schritt im
gefuehrten Ablauf ZUERST -- der Anwender erlebt das automatische
Weiterspringen damit am verlaesslichsten Schritt zum ersten Mal.

WARUM KEINE NEUE FFI-FUNKTION
-----------------------------
Die Dart-Bruecke wird in einem EIGENEN Ablaufauftrag erzeugt
(.github/workflows/bridge.yml, Auftrag generate-bridge). Dieser Auftrag
holt rustdesk/rustdesk UNVERAENDERT und laesst
flutter_rust_bridge_codegen darueber laufen; das Erzeugnis wird dem
macOS-Auftrag erst spaeter als Artefakt untergeschoben
("Restore bridge files"). Eine Funktion, die dieses Skript in
src/flutter_ffi.rs ergaenzen wuerde, fehlte damit in
generated_bridge.dart -- die Dart-Uebersetzung braeche ab.

Folge, und das ist eine Entwurfsvorgabe und kein Zufall: der ganze
Ablauf arbeitet ausschliesslich mit den DREI VORHANDENEN FFI-Funktionen.
Ihre Bedeutung wird praezisiert, ihre Signatur nicht angetastet:

  prompt = false  ->  "lies den Zustand, LEBEND, ohne Nebenwirkung"
  prompt = true   ->  "bring den Anwender dorthin, wo er es erteilen kann"

HARTE ABNAHME, KEIN "|| true"
-----------------------------
Ein gruener Bau mit wirkungslosem Erzeugnis ist die Fehlerklasse, die
dieses Haus hier am 30.09., 01.10. und 02.10. je einmal getroffen hat
(zuletzt der urlLink-sed, der rustdesk.com durch rustdesk.com ersetzte).
Deshalb bricht jede einzelne Ersetzung ab, wenn ihr Anker nicht genau
einmal vorkommt, und jede Datei wird nach dem Schreiben ERNEUT GELESEN
und gegen das erwartete Ergebnis geprueft. Ein zweiter Lauf bricht ab.

Umgebungsvariablen (alle optional, Vorgaben sind die Pfade im Baum):
  MM_DATEI     src/platform/macos.mm
  RS_DATEI     src/platform/macos.rs
  DART_DATEI   flutter/lib/desktop/pages/desktop_home_page.dart
  EN_DATEI     src/lang/en.rs
  DE_DATEI     src/lang/de.rs
"""

import io
import os
import sys

MM_DATEI = os.environ.get("MM_DATEI", os.path.join("src", "platform", "macos.mm"))
RS_DATEI = os.environ.get("RS_DATEI", os.path.join("src", "platform", "macos.rs"))
DART_DATEI = os.environ.get(
    "DART_DATEI",
    os.path.join("flutter", "lib", "desktop", "pages", "desktop_home_page.dart"),
)
EN_DATEI = os.environ.get("EN_DATEI", os.path.join("src", "lang", "en.rs"))
DE_DATEI = os.environ.get("DE_DATEI", os.path.join("src", "lang", "de.rs"))

MARKE = "GEFUEHRTE BERECHTIGUNG"


def abbruch(text):
    sys.stderr.write("GEFUEHRTEBERECHTIGUNG FEHLER: %s\n" % text)
    sys.exit(1)


def lies(pfad):
    if not os.path.isfile(pfad):
        abbruch("Datei nicht gefunden: %s (cwd=%s)" % (pfad, os.getcwd()))
    with io.open(pfad, "r", encoding="utf-8") as f:
        return f.read()


def schreib(pfad, inhalt):
    with io.open(pfad, "w", encoding="utf-8", newline="") as f:
        f.write(inhalt)


def genau_einmal(inhalt, anker, pfad, wofuer):
    n = inhalt.count(anker)
    if n != 1:
        abbruch(
            "%s: Anker fuer %s kommt %d mal vor, erwartet genau 1.\n"
            "  Anker: %r" % (pfad, wofuer, n, anker[:120])
        )


def ersetze(inhalt, alt, neu, pfad, wofuer):
    genau_einmal(inhalt, alt, pfad, wofuer)
    return inhalt.replace(alt, neu, 1)


# ---------------------------------------------------------------------------
# Zwei Stufen, damit kein halb gepatchter Baum zurueckbleibt.
#
# Bis zur ersten Fassung lief jede Datei fuer sich: erst aendern, dann
# schreiben, dann gegenlesen. Bricht dabei die DRITTE Datei ab, sind die
# ersten zwei schon geschrieben -- im Ablauf harmlos (der Auftrag
# scheitert, der Arbeitsbereich wird verworfen), bei einem Lauf von Hand
# aber ein Baum, der aussieht wie gepatcht und es nicht ist.
#
# Jetzt: Stufe 1 prueft ALLE Anker und baut alle neuen Inhalte im
# Speicher. Erst wenn das vollstaendig durchlief, schreibt Stufe 2.
# ---------------------------------------------------------------------------
PLAN = []


def plane(pfad, inhalt):
    PLAN.append((pfad, inhalt))


def schreibe_plan():
    for pfad, inhalt in PLAN:
        schreib(pfad, inhalt)


# ===========================================================================
# 1 -- src/platform/macos.mm
# ===========================================================================

MM_INCLUDE_ALT = """#include <CoreGraphics/CoreGraphics.h>
#include <vector>
#include <map>
#include <set>
#include <mutex>
#include <string>
"""

MM_INCLUDE_NEU = """#include <CoreGraphics/CoreGraphics.h>
#include <vector>
#include <map>
#include <set>
#include <mutex>
#include <string>
// GEFUEHRTE BERECHTIGUNG: atomic fuer den Zustand der lebendigen Messung,
// objc/message.h fuer den Aufruf von ScreenCaptureKit zur LAUFZEIT (siehe
// die ausfuehrliche Begruendung an OpenPrivacyPane).
#include <atomic>
#import <objc/message.h>
"""

# Die Helfer stehen ABSICHTLICH vor IsCanScreenRecording und damit auch vor
# InputMonitoringAuthStatus -- beide rufen OpenPrivacyPane auf, und eine
# Vorwaertsdeklaration waere eine zweite Stelle, die veralten kann.
MM_ISCAN_ALT = """extern "C" bool IsCanScreenRecording(bool prompt) {
    #ifdef NO_InputMonitoringAuthStatus
    return false;
    #else
    bool res = CGPreflightScreenCaptureAccess();
    if (!res && prompt) {
        CGRequestScreenCaptureAccess();
    }
    return res;
    #endif
}
"""

MM_ISCAN_NEU = """// ===== GEFUEHRTE BERECHTIGUNG 2026-10-02 =====
//
// Zwei Bausteine, die der unveraenderte Quelltext nicht hat.
//
// (1) OpenPrivacyPane() -- Direktsprung in die ZUSTAENDIGE Unterseite der
//     Systemeinstellungen. Den Sprung gab es bisher nur fuer die
//     Eingabeueberwachung (Privacy_ListenEvent, weiter unten in
//     InputMonitoringAuthStatus). Fuer Bildschirmaufnahme und
//     Bedienungshilfen gab es nur den Systemdialog, in dem noch einmal
//     "Systemeinstellungen oeffnen" angeklickt werden muss.
//
// (2) Eine LEBENDIGE Pruefung der Bildschirmaufnahme.
//     CGPreflightScreenCaptureAccess() ist pro Prozesslauf
//     zwischengespeichert: wird die Freigabe erteilt, waehrend die App
//     laeuft, antwortet die Funktion weiter mit "denied" -- bis zum
//     Neustart. Die bestehende Abfrageschleife auf diesen Wert kann
//     deshalb nie umschlagen, und ein automatisches Weiterspringen waere
//     baulich unmoeglich. SCShareableContent spiegelt den AKTUELLEN
//     TCC-Zustand.
//
// Warum ScreenCaptureKit zur LAUFZEIT gesucht wird (NSClassFromString /
// objc_msgSend) und nicht ueber Header und Framework-Link:
// MACOSX_DEPLOYMENT_TARGET dieses Baus ist 10.14 (build.py Z. 409,
// Runner.xcodeproj), ScreenCaptureKit gibt es erst ab macOS 12.3. Ein
// harter Framework-Link wuerde den Start auf aelteren Fassungen
// verhindern. Ein -weak_framework muesste in den ENDLINK des
// Flutter-Buendels gereicht werden -- macos.mm wird von cc als statische
// Bibliothek uebersetzt, dieser Patch hat den Endlink nicht in der Hand.
// Die Laufzeitsuche kommt ohne jede Aenderung an der Bau-Verdrahtung aus
// und antwortet auf 10.14 sauber mit "nicht vorhanden".

static std::atomic<bool> g_scErteilt(false);
static std::atomic<bool> g_scMessungLaeuft(false);
static std::atomic<double> g_scMessungBegonnen(0.0);
static std::atomic<bool> g_scUnterseiteGeoeffnet(false);

extern "C" void OpenPrivacyPane(const char* anker) {
    if (anker == NULL) {
        return;
    }
    NSString *a = [NSString stringWithUTF8String:anker];
    if (a == nil) {
        return;
    }
    // Die alte, parameterbehaftete Form zuerst. Die Ventura-Form
    // (com.apple.settings.PrivacySecurity.extension) oeffnet ohne Anker nur
    // die Oberseite "Datenschutz & Sicherheit" -- und genau das Suchen soll
    // wegfallen.
    NSArray<NSString *> *kandidaten = @[
        [NSString stringWithFormat:
            @"x-apple.systempreferences:com.apple.preference.security?%@", a],
        [NSString stringWithFormat:
            @"x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?%@", a],
    ];
    dispatch_async(dispatch_get_main_queue(), ^{
        for (NSString *s in kandidaten) {
            NSURL *u = [NSURL URLWithString:s];
            if (u != nil && [[NSWorkspace sharedWorkspace] openURL:u]) {
                return;
            }
        }
    });
}

extern "C" bool ScreenCaptureKitAvailable() {
    return NSClassFromString(@"SCShareableContent") != nil;
}

// Stoesst eine Messung an und kehrt SOFORT zurueck.
// Bewusst nicht blockierend: der Aufrufer ist am Ende die Dart-Seite ueber
// einen SyncReturn. Ein Warten auf den WindowServer wuerde die Oberflaeche
// einfrieren -- und ein Umlauf zum WindowServer kann unter Last Sekunden
// dauern.
extern "C" void ScreenCaptureKitProbeKick() {
    Class cls = NSClassFromString(@"SCShareableContent");
    if (cls == nil) {
        return;
    }
    SEL sel = NSSelectorFromString(
        @"getShareableContentExcludingDesktopWindows:onScreenWindowsOnly:completionHandler:");
    if (![cls respondsToSelector:sel]) {
        return;
    }
    double jetzt = CFAbsoluteTimeGetCurrent();
    if (g_scMessungLaeuft.load()) {
        // Bleibt der Rueckweg aus, darf die Pruefung nicht dauerhaft
        // blockiert bleiben: sie wuerde sonst fuer immer "keine Freigabe"
        // melden, und das waere ein stiller Fehlschlag.
        if (jetzt - g_scMessungBegonnen.load() < 10.0) {
            return;
        }
    }
    g_scMessungLaeuft.store(true);
    g_scMessungBegonnen.store(jetzt);
    void (^fertig)(id, NSError *) = ^(id inhalt, NSError *fehler) {
        g_scErteilt.store(fehler == nil && inhalt != nil);
        g_scMessungLaeuft.store(false);
    };
    typedef void (*Aufruf)(id, SEL, BOOL, BOOL, void (^)(id, NSError *));
    ((Aufruf)objc_msgSend)((id)cls, sel, NO, YES, fertig);
}

extern "C" bool ScreenCaptureKitGranted() {
    return g_scErteilt.load();
}

extern "C" bool IsCanScreenRecording(bool prompt) {
    #ifdef NO_InputMonitoringAuthStatus
    return false;
    #else
    if (prompt) {
        // CGRequestScreenCaptureAccess() bleibt drin, obwohl der Sprung den
        // Dialog ueberfluessig macht: dieser Aufruf ist der dokumentierte
        // Weg, mit dem sich die App UEBERHAUPT ERST in die TCC-Liste
        // eintraegt. Ohne ihn kann die Unterseite "Bildschirmaufnahme" leer
        // sein -- der Anwender haette dann nichts zum Umlegen, und der
        // gefuehrte Ablauf endete in einer Sackgasse.
        if (!CGPreflightScreenCaptureAccess()) {
            CGRequestScreenCaptureAccess();
        }
        OpenPrivacyPane("Privacy_ScreenCapture");
        g_scUnterseiteGeoeffnet.store(true);
    }
    // Der zwischengespeicherte Wert zuerst: sein "erteilt" ist richtig und
    // billig. Nur sein "nicht erteilt" ist nicht mehr das letzte Wort.
    if (CGPreflightScreenCaptureAccess()) {
        return true;
    }
    // Erst ab hier die lebendige Messung. Sie kann selbst einen TCC-Dialog
    // ausloesen, deshalb nicht, bevor der Anwender in der Unterseite
    // angekommen ist -- dort ist ein Dialog erwartbar und stoert nicht.
    if (g_scUnterseiteGeoeffnet.load()) {
        ScreenCaptureKitProbeKick();
        return ScreenCaptureKitGranted();
    }
    return false;
    #endif
}
"""

# Eine Quelle der Wahrheit fuer die Sprung-Adresse: die fest eingebaute
# URL der Eingabeueberwachung weicht demselben Helfer.
MM_LISTEN_ALT = """            case kIOHIDAccessTypeDenied: {
                if (prompt) {
                    NSString *urlString = @"x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent";
                    [[NSWorkspace sharedWorkspace] openURL:[NSURL URLWithString:urlString]];
                }
                break;
            }
            case kIOHIDAccessTypeUnknown: {
                if (prompt) {
                    bool result = IOHIDRequestAccess(kIOHIDRequestTypeListenEvent);
                    NSLog(@"IOHIDRequestAccess result = %d", result);
                }
                break;
            }
"""

MM_LISTEN_NEU = """            case kIOHIDAccessTypeDenied: {
                if (prompt) {
                    // GEFUEHRTE BERECHTIGUNG: derselbe Helfer wie fuer die
                    // beiden anderen Freigaben. Eine zweite, fest
                    // eingebaute URL waere eine Stelle, die veralten kann.
                    OpenPrivacyPane("Privacy_ListenEvent");
                }
                break;
            }
            case kIOHIDAccessTypeUnknown: {
                if (prompt) {
                    bool result = IOHIDRequestAccess(kIOHIDRequestTypeListenEvent);
                    NSLog(@"IOHIDRequestAccess result = %d", result);
                    // GEFUEHRTE BERECHTIGUNG: auch hier in die Unterseite,
                    // damit der gefuehrte Ablauf nicht am Dialog endet. Der
                    // Aufruf darueber traegt die App in die Liste ein, der
                    // Sprung bringt den Anwender dorthin.
                    OpenPrivacyPane("Privacy_ListenEvent");
                }
                break;
            }
"""


def plane_mm():
    pfad = MM_DATEI
    s = lies(pfad)
    if MARKE in s:
        abbruch("%s traegt die Marke %r schon -- zweiter Lauf." % (pfad, MARKE))
    s = ersetze(s, MM_INCLUDE_ALT, MM_INCLUDE_NEU, pfad, "Include-Block")
    s = ersetze(s, MM_ISCAN_ALT, MM_ISCAN_NEU, pfad, "IsCanScreenRecording")
    s = ersetze(s, MM_LISTEN_ALT, MM_LISTEN_NEU, pfad, "InputMonitoring-Sprung")
    plane(pfad, s)


def pruefe_mm():
    # Gegenlesen von der PLATTE. Der Rueckgabewert einer Ersetzung sagt
    # nichts darueber, ob das Ergebnis dort stimmt.
    pfad = MM_DATEI
    p = lies(pfad)
    for muss in (
        "#include <atomic>",
        "#import <objc/message.h>",
        "extern \"C\" void OpenPrivacyPane(const char* anker)",
        "extern \"C\" bool ScreenCaptureKitAvailable()",
        "extern \"C\" void ScreenCaptureKitProbeKick()",
        "extern \"C\" bool ScreenCaptureKitGranted()",
        "OpenPrivacyPane(\"Privacy_ScreenCapture\")",
        "getShareableContentExcludingDesktopWindows:onScreenWindowsOnly:completionHandler:",
    ):
        if muss not in p:
            abbruch("%s: %r fehlt nach dem Schreiben." % (pfad, muss))
    if "NSString *urlString = @\"x-apple.systempreferences" in p:
        abbruch("%s: die fest eingebaute ListenEvent-URL steht noch drin." % pfad)
    if p.count("OpenPrivacyPane(\"Privacy_ListenEvent\")") != 2:
        abbruch("%s: ListenEvent-Sprung nicht genau zweimal vorhanden." % pfad)
    print("  macos.mm           OK (Sprunghelfer + lebendige Messung)")


# ===========================================================================
# 2 -- src/platform/macos.rs
# ===========================================================================

RS_EXTERN_ALT = """    fn InputMonitoringAuthStatus(_: BOOL) -> BOOL;
    fn IsCanScreenRecording(_: BOOL) -> BOOL;
    fn CanUseNewApiForScreenCaptureCheck() -> BOOL;
"""

RS_EXTERN_NEU = """    fn InputMonitoringAuthStatus(_: BOOL) -> BOOL;
    fn IsCanScreenRecording(_: BOOL) -> BOOL;
    fn CanUseNewApiForScreenCaptureCheck() -> BOOL;
    // GEFUEHRTE BERECHTIGUNG, beide in src/platform/macos.mm
    fn OpenPrivacyPane(anker: *const hbb_common::libc::c_char);
    fn ScreenCaptureKitAvailable() -> BOOL;
"""

RS_TRUSTED_ALT = """pub fn is_process_trusted(prompt: bool) -> bool {
    autoreleasepool(|| unsafe_is_process_trusted(prompt))
}
"""

RS_TRUSTED_NEU = """// GEFUEHRTE BERECHTIGUNG: Oeffnet die Unterseite der Systemeinstellungen,
// in der die genannte Freigabe erteilt wird.
// anker ist "Privacy_Accessibility", "Privacy_ScreenCapture" oder
// "Privacy_ListenEvent".
pub fn open_privacy_pane(anker: &str) {
    match std::ffi::CString::new(anker) {
        Ok(c) => {
            // SICHERHEIT: Der Zeiger wird ausschliesslich fuer die Dauer
            // dieses Aufrufs gelesen; die Obj-C-Seite kopiert den Inhalt
            // sofort in ein NSString und behaelt den Zeiger nicht. c lebt
            // bis zum Ende dieses Zweigs und damit laenger als der Aufruf.
            unsafe { OpenPrivacyPane(c.as_ptr()) };
        }
        Err(e) => {
            // Kann nur bei einem Null-Byte im Anker auftreten. Die drei
            // Anker sind feste Zeichenketten, also nie -- aber ein
            // stillschweigendes Verschlucken wuerde den Ablauf an einer
            // unerklaerlichen Stelle haengen lassen.
            log::error!("open_privacy_pane({}): {}", anker, e);
        }
    }
}

pub fn is_process_trusted(prompt: bool) -> bool {
    let vertraut = autoreleasepool(|| unsafe_is_process_trusted(prompt));
    if prompt && !vertraut {
        // GEFUEHRTE BERECHTIGUNG: AXIsProcessTrustedWithOptions(prompt)
        // zeigt den Systemdialog, in dem noch einmal
        // "Systemeinstellungen oeffnen" angeklickt werden muss. Der Dialog
        // bleibt -- er ist der Weg, auf dem die App in die Liste der
        // Bedienungshilfen eingetragen wird -- der Klick faellt weg.
        open_privacy_pane("Privacy_Accessibility");
    }
    vertraut
}
"""

RS_SCREEN_ALT = """    unsafe {
        if CanUseNewApiForScreenCaptureCheck() == YES {
            return IsCanScreenRecording(if prompt { YES } else { NO }) == YES;
        }
    }
"""

RS_SCREEN_NEU = """    unsafe {
        if CanUseNewApiForScreenCaptureCheck() == YES {
            if IsCanScreenRecording(if prompt { YES } else { NO }) == YES {
                return true;
            }
            // GEFUEHRTE BERECHTIGUNG: Ab macOS 12.3 ist die Antwort
            // darueber bereits LEBENDIG gemessen (SCShareableContent in
            // macos.mm) -- ein "nein" ist dort ein echtes "nein".
            // Nur wo ScreenCaptureKit fehlt (macOS 11 bis 12.2), ist die
            // Fensternamen-Heuristik darunter der einzige Weg, der ohne
            // Neustart umschlaegt; dort faellt die Pruefung bewusst durch.
            if ScreenCaptureKitAvailable() == YES {
                return false;
            }
        }
    }
"""


def plane_rs():
    pfad = RS_DATEI
    s = lies(pfad)
    if MARKE in s:
        abbruch("%s traegt die Marke %r schon -- zweiter Lauf." % (pfad, MARKE))
    s = ersetze(s, RS_EXTERN_ALT, RS_EXTERN_NEU, pfad, "extern-Block")
    s = ersetze(s, RS_TRUSTED_ALT, RS_TRUSTED_NEU, pfad, "is_process_trusted")
    s = ersetze(s, RS_SCREEN_ALT, RS_SCREEN_NEU, pfad, "is_can_screen_recording")
    plane(pfad, s)


def pruefe_rs():
    pfad = RS_DATEI
    p = lies(pfad)
    for muss in (
        "pub fn open_privacy_pane(anker: &str)",
        "open_privacy_pane(\"Privacy_Accessibility\")",
        "fn ScreenCaptureKitAvailable() -> BOOL;",
        "if ScreenCaptureKitAvailable() == YES {",
        "// SICHERHEIT:",
    ):
        if muss not in p:
            abbruch("%s: %r fehlt nach dem Schreiben." % (pfad, muss))
    if "return IsCanScreenRecording(if prompt { YES } else { NO }) == YES;" in p:
        abbruch("%s: die alte, zwischengespeicherte Rueckgabe steht noch drin." % pfad)
    print("  macos.rs           OK (Sprung + Durchfall fuer macOS 11-12.2)")


# ===========================================================================
# 3 -- flutter/lib/desktop/pages/desktop_home_page.dart
# ===========================================================================

DART_KLASSE_ALT = "const borderColor = Color(0xFF2F65BA);\n"

DART_KLASSE_NEU = """const borderColor = Color(0xFF2F65BA);

// ===== GEFUEHRTE BERECHTIGUNG 2026-10-02 =====
// Ein Schritt des gefuehrten Freigabe-Ablaufs auf macOS.
//
// erteilt wird bei JEDEM Aufbau neu gelesen und nicht zwischengespeichert:
// AXIsProcessTrusted() und die SCShareableContent-Messung in macos.mm
// spiegeln den TCC-Zustand lebend, und genau davon haengt das
// automatische Weiterspringen ab.
class _MacFreigabe {
  // Stabiler Name fuer die Merkliste "hierher wurde schon gesprungen".
  // Bewusst NICHT der Uebersetzungsschluessel: der darf sich aendern,
  // ohne dass der Ablauf von vorne anfaengt.
  final String schluessel;
  // Uebersetzungsschluessel des Kurznamens, wie er in der Fortschrittsliste steht.
  final String name;
  // Uebersetzungsschluessel der Begruendung. Diese drei Texte enthalten
  // "RustDesk" und werden deshalb -- zur Bauzeit durch den sed des
  // Ablaufs, zur Laufzeit durch translate() -- auf den Anzeigenamen der
  // App umgeschrieben. Damit nennt der Hinweis automatisch den Namen, der
  // in der Liste der Systemeinstellungen steht, und kann nicht
  // auseinanderlaufen.
  final String begruendung;
  final bool erteilt;
  // Schickt den Anwender in die zustaendige Unterseite (prompt: true).
  final void Function() sprung;
  const _MacFreigabe(
      this.schluessel, this.name, this.begruendung, this.erteilt, this.sprung);
}
"""

DART_FELD_ALT = "  bool isCardClosed = false;\n"

DART_FELD_NEU = """  bool isCardClosed = false;

  // ===== GEFUEHRTE BERECHTIGUNG 2026-10-02 =====
  // In welche Unterseiten in diesem Programmlauf bereits gesprungen wurde.
  // Ohne diese Merkliste wuerde die 1-Sekunden-Schleife die
  // Systemeinstellungen jede Sekunde erneut nach vorne holen -- und damit
  // genau den Anwender daran hindern, den Schalter umzulegen.
  final Set<String> _macFreigabeGesprungen = {};
  // Letzter gesehener Stand aller Freigaben ("101"), nur zum Vergleich.
  String _macFreigabeStand = '';
  // Die Schleife laeuft nur, solange der Ablauf wirklich sichtbar ist. Wer
  // alles erteilt hat, zahlt keine drei FFI-Aufrufe pro Sekunde.
  bool _macFreigabeLaeuft = false;
  // Anzahl der FEHLENDEN Freigaben beim BEGINN des Ablaufs, einmal
  // festgehalten. Sonst liest die Anzeige erst "Schritt 1 von 2" und nach
  // der ersten Freigabe "Schritt 1 von 1" -- ein Fortschritt, der nicht
  // fortschreitet.
  int _macFreigabeGesamt = 0;
  int _macFreigabeVorherErteilt = 0;
"""

# Die drei Berechtigungskarten weichen dem gefuehrten Ablauf. Der
# Daemon-Zweig dahinter (} else if (!isOutgoingOnly && ...) bleibt
# unberuehrt -- deshalb endet der Ersatz ohne schliessende Klammer.
DART_ZWEIG_ALT = """      final isOutgoingOnly = bind.isOutgoingOnly();
      if (!(isOutgoingOnly || bind.mainIsCanScreenRecording(prompt: false))) {
        return buildInstallCard("Permissions", "config_screen", "Configure",
            () async {
          bind.mainIsCanScreenRecording(prompt: true);
          watchIsCanScreenRecording = true;
        }, help: 'Help', link: translate("doc_mac_permission"));
      } else if (!isOutgoingOnly && !bind.mainIsProcessTrusted(prompt: false)) {
        return buildInstallCard("Permissions", "config_acc", "Configure",
            () async {
          bind.mainIsProcessTrusted(prompt: true);
          watchIsProcessTrust = true;
        }, help: 'Help', link: translate("doc_mac_permission"));
      } else if (!bind.mainIsCanInputMonitoring(prompt: false)) {
        return buildInstallCard("Permissions", "config_input", "Configure",
            () async {
          bind.mainIsCanInputMonitoring(prompt: true);
          watchIsInputMonitoring = true;
        }, help: 'Help', link: translate("doc_mac_permission"));
      } else if (!isOutgoingOnly &&
"""

DART_ZWEIG_NEU = """      final isOutgoingOnly = bind.isOutgoingOnly();
      // ===== GEFUEHRTE BERECHTIGUNG 2026-10-02 =====
      // Vorher: drei Karten nacheinander, jede mit einem Knopf, den der
      // Anwender finden und druecken muss, ohne Fortschritt und ohne
      // Weiterspringen. Jetzt ein Ablauf, der von selbst laeuft.
      final freigaben = _macFreigabeSchritte();
      if (freigaben.any((f) => !f.erteilt)) {
        return _buildGefuehrteFreigabe(freigaben);
      } else if (!isOutgoingOnly &&
"""

DART_METHODEN_ALT = "  Widget buildInstallCard(String title, String content, String btnText,\n"

DART_METHODEN_NEU = """  // ===== GEFUEHRTE BERECHTIGUNG 2026-10-02 =====
  // Die TCC-Freigaben, die dieser Client auf macOS braucht, in der
  // Reihenfolge des gefuehrten Ablaufs.
  //
  // Bedienungshilfen stehen ABSICHTLICH vor der Bildschirmaufnahme --
  // anders als im unveraenderten Quelltext, der mit der Bildschirmaufnahme
  // beginnt. Grund: AXIsProcessTrusted() liest den TCC-Zustand ohne
  // Zwischenspeicher und schlaegt deshalb am verlaesslichsten um. Der
  // Anwender erlebt das automatische Weiterspringen damit am stabilsten
  // Schritt zum ersten Mal; blieb der erste Schritt haengen, waere der
  // ganze Ablauf entwertet.
  //
  // Die isOutgoingOnly-Vorbehalte sind woertlich die des unveraenderten
  // Quelltextes: Bildschirmaufnahme und Bedienungshilfen nur, wenn dieser
  // Client auch Steuerung ANNIMMT; Eingabeueberwachung immer.
  List<_MacFreigabe> _macFreigabeSchritte() {
    final isOutgoingOnly = bind.isOutgoingOnly();
    final liste = <_MacFreigabe>[];
    if (!isOutgoingOnly) {
      liste.add(_MacFreigabe(
          'acc',
          'guided_perm_acc',
          'config_acc',
          bind.mainIsProcessTrusted(prompt: false),
          () => bind.mainIsProcessTrusted(prompt: true)));
      liste.add(_MacFreigabe(
          'screen',
          'guided_perm_screen',
          'config_screen',
          bind.mainIsCanScreenRecording(prompt: false),
          () => bind.mainIsCanScreenRecording(prompt: true)));
    }
    liste.add(_MacFreigabe(
        'input',
        'guided_perm_input',
        'config_input',
        bind.mainIsCanInputMonitoring(prompt: false),
        () => bind.mainIsCanInputMonitoring(prompt: true)));
    return liste;
  }

  // Billiger Vergleichswert ueber alle Freigaben, nur fuer die Schleife.
  String _macFreigabeFingerabdruck(List<_MacFreigabe> freigaben) =>
      freigaben.map((f) => f.erteilt ? '1' : '0').join();

  Widget _buildGefuehrteFreigabe(List<_MacFreigabe> freigaben) {
    final offen = freigaben.where((f) => !f.erteilt).toList();
    if (offen.isEmpty) {
      // Kann der Aufrufer nicht herbeifuehren, aber ein Absturz an dieser
      // Stelle waere eine leere Oberflaeche statt eines Hinweises.
      return const SizedBox();
    }
    final erteilt = freigaben.length - offen.length;
    if (_macFreigabeGesamt == 0) {
      _macFreigabeGesamt = offen.length;
      _macFreigabeVorherErteilt = erteilt;
      _macFreigabeStand = _macFreigabeFingerabdruck(freigaben);
    }
    _macFreigabeLaeuft = true;

    final aktuell = offen.first;
    var nummer = erteilt - _macFreigabeVorherErteilt + 1;
    if (nummer < 1) {
      nummer = 1;
    }
    if (nummer > _macFreigabeGesamt) {
      nummer = _macFreigabeGesamt;
    }

    // Der Sprung passiert von selbst -- aber genau EINMAL je Schritt.
    // Nicht im Aufbau selbst: ein Seiteneffekt im build() liefe bei jedem
    // Neuzeichnen erneut.
    if (!_macFreigabeGesprungen.contains(aktuell.schluessel)) {
      _macFreigabeGesprungen.add(aktuell.schluessel);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        aktuell.sprung();
      });
    }

    final weissBlass = Colors.white.withOpacity(0.75);
    final inhalt = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          '${translate("guided_step")} ${nummer} ${translate("guided_step_of")} ${_macFreigabeGesamt}',
          style: TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.bold,
              fontSize: 13),
        ).marginOnly(bottom: 8),
        Text(
          translate(aktuell.begruendung),
          style: TextStyle(
              height: 1.5,
              color: Colors.white,
              fontWeight: FontWeight.normal,
              fontSize: 13),
        ).marginOnly(bottom: 4),
        Text(
          translate('guided_perm_auto'),
          style: TextStyle(
              height: 1.5,
              color: weissBlass,
              fontStyle: FontStyle.italic,
              fontSize: 12),
        ).marginOnly(bottom: 10),
        // Die Liste aller Schritte mit Haken. Sie beantwortet dem Anwender
        // "wie viel noch", ohne dass er es zaehlen muss.
        ...freigaben.map((f) {
          final istAktuell = f.schluessel == aktuell.schluessel;
          return Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: <Widget>[
              Icon(
                f.erteilt
                    ? Icons.check_circle
                    : (istAktuell
                        ? Icons.radio_button_checked
                        : Icons.radio_button_unchecked),
                color: f.erteilt ? Colors.white : weissBlass,
                size: 16,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  translate(f.name),
                  style: TextStyle(
                      color: f.erteilt || istAktuell ? Colors.white : weissBlass,
                      fontWeight:
                          istAktuell ? FontWeight.bold : FontWeight.normal,
                      fontSize: 12),
                ),
              ),
            ],
          ).marginOnly(bottom: 4);
        }),
      ],
    );

    // immerAnzeigen: diese Karte ist der EINZIGE Hinweis darauf, dass ohne
    // die Freigaben nichts geht. Sie darf nicht an hide-help-cards
    // scheitern -- upstream macht fuer install_daemon_tip dieselbe
    // Ausnahme, aus demselben Grund.
    //
    // Kein help/link mehr: der Ablauf ersetzt die Anleitung, und
    // doc_mac_permission zeigt auf rustdesk.com -- in einem Kundenbau die
    // falsche Marke.
    return buildInstallCard(
      "Permissions",
      "",
      "Configure",
      () async {
        // Rueckfallweg von Hand: wenn der automatische Sprung nichts
        // geoeffnet hat oder der Anwender das Fenster geschlossen hat.
        aktuell.sprung();
      },
      inhaltWidget: inhalt,
      immerAnzeigen: true,
    );
  }

  Widget buildInstallCard(String title, String content, String btnText,
"""

DART_SIGNATUR_ALT = """      {double marginTop = 20.0,
      String? help,
      String? link,
      bool? closeButton,
      String? closeOption}) {
    if (bind.mainGetBuildinOption(key: kOptionHideHelpCards) == 'Y' &&
        content != 'install_daemon_tip') {
      return const SizedBox();
    }
"""

DART_SIGNATUR_NEU = """      {double marginTop = 20.0,
      String? help,
      String? link,
      bool? closeButton,
      String? closeOption,
      // GEFUEHRTE BERECHTIGUNG 2026-10-02
      Widget? inhaltWidget,
      bool immerAnzeigen = false}) {
    if (bind.mainGetBuildinOption(key: kOptionHideHelpCards) == 'Y' &&
        content != 'install_daemon_tip' &&
        !immerAnzeigen) {
      return const SizedBox();
    }
"""

DART_INHALT_ALT = """                      <Widget>[
                        if (content.isNotEmpty)
                          Text(
                            translate(content),
                            style: TextStyle(
                                height: 1.5,
                                color: Colors.white,
                                fontWeight: FontWeight.normal,
                                fontSize: 13),
                          ).marginOnly(bottom: 20)
                      ] +
"""

DART_INHALT_NEU = """                      <Widget>[
                        // GEFUEHRTE BERECHTIGUNG: ein fertiges Widget statt
                        // eines Uebersetzungsschluessels, wenn der Aufrufer
                        // mehr als einen Absatz braucht (Fortschritt,
                        // Schrittliste). translate() auf eine
                        // zusammengesetzte Zeichenkette waere der falsche
                        // Weg: der Platzhaltergriff in lang.rs wuerde eine
                        // geschweifte Klammer im Text als Platzhalter lesen.
                        if (inhaltWidget != null)
                          inhaltWidget.marginOnly(bottom: 20)
                        else if (content.isNotEmpty)
                          Text(
                            translate(content),
                            style: TextStyle(
                                height: 1.5,
                                color: Colors.white,
                                fontWeight: FontWeight.normal,
                                fontSize: 13),
                          ).marginOnly(bottom: 20)
                      ] +
"""

DART_SCHLEIFE_ALT = """      if (watchIsCanScreenRecording) {
        if (bind.mainIsCanScreenRecording(prompt: false)) {
          watchIsCanScreenRecording = false;
          setState(() {});
        }
      }
"""

DART_SCHLEIFE_NEU = """      // ===== GEFUEHRTE BERECHTIGUNG 2026-10-02 =====
      // Die Schleife des gefuehrten Ablaufs. Sie laeuft NUR, solange der
      // Ablauf sichtbar ist (_macFreigabeLaeuft), und zeichnet neu, sobald
      // sich an irgendeiner Freigabe etwas geaendert hat -- daraus ergibt
      // sich das automatische Weiterspringen von selbst, weil buildHelpCards
      // dann den naechsten offenen Schritt waehlt.
      //
      // Dass das ueberhaupt umschlagen kann, haengt an der lebendigen
      // Messung in macos.mm: auf CGPreflightScreenCaptureAccess() allein
      // waere der Zustand pro Prozesslauf eingefroren.
      if (isMacOS && _macFreigabeLaeuft) {
        final freigaben = _macFreigabeSchritte();
        final stand = _macFreigabeFingerabdruck(freigaben);
        if (stand != _macFreigabeStand) {
          _macFreigabeStand = stand;
          if (!stand.contains('0')) {
            // Alles erteilt: Schleife aus, damit eine fertig eingerichtete
            // Maschine keine FFI-Aufrufe pro Sekunde mehr zahlt.
            _macFreigabeLaeuft = false;
            // Und den Ablauf zuruecksetzen. Nimmt der Anwender eine Freigabe
            // spaeter wieder weg, soll der Ablauf von vorne zaehlen und
            // erneut springen -- sonst stuende dort "Schritt 2 von 2" fuer
            // einen Ablauf, der gerade erst anfaengt.
            _macFreigabeGesamt = 0;
            _macFreigabeVorherErteilt = 0;
            _macFreigabeGesprungen.clear();
          }
          setState(() {});
        }
      }
      if (watchIsCanScreenRecording) {
        if (bind.mainIsCanScreenRecording(prompt: false)) {
          watchIsCanScreenRecording = false;
          setState(() {});
        }
      }
"""


def plane_dart():
    pfad = DART_DATEI
    s = lies(pfad)
    if MARKE in s:
        abbruch("%s traegt die Marke %r schon -- zweiter Lauf." % (pfad, MARKE))
    s = ersetze(s, DART_KLASSE_ALT, DART_KLASSE_NEU, pfad, "Klasse _MacFreigabe")
    s = ersetze(s, DART_FELD_ALT, DART_FELD_NEU, pfad, "Zustandsfelder")
    s = ersetze(s, DART_ZWEIG_ALT, DART_ZWEIG_NEU, pfad, "macOS-Zweig in buildHelpCards")
    s = ersetze(s, DART_METHODEN_ALT, DART_METHODEN_NEU, pfad, "Ablauf-Methoden")
    s = ersetze(s, DART_SIGNATUR_ALT, DART_SIGNATUR_NEU, pfad, "buildInstallCard-Signatur")
    s = ersetze(s, DART_INHALT_ALT, DART_INHALT_NEU, pfad, "buildInstallCard-Inhalt")
    s = ersetze(s, DART_SCHLEIFE_ALT, DART_SCHLEIFE_NEU, pfad, "Abfrageschleife")
    plane(pfad, s)


def pruefe_dart():
    pfad = DART_DATEI
    p = lies(pfad)
    for muss in (
        "class _MacFreigabe {",
        "List<_MacFreigabe> _macFreigabeSchritte()",
        "Widget _buildGefuehrteFreigabe(List<_MacFreigabe> freigaben)",
        "Widget? inhaltWidget,",
        "bool immerAnzeigen = false}) {",
        "if (inhaltWidget != null)",
        "if (isMacOS && _macFreigabeLaeuft) {",
        "addPostFrameCallback",
        "immerAnzeigen: true,",
    ):
        if muss not in p:
            abbruch("%s: %r fehlt nach dem Schreiben." % (pfad, muss))
    # Die drei alten Karten duerfen nicht mehr da sein, sonst waere der
    # gefuehrte Ablauf unerreichbar -- und der Bau trotzdem gruen.
    for darf_nicht in (
        'return buildInstallCard("Permissions", "config_screen", "Configure"',
        'return buildInstallCard("Permissions", "config_acc", "Configure"',
        'return buildInstallCard("Permissions", "config_input", "Configure"',
    ):
        if darf_nicht in p:
            abbruch("%s: alte Berechtigungskarte steht noch drin: %r" % (pfad, darf_nicht))
    if p.count("_macFreigabeSchritte()") < 3:
        abbruch("%s: _macFreigabeSchritte() wird zu selten aufgerufen." % pfad)
    print("  desktop_home_page  OK (gefuehrter Ablauf, Fortschritt, Schleife)")


# ===========================================================================
# 4 -- src/lang/en.rs und src/lang/de.rs
# ===========================================================================
#
# Nur Englisch und Deutsch. translate() faellt fuer eine fehlende Sprache
# erst auf Englisch und dann auf den Schluesseltext selbst zurueck
# (src/lang.rs Z. 254-266) -- 51 Sprachdateien anzufassen waere Umfang, den
# niemand bestellt hat.
#
# KEINE der neuen Zeichenketten enthaelt "RustDesk". Den Namen liefert
# ohnehin die Begruendung (config_acc / config_screen / config_input), die
# ihn schon traegt; ein zweites Vorkommen waere eine zweite Stelle, an der
# der Anzeigename auseinanderlaufen kann.
#
# ----------------------------------------------------------------------
# DER ANKER IST DER SCHLUESSEL, NIE DER TEXT -- hier teuer gelernt.
#
# Die erste Fassung verankerte auf der GANZEN Zeile, einschliesslich des
# uebersetzten Satzes. Lokal gegen den unveraenderten 1.4.9-Baum lief
# das. Im Ablauf brach es ab, auf beiden Architekturen:
#
#   GEFUEHRTEBERECHTIGUNG FEHLER: src/lang/en.rs: Anker fuer lang-Anker
#   en kommt 0 mal vor, erwartet genau 1.
#
# Ursache ist kein Tippfehler, sondern die REIHENFOLGE im Ablauf.
# generator-macos.yml fuehrt im Schritt "Update macOS Info.plist and
# settings" aus:
#
#   find ./src/lang -name "*.rs" -exec sed -i '' -e 's|RustDesk|<appname>|' {} \\;
#
# Dieser Schritt steht VOR dem Schritt, der dieses Skript aufruft. Wenn
# das Skript laeuft, heisst "RustDesk" in en.rs/de.rs also laengst
# IT-Labuhn-Soforthilfe. Ein Anker mit dem Wort "RustDesk" darin KANN
# dort nicht mehr treffen.
#
# Besonders aergerlich: der Absatz darueber nannte genau diesen sed. Es
# wurde ueber die AUSGABE nachgedacht (die neuen Texte enthalten kein
# "RustDesk") und die EINGABE vergessen (der Anker enthielt es).
#
# Die Lehre ist die bekannte, nur eine Ebene hoeher: ein Patcher wird
# nicht gegen den unveraenderten Baum geprueft, sondern gegen den Baum
# IN DEM ZUSTAND, IN DEM ER IHN IM ABLAUF VORFINDET. Dafuer gibt es
# jetzt simuliereAblauf.sh, das die vorangehenden Schritte abspielt.
#
# Daraus die Regel, die dieses Skript jetzt einhaelt: verankert wird am
# Uebersetzungs-SCHLUESSEL, den das Branding nie anfasst -- nie am
# uebersetzten Text, der es immer werden kann. Die Einfuegung ist
# zeilenweise und liest den Text ueberhaupt nicht.
# ----------------------------------------------------------------------

# Nur der Schluessel. Unveraenderlich gegenueber jedem Branding-sed.
LANG_ANKER = '("config_input",'

EN_NEU_ZEILEN = [
    '        ("guided_step", "Step"),',
    '        ("guided_step_of", "of"),',
    '        ("guided_perm_acc", "Accessibility"),',
    '        ("guided_perm_screen", "Screen Recording"),',
    '        ("guided_perm_input", "Input Monitoring"),',
    '        ("guided_perm_auto", "Turn on the switch in System Settings. '
    'This window continues on its own."),',
]

DE_NEU_ZEILEN = [
    '        ("guided_step", "Schritt"),',
    '        ("guided_step_of", "von"),',
    '        ("guided_perm_acc", "Bedienungshilfen"),',
    '        ("guided_perm_screen", "Bildschirmaufnahme"),',
    '        ("guided_perm_input", "Eingabeüberwachung"),',
    '        ("guided_perm_auto", "Schalter in den Systemeinstellungen '
    'einschalten. Dieses Fenster geht von selbst weiter."),',
]

NEUE_SCHLUESSEL = (
    "guided_step",
    "guided_step_of",
    "guided_perm_acc",
    "guided_perm_screen",
    "guided_perm_input",
    "guided_perm_auto",
)


def plane_lang(pfad, neue_zeilen, sprache):
    s = lies(pfad)
    for k in NEUE_SCHLUESSEL:
        if '("%s"' % k in s:
            abbruch("%s: Schluessel %r existiert schon." % (pfad, k))

    # Zeilenweise und ausschliesslich am Schluessel. Der uebersetzte Text
    # wird nicht gelesen -- er darf vom Branding beliebig umgeschrieben
    # worden sein.
    zeilen = s.split("\n")
    treffer = [i for i, z in enumerate(zeilen) if z.lstrip().startswith(LANG_ANKER)]
    if len(treffer) != 1:
        abbruch(
            "%s: Zeile mit %s kommt %d mal vor, erwartet genau 1.\n"
            "  Der Anker ist der Uebersetzungsschluessel, nicht der Text --\n"
            "  wenn er fehlt, hat upstream den Schluessel umbenannt."
            % (pfad, LANG_ANKER, len(treffer))
        )
    i = treffer[0]
    zeilen[i + 1 : i + 1] = list(neue_zeilen)
    plane(pfad, "\n".join(zeilen))


def pruefe_lang(pfad, sprache):
    p = lies(pfad)
    for k in NEUE_SCHLUESSEL:
        if p.count('("%s"' % k) != 1:
            abbruch("%s: Schluessel %r nicht genau einmal vorhanden." % (pfad, k))
    print("  lang/%-13s OK (%d Schluessel)" % (sprache + ".rs", len(NEUE_SCHLUESSEL)))


def main():
    print("GEFUEHRTE BERECHTIGUNG 2026-10-02 -- Patch laeuft")
    print("  cwd = %s" % os.getcwd())

    # Stufe 1: alle Anker pruefen, alle Inhalte im Speicher bauen.
    # Bricht hier etwas ab, ist KEINE Datei angefasst.
    plane_mm()
    plane_rs()
    plane_dart()
    plane_lang(EN_DATEI, EN_NEU_ZEILEN, "en")
    plane_lang(DE_DATEI, DE_NEU_ZEILEN, "de")
    print("  Stufe 1  alle %d Anker gefunden, nichts geschrieben" % len(PLAN))

    # Stufe 2: schreiben, dann von der Platte gegenlesen.
    schreibe_plan()
    pruefe_mm()
    pruefe_rs()
    pruefe_dart()
    pruefe_lang(EN_DATEI, "en")
    pruefe_lang(DE_DATEI, "de")
    print("GEFUEHRTE BERECHTIGUNG -- alle 5 Dateien geaendert und gegengelesen")


if __name__ == "__main__":
    main()
