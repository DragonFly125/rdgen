#!/usr/bin/env python3
"""IDSTABIL-MAC 2026-10-08 -- jede Variante bekommt ihre EIGENE, stabile Kennung.

Befund am echten Mac (IT.EckSe-Test, 08.10.2026): QuickSupport-App und
installierte App zeigten DIESELBE Kennung. Ursache im unveraenderten RustDesk
1.4.9: libs/hbb_common/src/config.rs get_id() -> gen_id() -> get_auto_id()
leitet die Kennung allein aus der MAC-Adresse ab. Die beiden Varianten haben
zwar getrennte Konfigurationsordner (APP_NAME), rechnen aber dieselbe Zahl
aus. Der Server fuehrt dann EINE Geraetezeile, und die Soforthilfe erscheint
nie als "Quick Support".

Windows hat das seit IDSTABIL0925 geloest (bau-lokal.ps1 Schritt 3e). Dieser
Schritt uebertraegt denselben Rust-Schnipsel:

    Kennung = 1e9 + SHA-256("IT-Labuhn-ID-v1"|machine_uid|host|APP_NAME|Saat)[0..8] mod 1e9

machine_uid ist auf macOS die IOPlatformUUID (rustdesk-org/machine-uid), sie
ueberlebt Neuinstallation und das Loeschen der Konfiguration.

EINE bewusste Abweichung von Windows: auf macOS geht der Rechnername NICHT
ein. Windows braucht ihn gegen Vollklone mit gleicher MachineGuid; auf macOS
liefert gethostname() je nach Netz unterschiedliche Namen (DHCP/Bonjour).
Erzeugen root (pkg-postinstall `--assign`) und der angemeldete Nutzer ihre
Kennung zu verschiedenen Zeitpunkten in verschiedenen Netzen, haetten sie
sonst verschiedene Kennungen - und die Zuordnung liefe ins Leere.

Zusaetzlich wird der Vorgabewert von APP_NAME auf den Laufzeitnamen gesetzt
(wie Windows Schritt 3b): zur Laufzeit setzt ihn ohnehin custom_.txt
(app-name), aber die Kennung darf NICHT davon abhaengen, ob diese Datei
gelesen wurde - sonst haetten beide Varianten wieder "RustDesk".

Jede Ersetzung muss GENAU einmal greifen, sonst rot (kein stiller Durchlauf).
"""
import os
import re
import sys

PFAD = os.environ.get("CONFIG_RS", "./libs/hbb_common/src/config.rs")
APPNAME = os.environ.get("APPNAME", "").strip()

if not APPNAME or APPNAME.lower() == "rustdesk" or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", APPNAME):
    sys.exit("ABBRUCH: APPNAME fehlt oder ist unzulaessig: %r" % APPNAME)

with open(PFAD, encoding="utf-8") as f:
    src = f.read()

HELFER = '''    // ---- IT-LABUHN IDSTABIL0925 / IDSTABIL-MAC ----------------------
    // Kennung aus Maschinenkennung + Laufzeitnamen, nicht aus der MAC.
    // `seed` ist leer bei der ERSTEN Erzeugung und sonst die bisherige
    // Kennung - damit wird update_id() eine deterministische Kette statt
    // eines Zufallssprungs.
    #[cfg(not(any(target_os = "android", target_os = "ios")))]
    fn itl_stable_id_from(seed: &str) -> Option<String> {
        use sha2::Digest;
        let machine = machine_uid::get().ok()?;
        if machine.trim().is_empty() {
            return None;
        }
        let app = APP_NAME.read().unwrap().clone();
        if app.trim().is_empty() {
            return None;
        }
        // macOS: Rechnername bewusst NICHT (netzabhaengig), siehe
        // .github/patches/stabileKennung.py.
        #[cfg(target_os = "macos")]
        let host = String::new();
        #[cfg(not(target_os = "macos"))]
        let host = whoami::fallible::hostname().unwrap_or_default();
        let mut h = sha2::Sha256::new();
        h.update(b"IT-Labuhn-ID-v1");
        h.update([0u8]);
        h.update(machine.as_bytes());
        h.update([0u8]);
        h.update(host.as_bytes());
        h.update([0u8]);
        h.update(app.as_bytes());
        h.update([0u8]);
        h.update(seed.as_bytes());
        let d = h.finalize();
        let mut n: u64 = 0;
        for b in d.iter().take(8) {
            n = (n << 8) | (*b as u64);
        }
        Some((1_000_000_000u64 + n % 1_000_000_000u64).to_string())
    }

    #[cfg(any(target_os = "android", target_os = "ios"))]
    fn itl_stable_id_from(_seed: &str) -> Option<String> {
        None
    }

    fn get_auto_id() -> Option<String> {
'''

VORRANG = '''            if let Some(stable) = Self::itl_stable_id_from("") {
                log::info!("Generated stable id {}", stable);
                return Some(stable);
            }
            let mut id = 0u32;
'''

ERSETZUNGEN = [
    ("APP_NAME-Vorgabe",
     '    pub static ref APP_NAME: RwLock<String> = RwLock::new("RustDesk".to_owned());\n',
     '    pub static ref APP_NAME: RwLock<String> = RwLock::new("%s".to_owned());\n' % APPNAME),
    ("Hilfsfunktion vor get_auto_id", "    fn get_auto_id() -> Option<String> {\n", HELFER),
    ("Vorrang in get_auto_id", "            let mut id = 0u32;\n", VORRANG),
    ("Kette in update_id",
     "        let new_id = rng.gen_range(1_000_000_000..2_000_000_000).to_string();\n",
     "        let new_id = Self::itl_stable_id_from(&id)\n"
     "            .unwrap_or_else(|| rng.gen_range(1_000_000_000..2_000_000_000).to_string());\n"),
]

for name, alt, neu in ERSETZUNGEN:
    n = src.count(alt)
    if n != 1:
        sys.exit("ABBRUCH: %s - Anker %d mal gefunden (erwartet genau 1)" % (name, n))
    src = src.replace(alt, neu)
    print("%-32s 1 Ersetzung" % name)

# Gegenpruefung am ERGEBNIS, beide Richtungen
for muss in ('fn itl_stable_id_from(seed: &str) -> Option<String>',
             'let machine = machine_uid::get().ok()?;',
             'let app = APP_NAME.read().unwrap().clone();',
             'h.update(app.as_bytes());',
             'h.update(b"IT-Labuhn-ID-v1");',
             'if let Some(stable) = Self::itl_stable_id_from("")',
             'let new_id = Self::itl_stable_id_from(&id)',
             'RwLock::new("%s".to_owned())' % APPNAME):
    if muss not in src:
        sys.exit("ABBRUCH: Gegenpruefung - %r fehlt in config.rs" % muss)
for darf_nicht in ('RwLock::new("RustDesk".to_owned())',
                   "        let new_id = rng.gen_range(1_000_000_000..2_000_000_000).to_string();\n"):
    if darf_nicht in src:
        sys.exit("ABBRUCH: Gegenpruefung - %r steht noch in config.rs" % darf_nicht.strip())

with open(PFAD, "w", encoding="utf-8") as f:
    f.write(src)
print("IDSTABIL-MAC: Kennung = machine_uid + APP_NAME '%s' (Rueckfall MAC nur ohne machine_uid)" % APPNAME)
