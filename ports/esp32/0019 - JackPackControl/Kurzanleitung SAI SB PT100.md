

## Dokumentation
Subbus Modul SAI-SB 4PT100

## Inhaltsverzeichnis
- Einleitung.........................................................................................................................................3
1.1 Format der Messwerte...............................................................................................................3
1.1.1 Temperaturen.....................................................................................................................3
1.1.2 Widerstandswerte...............................................................................................................3
1.2 Prozessdaten...............................................................................................................................3
1.3 Diagnose und Fehlermeldungen................................................................................................4
- Funktionsbeschreibung.....................................................................................................................4
2.1 Messwerte..................................................................................................................................4
2.2 Alarme.......................................................................................................................................5
2.3 Weiter Einstellmöglichkeiten....................................................................................................5
- Übersichten.......................................................................................................................................6
3.1 Parameter...................................................................................................................................6
3.2  Messbereiche............................................................................................................................8
3.3 Genauigkeit................................................................................................................................9
3.4 Sensorstrom und Verstärkungsfaktor.........................................................................................9
3.5  Anschlussbelegung.................................................................................................................10
3.5.1 2-Leiter.............................................................................................................................10
3.5.2 3-Leiter.............................................................................................................................10
3.5.3 4-Leiter.............................................................................................................................10
3.5.4 Poti...................................................................................................................................10
## 2/10

## 1. Einleitung
Das   SAI-SB   PT100   Modul   kann   Widerstände   und   Temperaturen   mittels   PT100-
Sensoren/Widerständen messen. Folgende Tabelle gibt noch einen Überblick über die möglichen
## Sensortypen :
SensortypParameterwert
## PT1000
## PT2001
## PT5002
## PT10003
## Ni1004
## Ni1205
## Ni10006
## Widerstand 500 Ohm7
Widerstand 5 kOhm8
## Poti 100 -500 Ohm9
Poti 500-5K10
Poti >5K-11
1.1 Format der Messwerte
Folgend wird das Format und die Skalierung der Messwerte des Moduls beschrieben.
## 1.1.1 Temperaturen
## 1 Bit = 1/10 K
z.B. 0 °C = 0x0000, 1 °C = 0x00a0, 1000 °C = 0x2710
## 1.1.2 Widerstandswerte
Format : 16 bit vorzeichenlos
Bereich 500  Ohm : resolution = 0,01 Ohm -> 1 Bit = 0,01 Ohm
Bereich 5000 Ohm : resolition = 0,1 Ohm -> 1 Bit = 0,1 Ohm
## 1.2 Prozessdaten
Das Modul erzeugt 4 * 16 bit Eingangsdaten, welche bei Veränderung auf den Feldbus übertragen
werden.  Jedes 16 bit Wort entspricht dem Messwert eines Kanals.
## 3/10

1.3 Diagnose und Fehlermeldungen
Das Modul erzeugt 3 Bytes an Diagnosedaten. Folgende Tabelle gibt eine Übersicht:
Nummer des BytesBezeichnung
1.Bereichsüber- und unterschreitung der Messwerte
## Bit 0 : Kanal 1 Bereichsfehler
## Bit 1 : Kanal 2 Bereichsfehler
## Bit 2 : Kanal 3 Bereichsfehler
## Bit 3 : Kanal 4 Bereichsfehler
2.Leitungsbruch-Erkennung
## Bit 0 : Kanal 1 Leitungsbruch
## Bit 1 : Kanal 2 Leitungsbruch
## Bit 2 : Kanal 3 Leitungsbruch
## Bit 3 : Kanal 4 Leitungsbruch
3.Status der Alarme
## Bit 0 : Kanal 1 Alarm1
## Bit 1 : Kanal 2 Alarm1
## Bit 2 : Kanal 3 Alarm1
## Bit 3 : Kanal 4 Alarm1
## Bit 4 : Kanal 1 Alarm2
## Bit 5 : Kanal 2 Alarm2
## Bit 6 : Kanal 3 Alarm2
## Bit 7 : Kanal 4 Alarm2
## 2. Funktionsbeschreibung
## 2.1 Messwerte
Nach Einstellen des Sensortyps für einen Kanal durch Setzen der entsprechenden Parameter des
Kanals   liefert   das     Modul  Messwerte   für   diesen   Kanal.   In   der   Standardeinstellung   sind   die
Messwerte vorzeichenbehaftet und werden in Zweierkomplementärdarstellung ausgegeben. Falls
ein Fehler für den Kanal vorliegt, wird dies über die Diagnosebytes des Moduls signalisiert. Das
Modul besitzt 3 Diagnosebytes, welche sich aus den Bytes der Status-PDO des Moduls, abzüglich
der ersten zwei Bytes, ergeben. Das erste Byte signalisiert in den unteren 4 Bits eine Bereichsüber-
oder unterschreitung des Eingangspegels. Jedes  Bit entspricht dabei einem Kanal. Im 2 Status-Byte
wird ein Fehler in den unteren 4 Bits signalisiert, wenn die Messelektronik einen Leitungsbruch am
entsprechenden Kanal erkennt.
## 4/10
Setzen der Parameter

Für Sensortypen, die eine Temperaturmessung erlauben, ist es durch Setzen des Parameters „output
format temperatures“ möglich, eine Darstellung mittels der Fahrenheit-Skala einzustellen.
Für alle Bereiche, deren Messbereich bipolar ist, kann durch Setzen des Parameters „signes values“
eine vorzeichenlose Darstellung eingestellt werden, bei der der Wert 0 durch den Wert 8000h
(32768 dezimal) dargestellt. Diese Einstellung betrifft auch die Temperaturausgabe (Celsius und
Fahrenheit), sowei die Parametrierung und Auswertung der Alarme.
## 2.2 Alarme
Für jeden Kanal lassen  sich 2 Grenzwerte definieren.  Bei Erreichen  dieser Grenzwerte kann
entweder ein High-Alarm (Überschreitung des Schwellwerts) oder ein Low-Alarm (Unterschreitung
des Messwerts), abhängig von der Parametrierung, signalisiert werden. Zusätzlich besteht noch die
Möglichkeit,   für   jeden   Kanal   eine   Hysterese   für   die   Alarm-Signalisierung   einzustellen.   Die
Signalisierung der Alarme erfolgt durch das 3 Status-Byte des Moduls. Die unteren 4 Bits des Bytes
signalisieren den ALARM1 für die Kanäle 1..4. Die oberen 4 Bits signalisieren den ALARM2 für
## Kanal 1..4.
## 2.3 Weiter Einstellmöglichkeiten
Über den 2. kanalspezifischen Parameter ist es möglich, die Anschlussart des Sonsors zu wählen.
Mögliche Einstellungen sind 2-Leiter-, 3-Leiter- und 4-Leiter-Anschluss. Der 4-Leiter-Anschluss ist
die Standardeinstellung.
Für   jeden   Kanal   kann   weiterhin   über   den   1.   kanalspezifischen   Parameter   die   Wandlungszeit
## 5/10
Setzen der Parameter

eingestellt werden. Dazu müssen die Bits 7-5 entsprechend der folgenden Tabelle gesetzt werden.
WertBedeutung
050+60Hz Unterdrückung, langsam
(Filterzeit d. ADC:300ms / Wandlungszeit ca. 620ms)
150 Hz Unterdrückung, langsam
(Filterzeit:60ms / Wandlungszeit ca. 140ms)
260 Hz Unterdrückung, langsam
(Filterzeit:50ms / Wandlungszeit ca. 120ms)
350+60Hz Unterdrückung, schnell
(Filterzeit:100ms/ Wandlungszeit ca. 220ms)
450 Hz Unterdrückung, schnell
(Filterzeit:20ms/ Wandlungszeit ca. 60ms)
560 Hz Unterdrückung, schnell
(Filterzeit:16,7ms/ Wandlungszeit ca. 54ms)
## 3. Übersichten
## 3.1 Parameter
ParameterFormatBeschreibung
Output format
temperatures
Byte (1. Byte Bit 0)Degree celsius (0=Darstellung in °C,
1=Darstellung in Fahrenheit)
SignedByte (1. Byte Bit 1)Vorzeichen (1=unsigned, 0=signed)
HysteresisByte (1.Byte Bit 7-3)Auswahlmöglichkeit für Hysterese bei
Bewertung   der   Schaltschwellen   der
## Alarm1 / Alarm2 – Meldungen
Sensor type channel 1Byte (2.Byte Bit4-0 )Sensortyp am Kanal 1 (siehe Liste)
Cycle time channel 1Byte (2.Byte Bit7-5)Wandlungszeit Kanal 1 (siehe Liste)
Sensor type channel 2Byte (3.Byte Bit4-0 )Sensortyp am Kanal 2 (siehe Liste)
Cycle time channel 2Byte (3.Byte Bit7-5)Wandlungszeit Kanal 2 (siehe Liste)
Sensor type channel 3Byte (4.Byte Bit4-0 )Sensortyp am Kanal 3 (siehe Liste)
Cycle time channel 3Byte (4.Byte Bit7-5)Wandlungszeit Kanal 3 (siehe Liste)
Sensor type channel 4Byte (5.Byte Bit4-0 )Sensortyp am Kanal 4 (siehe Liste)
Cycle time channel 4Byte (5.Byte Bit7-5)Wandlungszeit Kanal 4 (siehe Liste)
Connection type channel Byte (6.Byte 1-0 )Anschlussart Kanal 1 (2-, 3-, oder 4-
## 6/10

1Leiter)
Alarm 1 mode channel 1Byte (6.Byte Bit3-2)Modus   für   Alarm   1   Kanal   1   (Off,
High-Alarm, Low-Alarm)
Alarm 2 mode channel 1Byte (6.Byte Bit5-4)Modus   für   Alarm   2   Kanal   1   (Off,
High-Alarm, Low-Alarm)
Connection type channel
## 2
Byte (7.Byte 1-0 )Anschlussart Kanal 2 (2-, 3-, oder 4-
## Leiter)
Alarm 1 mode channel 2Byte (7.Byte Bit3-2)Modus   für   Alarm   1   Kanal   2   (Off,
High-Alarm, Low-Alarm)
Alarm 2 mode channel 2Byte (7.Byte Bit5-4)Modus   für   Alarm   2   Kanal   2   (Off,
High-Alarm, Low-Alarm)
Connection type channel
## 3
Byte (8.Byte 1-0 )Anschlussart Kanal 3 (2-, 3-, oder 4-
## Leiter)
Alarm 1 mode channel 3Byte (8.Byte Bit3-2)Modus   für   Alarm   1   Kanal   3   (Off,
High-Alarm, Low-Alarm)
Alarm 2 mode channel 3Byte (8.Byte Bit5-4)Modus   für   Alarm   2   Kanal   3   (Off,
High-Alarm, Low-Alarm)
Connection type channel
## 4
Byte (9.Byte 1-0 )Anschlussart Kanal 4 (2-, 3-, oder 4-
## Leiter)
Alarm 1 mode channel 4Byte (9.Byte Bit3-2)Modus   für   Alarm   1   Kanal   4   (Off,
High-Alarm, Low-Alarm)
Alarm 2 mode channel 4Byte (9.Byte Bit5-4)Modus   für   Alarm   2   Kanal   4   (Off,
High-Alarm, Low-Alarm)
Limit 1 channel 1WortSchwellwert 1 für Alarm1 Kanal 1 (16
bit Wort)
Limit 1 channel 2WortSchwellwert 1 für Alarm1 Kanal 2 (16
bit Wort)
Limit 1 channel 3WortSchwellwert 1 für Alarm1 Kanal 3 (16
bit Wort)
Limit 1 channel 4WortSchwellwert 1 für Alarm1 Kanal 4 (16
bit Wort)
Limit 2 channel 1WortSchwellwert 2 für Alarm1 Kanal 1 (16
bit Wort)
Limit 2 channel 2WortSchwellwert 2 für Alarm1 Kanal 2 (16
bit Wort)
Limit 2 channel 3WortSchwellwert 2 für Alarm1 Kanal 3 (16
bit Wort)
Limit 2 channel 4WortSchwellwert 2 für Alarm1 Kanal 4 (16
bit Wort)
## 7/10

Liste möglicher Werte für Hysterese
## 00
## 15
## 210
## 320
## 430
## 540
## 650
## 760
## 870
## 980
## 1090
## 11100
## 12120
## 13140
## 14160
## 15180
## 16200
## 17300
## 18400
## 19500
## 20600
## 21700
## 22800
## 23900
## 241000
## 251250
## 261500
## 271750
## 282000
## 293000
## 304000
## 315000
## 8/10

## 3.2 Messbereiche
## Sensor-
## Typ
## Beschreibung
θminθmax
## 0PT100-200°C850°C
IEC 60571  α=0,00385°C
## -1
## 1PT200-200°C850°C
IEC 60571  α=0,00385°C
## -1
## 2PT500-200°C850°C
IEC 60571  α=0,00385°C
## -1
## 3PT1000-200°C850°C
IEC 60571  α=0,00385°C
## -1
4Ni100-60°C+250°CDIN43 760  zurückgezogen
5Ni120-80°C+260°C
α=0,00672°C
## -1
Fa.Minco
6Ni1000-60°C+250°CDIN43 760  zurückgezogen
7Widerstand0500 Ohm
8Widerstand05K
9Poti100R-500R
10Poti500R-5K
11Poti5K-10K
## 3.3 Genauigkeit
PT-, Ni-Eingänge < ± 1 °C
sonst. Eingänge :< ± 0,5% (vom Messbereichsendwert)
## Typ
θmax0,5% θmax
PT100850°C1°C=0,38 Ohm
## PT200850°C1°C
## PT500850°C1°C
## PT1000850°C1°C
Ni100250°C1°C
Ni120260°C
## Ni1000
## Widerstand5000 Ohm15 Ohm= 0,3%
## Widerstand500 Ohm1,5 Ohm= 0,3%
## Poti
3.4 Sensorstrom und Verstärkungsfaktor
RmaxI
sensor
I offVuU_FSMessbereichVu
## Rref
## PT100850°C3900,52550,094680,2755508
## PT2007800,52550,094640,5511008
## PT50019500,21020,210240,55275016
## 9/10

## PT100039000,21020,210221,1550016
Ni100+250°C2900,52550,094680,2755508
## Ni1203480,52550,094680,2755508
## Ni100029000,21020,210221,1550016
## Widerstand5000
## Ohm
## 0,21020,210221,1550016
## 500
## Ohm
## 0,52550,094680,2755508
Poti5K-10
## K
## 0,21020,210221,1-
Poti500R-5
## K
## 0,21020,210240,5516
Poti100R-5
## 00R
## 0,52550,094680,2758
## 3.5  Anschlussbelegung
3.5.1 2-Leiter
## M12 Pin1: R+
M12 Pin2: not connected
## M12 Pin3: R-
M12 Pin4: not connected
3.5.2 3-Leiter
## M12 Pin1: R+
## M12 Pin2: Sense+
## M12 Pin3: R-
M12 Pin4: not connected
3.5.3 4-Leiter
## M12 Pin1: R+
## M12 Pin2: Sense+
## M12 Pin3: R-
## M12 Pin4: Sense-
## 3.5.4 Poti
## M12 Pin1: Poti+
## M12 Pin2: Schleifer
## M12 Pin3: Poti -
M12 Pin4: not connected
## 10/10