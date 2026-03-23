

## Dokumentation
Subbus Modul SAI-SB 4AO

## Inhaltsverzeichnis
- Einleitung.........................................................................................................................................3
1.1 Messbereiche und Format der Messwerte.................................................................................3
1.2 Prozessdaten...............................................................................................................................3
1.3 Diagnose und Fehlermeldungen................................................................................................3
1.4 Parameter...................................................................................................................................3
- Funktionsbeschreibung.....................................................................................................................4
- Technische Daten.............................................................................................................................4
## 2/4

## 1. Einleitung
Das Subbus-Modul SAI SB 4AO hat 4 analoge Ausgänge, über die Spannungen zwischen -10 und
+10 Volt und Ströme zwischen 0 und 20 mA ausgegeben werden können.
1.1 Messbereiche und Format der Messwerte
Das Modul unterstützt pro Kanal 4 Ausgangsbereiche. Folgende Bereiche sind wählbar :
MessbereichWertebereich
0..10 V0 Volt (0x0000) bis 10 Volt (0x07ff)
-10 .. 10 V-10 Volt (0x0000) bis 10 Volt (0xfff)
0..20 mA0 mA (0x0000) bis 20 mA (0x0fff)
4..20 mA4 mA (0x0199) bis 20 mA (0x0fff)
## 1.2 Prozessdaten
Das Modul benötigt 4 * 16 bit Eingangsdaten, welche bei Beschreiben zum Setzen der analogen
Ausgänge des Moduls führen.
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
## 1.4 Parameter
Folgende Parameter stehen bei dem Subbus-Modul zur Verfügung:
## 3/4

ParameterBeschreibung
AusgangsbereichEinstellung des Ausgabebereichs für Kanal 1 .. 4
Verhalten       bei
## Fehler
Definition   des   Verhaltens   der   analogen   Ausgänge
bei Fehlern
FehlerzustandFehlerzustand der 4 analogen Ausgänge
## 2. Funktionsbeschreibung
Nach   Einstellen   des   Ausgabebereichs   und   Schreiben   von   Daten   auf   den   entsprechenden
Ausgangsbereich eines Kanals wird der ensprechende Strom- bzw. Spannungswert ausgegeben. Der
unbenutzte   Ausgang  am   Anschluss   (Strom-   bzw.  Spannungsausgang)   wird  mit   entweder   0   Volt
oder 0 mA beschalten.
Beim ausgewählten Bereich von 4 bis 20 mA wird stets mindestens 4 mA am Ausgang ausgegeben.
Falls über die Prozessdaten ein geringerer Wert geschrieben wurde, wird dies als Fehler über die
Fehler-LED und über die Diagnosedaten signalisiert.
Über die Statusdaten des Moduls kann die Bereichsunterschreitung bzw. Bereichsüberschreitung für
jeden Kanal festgestellt werden.
Über   die   Parameter   für   den   sicheren   Zustand   kann   zudem   festgelegt   werden,   wie   die   analogen
Ausgänge   sich   im   Fehlerfall   (fehlende   Komminukation,   Unterspannung   auf   dem   Subbus   ...)
verhalten sollen.
## 3. Technische Daten
## Analogbandbreite 100 Hz
Genauigkeit <0.2% vom Messbereichsendwert
Offsetfehler <0.1% vom Messbereichsendwert
## Linearität <0.05%
Temperaturkoeffizient <300 ppm/K vom Messbereichsendwert
## Kurzschlussfestigkeit Ja
Spannungsbereiche 0 ... +10 V und –10 V ... 10 V
Lastwiderstand >1 kOhm
## Auflösung 11 Bit + 1 Bit Vorzeichen
Ausgang Asymmetrisch (PIN 2)
Strombereiche 0 ... 20 mA und 4 ... 20 mA
## Lastwiderstand < 600 Ohm
## Auflösung 12 Bit
Ausgang Asymmetrisch (PIN 4)
Potentialtrennung Ein-/Ausgänge
zur Sub-Bus-Spannungnein
zur Sub-Bus-Datenleitungnein
untereinandernein
## 4/4