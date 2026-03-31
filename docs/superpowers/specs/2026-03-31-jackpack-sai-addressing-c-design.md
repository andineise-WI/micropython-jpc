# Design: Early CAN Auto-Addressing in C (JackPack ESP32)

**Datum:** 2026-03-31
**Status:** Genehmigt
**Autor:** GitHub Copilot

---

## 1. Ziel

Das CAN Auto-Addressing für SAI-Module soll so früh wie möglich im ESP32-Bootprozess in C ausgeführt werden, um keine Bootup-Nachricht zu verpassen. Die Lösung läuft vor der MicroPython-VM und übergibt den laufenden TWAI-Treiber an die Python-Ebene. Die Python-API (`machine.CAN`) bleibt voll erhalten.

---

## 2. Architektur

- **Board-spezifischer Startup-Hook** (`MICROPY_BOARD_STARTUP`):
  - Initialisiert NVS/Flash (wie bisher)
  - Führt `sai_early_addressing()` aus (TWAI-Init, Addressing-State-Machine)
  - TWAI bleibt installiert, wird von Python übernommen
- **State Machine in C** (direkte Übersetzung des funktionierenden Python-Ablaufs):
  - Kein NMT Reset am Anfang
  - Bootup-Loop: 0x7FF empfangen → 0x7FE [0x81,nid] / [0x82,nid]
  - 1s Silence → Addressing abgeschlossen
  - App-Start: 0x77F [0x7F] + 0x7FE [0x83,nid] pro Modul
  - Ergebnis in globale Struct schreiben
- **Ergebnis-Struct**
  - `SAI_MAX_NODES = 16`
  - Enthält Node-IDs und Status
- **Python-API**
  - Optionales Modul `sai.get_nodes()` für Node-Liste
  - `machine.CAN` bleibt unverändert

---

## 3. Dateien/Änderungen

| Datei | Aktion | Zweck |
|---|---|---|
| `ports/esp32/sai_addressing.c` | Neu | C-Implementierung der State Machine |
| `ports/esp32/sai_addressing.h` | Neu | API Header + Ergebnis-Struct |
| `ports/esp32/boards/JACKPACK_ESP32/mpconfigboard.h` | Neu | Board-Profil mit custom Startup |
| `ports/esp32/boards/JACKPACK_ESP32/mpconfigboard.cmake` | Neu | Build-Konfiguration |
| `ports/esp32/machine_can.c` | Ändern | TWAI-Handoff: "already installed" erkennen |

---

## 4. State Machine Ablauf

1. Warte auf erstes Bootup (0x7FF, data[0]==0x01)
2. Adresse zuweisen: 0x7FE [0x81, module_cnt]
3. Warte auf ACK: 0x7FF [0x81, ...]
4. Switch-On: 0x7FE [0x82, module_cnt]
5. Warte auf ACK: 0x7FF [0x82, ...]
6. Warte auf nächstes Bootup oder 1s Timeout
7. App-Start: 0x77F [0x7F] + 0x7FE [0x83, nid] pro Modul

---

## 5. Besonderheiten

- Kein NMT Reset am Anfang
- SAI_MAX_NODES = 16
- machine.CAN bleibt erhalten
- Ergebnis-Struct für Python-API

---

## 6. Offene Punkte

- Optional: Python-API als eigenes Modul oder Attribut von machine.CAN
- Testfälle: Addressing mit 1, 2, 3+ Modulen, kein Modul, fehlerhafte Module

---

**Freigabe:**
- [x] User bestätigt Design
- [ ] Plan schreiben
