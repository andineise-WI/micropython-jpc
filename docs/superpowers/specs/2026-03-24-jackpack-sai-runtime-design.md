# Design: JackPack Control – ESP32 SAI CANopen Runtime

**Datum:** 2026-03-24  
**Status:** Genehmigt  
**Hardware:** ESP32-PICO-V3-02, SAI Module (8DI, 8DO, AI, AO, CNT) via CAN 250kbps

---

## 1. Übersicht

Das System besteht aus zwei klar getrennten Schichten:

- **Firmware** (`main.py` + `sai_runtime.py`): Unveränderlich. Übernimmt CAN Auto-Addressing, CANopen Kommunikation, Modul-Identifikation, I/O-Map-Aufbau und den SPS-Scan-Zyklus.
- **Anwenderprogramm** (`user_program.py`): Vom End-User im Browser via Blockly Web erstellt und per WebSerial (USB) auf den ESP32 übertragen.

---

## 2. Schichtenarchitektur

```
┌─────────────────────────────────────────────┐
│  BLOCKLY WEB (Browser)                      │
│  setup() / loop() Blöcke                    │
│  → erzeugt user_program.py                  │
│  → überträgt via WebSerial (USB)            │
└──────────────────┬──────────────────────────┘
                   │ USB / WebSerial
┌──────────────────▼──────────────────────────┐
│  ESP32 FILESYSTEM                           │
│  main.py          ← Firmware (unveränderlich)│
│  sai_runtime.py   ← CANopen Library         │
│  user_program.py  ← Blockly-Programm        │
└──────────────────┬──────────────────────────┘
                   │ import
┌──────────────────▼──────────────────────────┐
│  FIRMWARE (main.py + sai_runtime.py)        │
│  Phase 1: CAN Auto-Addressing (immer)       │
│  Phase 2: App-Start (0x77F + 0x7FE[0x83])  │
│  Phase 3: Modul-Erkennung (Heartbeats)      │
│  Phase 4: Identity-Query (SDO 0x1018:2,3)  │
│  Phase 5: Parametrierung (SDO writes)       │
│  Phase 6: I/O-Map aufbauen + SPS-Loop       │
└──────────────────┬──────────────────────────┘
                   │ CAN 250kbps (GPIO4 RX, GPIO5 TX)
┌──────────────────▼──────────────────────────┐
│  SAI Module (DI, DO, AI, AO, CNT)          │
└─────────────────────────────────────────────┘
```

---

## 3. Boot-Ablauf (immer sequenziell, blocking)

```
Power ON
  Phase 1: NMT Reset → Bootup-Nachrichten empfangen (0x7FF)
           → Node-ID vergeben + Switch-on + App-Start
  Phase 2: App-Start Broadcast (0x77F[0x7F] + 0x7FE[0x83 nid])
  Phase 3: Heartbeat-Listen (0x700+nid, ~400-600ms warten)
  Phase 4: SDO Identity-Query (0x1018:2 ProductCode, 0x1018:3 Revision)
           → Modul-Typ bestimmen via MODULE_PROFILES
  Phase 5: SDO Parametrierung (0x2000, 0x2007, 0x2005, 0x2006)
           NMT Operational (0x000[0x01 0x00])
  Phase 6: I/O-Map aufbauen (sortiert nach Node-ID, nach Typ gruppiert)
           user_program.setup() aufrufen
           SPS-Loop starten
```

Kein Fehler → blockiert Blockly-Start. Fehlerverhalten: Modul antwortet nicht → Kanäle bleiben 0, Firmware fährt fort.

---

## 4. SPS-Scan-Zyklus

Takt: ~10ms, firmware-gesteuert.

```
LOOP (alle 10ms):
  digital_in[]  ← PDO 0x181+nid lesen (8DI-Module)
  analog_in[]   ← PDO lesen (AI-Module)
  counter[]     ← PDO lesen (CNT-Module)
  user_program.loop() aufrufen
  digital_out[] → PDO 0x201+nid senden (8DO-Module)
  analog_out[]  → PDO senden (AO-Module)
  sleep_ms(10)
```

---

## 5. I/O-Map

Dynamisch aufgebaut nach Phases 3-4. Sortierung nach **Node-ID** (aufsteigend), Gruppierung nach **Modultyp**.

| Array | Quelle | Kanalbreite | Beispiel (2x DI) |
|---|---|---|---|
| `digital_in[1..N]` | alle DI-Module | 8 Bit/Modul | Node1 → [1..8], Node2 → [9..16] |
| `digital_out[1..N]` | alle DO-Module | 8 Bit/Modul | analog |
| `analog_in[1..N]` | alle AI-Module | 1 Wert/Kanal | — |
| `analog_out[1..N]` | alle AO-Module | 1 Wert/Kanal | — |
| `counter[1..N]` | alle CNT-Module | 1 Wert/Kanal | — |

**Nicht vorhandene Kanäle:** Wert `0`, kein Absturz, kein Fehler.

---

## 6. Blockly-Programm-Schnittstelle

Die Firmware erwartet in `user_program.py` genau zwei Funktionen:

```python
# user_program.py – erzeugt von Blockly Web
from sai_runtime import digital_in, digital_out, analog_in, analog_out, counter

def setup():
    # Einmalig beim Start aufgerufen
    pass

def loop():
    # Zyklisch aufgerufen (~10ms)
    if digital_in[1]:
        digital_out[1] = True
```

**Kein `user_program.py`:** Firmware startet mit leerer `setup()`/`loop()` – sicherer Betrieb ohne Anwenderprogramm.

---

## 7. Dateien auf dem ESP32

| Datei | Zweck | Aktualisierung |
|---|---|---|
| `main.py` | Firmware-Einstiegspunkt, SPS-Loop | Nur bei Firmware-Update |
| `sai_runtime.py` | CAN/CANopen Library, I/O-Arrays | Nur bei Firmware-Update |
| `user_program.py` | Blockly-Anwenderprogramm | Bei jedem Deploy via WebSerial |

---

## 8. CAN-Protokoll-Referenz

| Phase | CAN-IDs | Beschreibung |
|---|---|---|
| Addressing | 0x7FF (RX), 0x7FE (TX) | Bootloader Bootup/Assign |
| App-Start | 0x77F, 0x7FE | Broadcast + pro Modul |
| Heartbeat | 0x700+nid | Modul-Erkennung |
| SDO | 0x600+nid (TX), 0x580+nid (RX) | Identity + Parametrierung |
| NMT | 0x000 | Operational Start |
| PDO Input | 0x181+nid | Zyklische Eingangsdaten |
| PDO Output | 0x201+nid | Zyklische Ausgangsdaten |

---

## 9. Bekannte Modul-Profile

Identifikation via `0x1018:2` (ProductCode) + `0x1018:3` (Revision):

| Modultyp | ProductCode | I/O-Typ | Kanäle |
|---|---|---|---|
| SAI-8DI | 0x01 | digital_in | 8 |
| SAI-8DO | 0x05 | digital_out | 8 |
| (weitere aus MODULE_PROFILES) | | | |

---

## 10. Nicht im Scope dieses Designs

- Blockly Web Frontend (separates Projekt)
- WebSerial Transfer-Protokoll (Browser-seitig)
- Firmware OTA-Updates
- WiFi / Netzwerk-Funktionalität
