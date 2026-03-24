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
  Phase 1: NMT Reset (0x000[0x81 0x00]) → Bootup-Nachrichten empfangen (0x7FF)
           Jedes SAI-Modul sendet nach Reset eine Bootup-Nachricht auf 0x7FF.
           Firmware wartet bis 1000ms Silence, dann gilt Addressing als abgeschlossen.
           Reihenfolge der Bootups bestimmt Node-ID-Zuweisung (erstes Bootup = Node 1).
           → Adresse vergeben (0x7FE[0x81 nid])
           → Switch-on (0x7FE[0x82 nid])
           → 1s warten auf weitere Bootups, dann App-Start
  Phase 2: App-Start Broadcast: 0x77F[0x7F] (alle Module)
           + pro Modul: 0x7FE[0x83 nid] (Unicast mit nid im Datenbyte)
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
| `digital_out[1..N]` | alle DO-Module | 8 Bit/Modul | Node3 → [1..8], Node4 → [9..16] |
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
| PDO Input DI/DIO | 0x181+nid | 1 Byte: 8 Digital-Eingänge als Bitfeld |
| PDO Input AI | 0x181+nid | 8 Bytes: 4× 16-bit unsigned (Little-Endian) |
| PDO Input CNT | 0x181+nid | 8 Bytes: 2× 32-bit unsigned (Little-Endian) |
| PDO Output DO/DIO | 0x201+nid | 1 Byte: 8 Digital-Ausgänge als Bitfeld |
| PDO Output AO | 0x201+nid | 8 Bytes: 4× 16-bit unsigned (Little-Endian) |

> **PDO-Dekodierung:** Gleiche COB-ID-Familie (0x181+nid), aber unterschiedliche Nutzdatenlängen je nach Typ. Die Firmware kennt den Typ jedes Knotens aus Phase 4 (Identity-Query) und dekodiert den PDO-Inhalt anhand des gespeicherten Modul-Typs – nicht anhand der CAN-ID allein.
| Switch-on | 0x7FE[0x82 nid] | Bootloader: Modul auf Ziel-Node-ID schalten |

---

## 9. Modul-Profile (vollständig)

Identifikation via SDO Upload `0x1018:2` (ProductCode) + `0x1018:3` (Revision).  
Node-IDs werden beim Addressing ab 1 aufsteigend vergeben (max. 127 per CANopen-Standard, praktisch durch CAN-Bus-Last begrenzt).

| Modultyp | ProductCode | Revision | I/O-Array | Kanäle/Modul | Wertebereich |
|---|---|---|---|---|---|
| SAI-8DI | 0x01 | 0x00010006 | `digital_in[]` | 8 | `True`/`False` |
| SAI-8DO | 0x05 | 0x0001000A | `digital_out[]` | 8 | `True`/`False` |
| SAI-8DIO | 0x02 | 0x00010007 | `digital_in[]` + `digital_out[]` | 8+8 | `True`/`False` |

**DIO-Mapping-Beispiel** (Szenario: Node1=8DI, Node2=8DI, Node3=8DIO, Node4=8DO):
- `digital_in[1..8]` ← Node1 (8DI)
- `digital_in[9..16]` ← Node2 (8DI)
- `digital_in[17..24]` ← Node3 (8DIO Eingänge)
- `digital_out[1..8]` ← Node3 (8DIO Ausgänge) ← DIO zählt **separat** in jeder Typen-Liste
- `digital_out[9..16]` ← Node4 (8DO)
| SAI-4AI | 0x03 | 0x00010008 | `analog_in[]` | 4 | `int` 0–65535 (raw 16-bit) |
| SAI-4AO | 0x04 | 0x00010009 | `analog_out[]` | 4 | `int` 0–65535 (raw 16-bit) |
| SAI-CNT | 0x06 | 0x0001000B | `counter[]` | 2 | `int` 0–4294967295 (32-bit) |

### SDO-Parametrierung pro Modul (Phase 5)

**8DI** (`0x01`):
- `0x2000:0x00 = 0x00` — DESINA-Konfiguration (Standard)
- `0x2007:0x01 = 0x55` — Eingangsfilter 1 (5ms/Eingang)
- `0x2007:0x02 = 0x55` — Eingangsfilter 2 (5ms/Eingang)

**8DO** (`0x05`):
- `0x2005:0x00 = 0x00` — Fehlerverhalten Ausgang (Standard)
- `0x2006:0x00 = 0x00` — Sicherheitszustand (alle Ausgänge aus)

**8DIO** (`0x02`):
- `0x2000:0x00 = 0x00`, `0x2001:0x00 = 0x00`, `0x2005:0x00 = 0x00`
- `0x2006:0x00 = 0x00`, `0x2007:0x01 = 0x55`, `0x2007:0x02 = 0x55`

**4AI** (`0x03`):
- `0x2002:0x00 = 0x05` — Zykluszeit 5ms
- `0x2004:0x00 = 0x00` — Analogeingang-Konfiguration (Standard)

**4AO** (`0x04`):
- `0x2003:0x00 = 0x00` — Ausgangs-Konfiguration (Standard)
- `0x2005:0x00 = 0x00` — Fehlerverhalten (Standard)

**CNT** (`0x06`):
- `0x2101:0x00 = 0x00` — Preset-Wert 0
- `0x2102:0x01/0x02 = 0x00` — Control Kanal 1/2
- `0x2103:0x01/0x02 = 0x00` — Status Kanal 1/2
- `0x2105:0x00 = 0x00` — Einstellungen (Standard)

---

## 10. Phase-Timeouts

| Phase | Timeout | Verhalten bei Überschreitung |
|---|---|---|
| Phase 1 – Bootup warten | 1000ms ohne neue Bootup-Nachricht | Addressing abgeschlossen, weiter mit Phase 2 |
| Phase 2 – App-Start warten | 500ms | Weiter mit Phase 3 (Module die nicht antworten erscheinen nicht in Heartbeats) |
| Phase 3 – Heartbeat-Listen | 1000ms | Module die nicht antworten werden mit Kanälen=0 gemappt |
| Phase 4 – SDO Identity | 500ms pro Modul | Modul überspringen, Kanäle=0 |
| Phase 5 – SDO Write | 500ms pro Write | Fehler loggen (Serial), weiter |

---

## 11. API-Kontrakte für sai_runtime.py

### 1-basierte Indizierung
Die I/O-Arrays verwenden 1-basierte Indizes (SPS-Konvention).  
Implementierung: Index `[0]` ist `None`/ungenutzt, oder eine `__getitem__`-Klasse die intern `idx-1` verwendet.  
Empfehlung: Liste mit Padding-Element an Position 0:
```python
digital_in = [None] + [False] * n_channels  # Index 1..n gültig
```

### Mutabilität
`digital_in`, `digital_out`, `analog_in`, `analog_out`, `counter` sind **module-level Listen**, die niemals neu zugewiesen werden – nur in-place mutiert. `from sai_runtime import digital_in` funktioniert daher korrekt.

### Initialzustand
Vor `setup()`: alle `digital_out[]` = `False`, alle `analog_out[]` = `0`. Outputs werden erst nach dem ersten `loop()`-Aufruf auf den CAN-Bus geschrieben.

### Exception-Handling in setup() und loop()
```python
try:
    user_program.setup()
except Exception as e:
    print("USER SETUP ERROR:", e)  # Serial-Ausgabe
    # setup() wird nicht wiederholt, Loop startet trotzdem

# Im Scan-Loop:
try:
    user_program.loop()
except Exception as e:
    print("USER PROGRAM ERROR:", e)  # Serial-Ausgabe
    # Loop weiter – kein Stopp
```

### Zykluszeit
`sleep_ms(10)` am Ende des Loops. Zykluszeit = 10ms + Ausführungszeit von `loop()`. Kein festes Deadline-Scheduling. Für zeitkritische Anwendungen gilt: `loop()` muss schnell sein (<5ms).

### Stale-Values
Wenn kein PDO innerhalb des aktuellen Zyklus empfangen wurde: letzter bekannter Wert wird beibehalten. Beim Start: `0`/`False`.

---

## 12. Nicht im Scope dieses Designs

- Blockly Web Frontend (separates Projekt)
- WebSerial Transfer-Protokoll (Browser-seitig)
- Firmware OTA-Updates
- WiFi / Netzwerk-Funktionalität
