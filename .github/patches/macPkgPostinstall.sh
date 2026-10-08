#!/bin/bash
# MACPKGASSIGN 2026-10-08 -- postinstall des macOS-Installationspakets.
#
# Gegenstueck zu install-and-assign.ps1 (Windows): ordnet das Geraet direkt
# nach der Installation per `--assign --token` der Kundengruppe zu, an die das
# Onboarding-Token gebunden ist. Ohne diesen Schritt landet eine per DMG
# installierte Mac-App in KEINER Gruppe (Befund IT.EckSe, 07.10.2026).
#
# Warum es so geht (RustDesk 1.4.9, nachgelesen):
#  - src/core_main.rs `--assign`: nur wenn platform::is_installed() && is_root().
#    macOS is_installed() = Programmpfad beginnt mit /Applications/<App>.app,
#    der Installer fuehrt dieses Skript als root aus.
#  - Die Kennung kommt aus ipc::get_id() bzw. Config::get_id(); eine frische
#    macOS-Kennung ist aus der MAC-Adresse abgeleitet und damit fuer root und
#    den angemeldeten Nutzer dieselbe.
#  - Der Server (DeviceCliController::assign) legt die Geraetezeile an, falls
#    es sie noch nicht gibt; ohne device_group_name nimmt er die Tokengruppe.
#
# Das Token steht NICHT in diesem Skript, sondern in der Datendatei
# assign.token neben ihm (eine Datei, kein Code). Es wird nie protokolliert.
# RustDesk nimmt das Token nur als Argument an -- dieselbe Einschraenkung wie
# bei install-and-assign.ps1 unter Windows.
#
# Das Skript bricht die Installation NIE ab: die App ist installiert, auch
# wenn die Zuordnung scheitert. Ergebnis steht in /var/log/it-labuhn-assign.log.

HIER="$(cd "$(dirname "$0")" && pwd)"
PROTOKOLL="/var/log/it-labuhn-assign.log"
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$PROTOKOLL"; }

APPNAME="$(cat "$HIER/app.name" 2>/dev/null)"
TOKENDATEI="$HIER/assign.token"

if [ -z "$APPNAME" ]; then
  log "FEHLER: app.name fehlt im Paket - keine Zuordnung"
  exit 0
fi
if [ ! -s "$TOKENDATEI" ]; then
  log "FEHLER: assign.token fehlt im Paket - keine Zuordnung"
  exit 0
fi

PROGRAMM="/Applications/$APPNAME.app/Contents/MacOS/$APPNAME"
if [ ! -x "$PROGRAMM" ]; then
  log "FEHLER: $PROGRAMM nicht gefunden - keine Zuordnung"
  rm -f "$TOKENDATEI"
  exit 0
fi

TOKEN="$(cat "$TOKENDATEI")"
rm -f "$TOKENDATEI"

# IDSTABIL-MAC: --assign meldet die Kennung aus der root-Konfiguration
# (/var/root/Library/Preferences/com.carriez.<App>). Bleibt dort eine alte
# Kennung von einer frueheren Installation liegen (frueher MAC-abgeleitet),
# wuerde root eine ANDERE Kennung zuordnen als die, mit der sich die App des
# Nutzers meldet. Seit IDSTABIL-MAC ist die Kennung deterministisch
# (Maschinen-UUID + App-Name), root rechnet nach dem Entfernen also dieselbe
# Zahl wie der Nutzer - gleiche Massnahme wie SERVICEHARDEN2 unter Windows.
ROOTKONFIG="/var/root/Library/Preferences/com.carriez.$APPNAME"
case "$APPNAME" in
  ""|*/*|.*) log "FEHLER: unzulaessiger App-Name, root-Konfiguration nicht angefasst" ;;
  *) if [ -d "$ROOTKONFIG" ]; then rm -r -- "$ROOTKONFIG" && log "alte root-Konfiguration entfernt"; fi ;;
esac

KONSOLENNUTZER="$(stat -f %Su /dev/console 2>/dev/null)"
GERAETENAME="$(scutil --get ComputerName 2>/dev/null || hostname)"
NOTIZ="Auto-provisioned by macOS pkg postinstall on $(date '+%Y-%m-%d %H:%M')"

log "Zuordnung startet: App '$APPNAME', Geraet '$GERAETENAME', Nutzer '$KONSOLENNUTZER'"

ERFOLG=0
for VERSUCH in 1 2 3 4 5 6 7 8 9 10; do
  AUSGABE="$("$PROGRAMM" --assign --token "$TOKEN" \
      --device_name "$GERAETENAME" \
      --device_username "$KONSOLENNUTZER" \
      --note "$NOTIZ" 2>&1 | tail -n 3 | tr -d '\r')"
  LETZTE="$(printf '%s' "$AUSGABE" | tail -n 1 | sed 's/[[:space:]]*$//')"
  if [ -z "$LETZTE" ] || [ "${LETZTE%Done!}" != "$LETZTE" ]; then
    log "Zuordnung bestaetigt (Versuch $VERSUCH)"
    ERFOLG=1
    break
  fi
  log "Versuch $VERSUCH nicht bestaetigt: $LETZTE"
  sleep 6
done
TOKEN=""

if [ "$ERFOLG" -ne 1 ]; then
  log "FEHLER: Zuordnung nach 10 Versuchen nicht bestaetigt - Geraet in der Konsole von Hand zuordnen"
fi

# Die App fuer den angemeldeten Nutzer starten, damit er die macOS-Freigaben
# (Bildschirmaufnahme, Bedienungshilfen) erteilen kann. Fehlschlag ist egal.
if [ -n "$KONSOLENNUTZER" ] && [ "$KONSOLENNUTZER" != "root" ]; then
  NUTZERID="$(id -u "$KONSOLENNUTZER" 2>/dev/null)"
  if [ -n "$NUTZERID" ]; then
    launchctl asuser "$NUTZERID" sudo -u "$KONSOLENNUTZER" open -a "/Applications/$APPNAME.app" >/dev/null 2>&1 || true
  fi
fi

exit 0
