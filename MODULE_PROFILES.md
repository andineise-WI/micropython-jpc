# SAI Module Profiles - Identity & Configuration

Diese Dokumentation beschreibt die Module-Profile für die automatische Adressierung und CANopen-Konfiguration der SAI Sub-Bus Module.

## Übersicht der Module

Module werden durch ihre CANopen Identity-Objekte (0x1018:2 und 0x1018:3) identifiziert. Jedes known Modul hat ein Profil mit zugehörigen SDO-Parametern.

## Module und ihre Identitätssignaturen

### 1. **8DI** - 8 Digital Inputs
- **Identität**: `(1, 0x00010006)`
- **Beschreibung**: 8 digitale Eingänge mit Filterung
- **Konfiguration**:
  - `0x2000:0` = `0x00` - Desina-Konfiguration aktivieren
  - `0x2007:1` = `0x55` - Filtereinstellung 1 (5ms pro Eingang)
  - `0x2007:2` = `0x55` - Filtereinstellung 2 (5ms pro Eingang)
- **OD-Parameter**: Digitale Input-Konfiguration, Filter pro Kanal

---

### 2. **8DO** - 8 Digital Outputs
- **Identität**: `(5, 0x0001000A)`
- **Beschreibung**: 8 digitale Ausgänge mit Fehlersicherung
- **Konfiguration**:
  - `0x2005:0` = `0x00` - Output-Fehlerverhalten (Standard: keine Sicherheitsreaktion)
  - `0x2006:0` = `0x00` - Sicherer Zustand (Standard: alle aus)
- **OD-Parameter**: Output-Steuerung, Fehlverhalten, sicherer Zustand

---

### 3. **8DIO** - 8 Digital In/Outputs
- **Identität**: `(2, 0x00010007)`
- **Beschreibung**: 8 digitale Ein-/Ausgänge kombiniert
- **Konfiguration**:
  - `0x2000:0` = `0x00` - Input-Desina-Konfiguration
  - `0x2001:0` = `0x00` - Output-Konfiguration
  - `0x2005:0` = `0x00` - Output-Fehlerverhalten
  - `0x2006:0` = `0x00` - Sicherer Zustand
  - `0x2007:1` = `0x55` - Filter Input 1
  - `0x2007:2` = `0x55` - Filter Input 2
- **OD-Parameter**: Kombinierte Input/Output-Konfiguration mit Filtern

---

### 4. **4AI** - 4 Analog Inputs
- **Identität**: `(3, 0x00010008)`
- **Beschreibung**: 4 analoge Eingänge (z.B. Temperatur, 0-10V, 4-20mA)
- **Konfiguration**:
  - `0x2002:0` = `0x05` - Zykluszeit (5ms)
  - `0x2004:0` = `0x00` - Analoge Input-Konfiguration (Standard)
- **OD-Parameter**: Messbereiche, Zykluszeit, Kalibrierung

---

### 5. **4AO** - 4 Analog Outputs
- **Identität**: `(4, 0x00010009)`
- **Beschreibung**: 4 analoge Ausgänge (0-10V, 4-20mA)
- **Konfiguration**:
  - `0x2003:0` = `0x00` - Output-Konfiguration (Standard)
  - `0x2005:0` = `0x00` - Output-Fehlerverhalten (Standard)
- **OD-Parameter**: Output-Bereiche, Fehlverhalten

---

### 6. **CNT** - Counter Module
- **Identität**: `(6, 0x0001000B)`
- **Beschreibung**: 2-Kanal Counter/Frequenz-Messmodul
- **Konfiguration**:
  - `0x2101:0` = `0x00` - Programmierbarer Präsetwert
  - `0x2102:1` = `0x00` - Steuerbyte Kanal 1
  - `0x2102:2` = `0x00` - Steuerbyte Kanal 2
  - `0x2103:1` = `0x00` - Statusbyte Kanal 1
  - `0x2103:2` = `0x00` - Statusbyte Kanal 2
  - `0x2105:0` = `0x00` - Einstellungen
- **OD-Parameter**: Zählergrenzwerte, Vergleichswerte, Konfiguration

---

## CANopen Identitäts-Objekt Struktur

Das Identity Object (`0x1018`) hat folgende Subindizes:

| Subindex | Name | Wert | Typ |
|----------|------|------|-----|
| 0 | Anzahl Einträge | 0x04 | UNSIGNED8 |
| 1 | Vendor ID | 0x0000007F | UNSIGNED32 |
| 2 | **Product Code** | Siehe Module oben | UNSIGNED32 |
| 3 | **Revision Number** | Siehe Module oben | UNSIGNED32 |
| 4 | Serial Number | individuell | UNSIGNED32 |

**Die Kombination aus 0x1018:2 und 0x1018:3 identifiziert eindeutig den Modultyp.**

---

## Automatische Adressierung - Process Flow

1. **Phase [1-5]**: Bootloader Addressing (Auto-Addressing mit 0x7FE/0x7FF)
2. **Phase [6]**: CANopen Identity-Abfrage (liest 0x1018 von jedem Knoten)
3. **Phase [7]**: NMT Pre-Operational (Vorbereitung für Parameter)
4. **Phase [8]**: SDO Parameter-Schreibvorgänge basierend auf erkanntem Profil
5. **Phase [9]**: NMT Operational (Aktivierung zyklischer Datenaustausch)
6. **Phase [10]**: Zyklischer Traffic-Monitoring (Verifikation)

---

## Hinweise zum Erweitern von Profilen

Um ein neues Modul hinzuzufügen:

1. **Identität ermitteln**: Lese 0x1018:2 und 0x1018:3 vom neu angeschlossenen Modul
2. **Profile hinzufügen**: Füge einen neuen Eintrag in `MODULE_PROFILES` hinzu mit:
   - Der Identitäts-Tuple `(product_code, revision_number)`
   - `"name"`: Kurze Bezeichnung (z.B. "8DI")
   - `"description"`: Ausführliche Beschreibung
   - `"writes"`: Liste von `(index, subindex, value)` Tupeln
3. **Dokumentation aktualisieren**: Diese Datei mit den neuen Modultypen erweitern

---

## SDO Download Formate

Alle Parameter werden als **1-Byte expedited SDO downloads** geschrieben:

```
Request Frame:
  CAN ID: 0x600 + node_id
  Byte 0: 0x2F (expedited, 1 byte)
  Byte 1: Index (low byte)
  Byte 2: Index (high byte)
  Byte 3: Subindex
  Byte 4: Wert (1 Byte)
  Byte 5-7: 0x00

Response Frame:
  CAN ID: 0x580 + node_id
  Byte 0: 0x60 (ACK)
  Byte 1-7: Echo des Request
```

---

## Trace-Validierung

Die Profile basieren auf der CANopen-Mitschnitt (Trace) für ein System mit:
- 1× 8DI Modul
- 1× 8DO Modul
- 1× Gateway

Die Trace zeigt alle 4 Commissioning-Phasen und wurde als Vorlage für die Parameter verwendet.

---

## Kommando-Referenz für Test/Debugging

```python
# Test einzelnes Modul
from machine import CAN
can = CAN(1, bitrate=250000)

# Debug: CAN-Bus abhören
from test_sai_addressing import debug_can_receive
debug_can_receive(duration_s=10)

# Adressierung mit gesamtem Workflow starten
from test_sai_addressing import test_addressing
test_addressing()
```

---

## Bekannte Module & Dateistruktur

```
Dokumentation:
  sub8di.html  → 8 Digital Inputs
  sub8do.html  → 8 Digital Outputs
  sub8dio.html → 8 Digital In/Outputs
  sub4ai.html  → 4 Analog Inputs
  sub4ao.html  → 4 Analog Outputs
  subcnt.html  → Counter Module
```

---

**Letzte Aktualisierung**: 24. März 2026  
**Datei**: test_sai_addressing.py  
**Modulanzahl**: 6 bekannte Profile
