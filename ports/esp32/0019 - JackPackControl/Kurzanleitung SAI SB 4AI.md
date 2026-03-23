

## Dokumentation
Subbus Modul SAI-SB 4AI

## Inhaltsverzeichnis
- Einleitung.........................................................................................................................................3
1.1 Messbereiche und Format der Messwerte.................................................................................3
1.2 Prozessdaten...............................................................................................................................3
1.3 Diagnose und Fehlermeldungen................................................................................................3
1.4 Parameter...................................................................................................................................4
- Funktionsbeschreibung.....................................................................................................................4
- Technische Daten.............................................................................................................................4
## 2/4

## 1. Einleitung
Das Subbus-Modul SAI SB 4AI hat 4 analoge Eingänge, über die Spannungen zwischen -10 und
+10 Volt und Ströme zwischen 0 und 20 mA gemessen werden können.
1.1 Messbereiche und Format der Messwerte
Das Modul unterstützt pro Kanal 4 Messbereiche. Folgende Bereiche sind wählbar :
MessbereichWertebereich
0..10 V0 Volt (0x0000) bis 10 Volt (0x07ff)
-10 .. 10 V-10 Volt (0x0000) bis 10 Volt (0xfff)
0..20 mA0 mA (0x0000) bis 20 mA (0x007ff)
4..20 mA4 mA (0x0333) bis 20 mA (0x07ff)
## 1.2 Prozessdaten
Das Modul erzeugt 4 * 16 bit Eingangsdaten, welche bei Veränderung auf den Feldbus übertragen
werden.  Jedes 16 bit Wort entspricht dem Messwert eines Kanals.
1.3 Diagnose und Fehlermeldungen
Das Modul erzeugt 2 Bytes an Diagnosedaten. Folgende Tabelle gibt eine Übersicht:
Nummer des BytesBezeichnung
1.Kurzschluss der Sensorversorgung
## Bit 0 : Anschluss 1 Kurzschluss
## Bit 1 : Anschluss 2 Kurzschluss
## Bit 2 : Anschluss 3 Kurzschluss
## Bit 3 : Anschluss 4 Kurzschluss
2.Bereichsfehler
## Bit 0 : Anschluss 1 Unterschreitung
## Bit 1 : Anschluss 2 Unterschreitung
## Bit 2 : Anschluss 3 Unterschreitung
## Bit 3 : Anschluss 4 Unterschreitung
## Bit 4 : Anschluss 1 Überschreitung
## Bit 5 : Anschluss 2 Überschreitung
## Bit 6 : Anschluss 3 Überschreitung
## Bit 7 : Anschluss 4 Überschreitung
Die Bereichsüberschreitung bzw. Bereichsunterschreitung wird daneben über die Fehler-LEDs der
Kanäle 1 – 4 angezeigt.
## 3/4

## 1.4 Parameter
Folgende Parameter stehen bei dem Subbus-Modul zur Verfügung:
ParameterBeschreibung
MessbereicheEinstellung des Messbereichs für Kanal 1 .. 4
ZykluszeitEinstellung der Wandlungszeit für jeden Kanal
getrennt im Bereich von 5 bis 250 ms
## 2. Funktionsbeschreibung
Nach Einstellen des richtigen Messbereichs und Wählen einer Zykluszeit wird das Modul bei jeder
Änderung am Eingang den Messwert über das Gateway auf den Profibus abbilden. Die Zykluszeit
bestimmt dabei die minimale Zeit, in der eine Änderung am Eingang zu einem neuen Messwert auf
dem Bus führt.
Beim Messbereich 4..20 mA wird unterhalb von 4 mA der Messwert auf 0 geklemmt. Wenn der
Messwert 4 mA erreicht, wird der tasächliche Messwert gemeldet.
Über die Statusdaten des Moduls kann die Bereichsunterschreitung bzw. Bereichsüberschreitung für
jeden Kanal festgestellt werden.
## 3. Technische Daten
Störunterdrückung Differenzeingänge (PIN 2 und PIN 4)
## Analogbandbreite 200 Hz
Abtastintervall für jeden Kanal konfigurierbar 5 ms bis 250 ms
Genauigkeit <0.2% vom Messbereichsendwert
Offsetfehler <0.1% vom Messbereichsendwert
## Linearität <0.05%
Temperaturkoeffizient <300 ppm/K vom Messbereichsendwert
Spannungsbereiche 0 ... +10 V und –10 V ... 10 V
maximale Eingangsspannung
bezogen auf GND±35 V (dauernd)
## Gleichtaktbereich -35 V ... +35 V
Eingangswiderstand >100 kOhm
Auflösung 11 Bit + 1 Bit Vorzeichen (1 LSB = 4.88 mV)
Strombereiche 0 ... 20 mA und 4 ... 20 mA
maximaler Eingangsstrom (differentiell)
- 50 mA ... +50 mA (verpolungssicher),
Schutzabschaltung bei Überschreitung
Eingangswiderstand (Bürde) < 125 Ohm
Auflösung 11 Bit (1 LSB = 9,76 μA )
Potentialtrennung Ein-/Ausgänge
zur Sub-Bus-Spannungnein
zur Sub-Bus-Datenleitungnein
untereinandernein
## 4/4