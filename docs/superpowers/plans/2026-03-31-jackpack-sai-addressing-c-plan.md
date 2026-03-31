# JackPack SAI CAN Auto-Addressing (C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
Robuste, früh gestartete CAN Auto-Addressing-Logik für SAI-Module direkt in C, vor MicroPython, mit sauberer Übergabe an die Python-Ebene.

**Architecture:**
- Board-spezifischer Startup-Hook (`MICROPY_BOARD_STARTUP`) ruft C-Addressing-State-Machine auf
- TWAI bleibt installiert, Python übernimmt Treiber
- Ergebnis-Struct für Node-IDs, optional Python-API

**Tech Stack:**
- ESP32 C (ESP-IDF, TWAI)
- MicroPython Port-Architektur
- CMake, Board-Konfiguration

---

### Task 1: Board-Profil anlegen
**Files:**
- Create: `ports/esp32/boards/JACKPACK_ESP32/mpconfigboard.h`
- Create: `ports/esp32/boards/JACKPACK_ESP32/mpconfigboard.cmake`

- [ ] Board-Name, MCU, Startup-Hook setzen
- [ ] CMake-Konfiguration für Build anlegen

---

### Task 2: C-Header & Structs
**Files:**
- Create: `ports/esp32/sai_addressing.h`

- [ ] Ergebnis-Struct und API-Prototypen definieren
- [ ] SAI_MAX_NODES = 16 setzen

---

### Task 3: C-Implementierung State Machine
**Files:**
- Create: `ports/esp32/sai_addressing.c`

- [ ] TWAI-Init (250kbps, GPIO4/5)
- [ ] Addressing-State-Machine (kein NMT Reset)
- [ ] Ergebnis-Struct füllen
- [ ] App-Start-Broadcast
- [ ] TWAI installiert lassen

---

### Task 4: Startup-Hook einbinden
**Files:**
- Modify: `ports/esp32/boards/JACKPACK_ESP32/mpconfigboard.h`
- Create: `ports/esp32/boards/JACKPACK_ESP32/board_init.c`

- [ ] Funktion `jackpack_startup()` implementieren
- [ ] `boardctrl_startup()` + `sai_early_addressing()` aufrufen

---

### Task 5: TWAI Handoff in machine_can
**Files:**
- Modify: `ports/esp32/machine_can.c`

- [ ] Erkennen, ob TWAI schon installiert (durch Addressing)
- [ ] Treiber nicht deinstallieren, sondern übernehmen
- [ ] RX-Queue ggf. leeren

---

### Task 6: Python-API (optional)
**Files:**
- Create: `ports/esp32/sai_py.c` (optional)

- [ ] C-Extension für `sai.get_nodes()`
- [ ] Bindung an Ergebnis-Struct

---

### Task 7: Testfälle & Validierung
**Files:**
- Test: Hardware-Integrationstest, Mitschnitt

- [ ] Test mit 1, 2, 3+ Modulen
- [ ] Test ohne Modul
- [ ] Test mit fehlerhaftem Modul

---

### Task 8: Dokumentation
**Files:**
- Modify: `docs/superpowers/specs/2026-03-31-jackpack-sai-addressing-c-design.md`
- Create: `docs/superpowers/plans/2026-03-31-jackpack-sai-addressing-c-plan.md`

- [ ] Plan und Design aktuell halten

---

Fertig!