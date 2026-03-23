

## Dokumentation
Subbus Modul SAI-SB 4PT100
Heyfra Electronic GmbH
## Herner Str. 5
## 06295 Lutherstadt Eisleben
## Vertraulich

## Autoren
## Torsten Bitterlich
## Freigabe
Geprüft durchVersionUnterschriftFreigegeben
am
## 1.00
## Inhaltsverzeichnis
- Einleitung.........................................................................................................................................3
- Service-Schnittstelle.........................................................................................................................3
- Applikation.......................................................................................................................................3
3.1 Parametrierung...........................................................................................................................4
3.1.1 Manuelle Parametrierung...................................................................................................4
3.1.2 Parameter des Moduls SAI SB 4PT100.............................................................................4
3.2 Prozessdaten...............................................................................................................................9
3.3 Diagnose und Fehlermeldungen................................................................................................9
- Funktionsbeschreibung...................................................................................................................10
4.1 Messwerte................................................................................................................................10
4.1.1 Alarme..............................................................................................................................10
4.1.2 Skalierte Ausgabe............................................................................................................10
4.2 Weiter Einstellmöglichkeiten..................................................................................................11
## Vertraulich
Heyfra Electronic GmbHVersion 1.002/11

## 1. Einleitung
- Service-Schnittstelle
Die Software des PT100/Thermo-Modul besteht aus 3 Teilen. Zum einen der Bootloader, welcher
nach   dem   Aufstarten  des   Moduls   automatisch   gestartet  wird.   Dieser   ermöglicht   die
Programmierung  der  Modulsoftware. Über   den  Bootloader kann  außerdem  entweder  die
Applikation (was in der normalen Anwendung die Standardanwendung ist) oder die Service-
Applikation starten. Mit folgenden Bootloader-Kommandos wird in die Service-Applikation
gesprungen :
1.0x7fe 0x81 modulAdresse
2.0x7fe 0x84 modulAdresse
Danach ist es möglich, beliebige Kommandos direkt an die 4 C51-Prozessoren auf dem Subbus-
Modul zu senden. Dazu ist eine CAN-Nachricht mit der ID 0x7fe mit 8 Datenbytes zu senden. Byte
1 enthält die Adresse des anzusprechenden Controllers (0..3). Die Bytes 2 bis 8 können ein
beliebiges Kommando für diesen Controller enthalten. Die Checksumme muss nicht mit übergeben
werden, da diese die Applikation selbst einfügt.
Folgendes Beispiel liest den Messwert des Controllers 03:
## 0x7fe 0x03 0x01 0x00 0x00 0x00 0x00 0x00 0x00
Als Antwort wird folgende Nachricht gesendet :
## 0x7ff 0x03 0x43 0x10 0x0a 0xfe 0x00 0x00 0x00
Die möglichen Kommandos und deren Aufbau sind der Dokumentation der PT100/Thermo-
Controller-Software zu entnehmen.
## 3. Applikation
Durch folgende Sequenz wird durch den Bootloader die Applikation gestartet:
1.0x7fe 0x81 modulAdresse
## Vertraulich
Heyfra Electronic GmbHVersion 1.003/11

2.0x7fe 0x82 modulAdresse
3.0x7fe 0x83 modulAdresse
Danach befindet die Applikation sich im Zustand PRE_OPERATIONAL. Ein Austausch von
Prozessdaten  erfolgt   in   diesem   Zustand   nicht.   Durch   folgenden  Befehl   wird   in   den
OPERATIONAL Zustand gewechselt:
## 0x0 0x1 0x0
## 3.1 Parametrierung
## 3.1.1 Manuelle Parametrierung
Nach dem Aufstarten der Applikation kann die Parametrierung erfolgen. Die Parameter werden
über SDO-Zugriffe im Objekt-Verzeichnis des Moduls verändert. Um auf einen Parameter vom Typ
Byte zu schreiben, kann folgende Nachricht benutzt werden :
0x601 0x2f indexLowByte indexHighByte subIndex daten 0x00 0x00 0x00 0x00
Das Schreiben von 16-bit Werten erfolgt mit folgender Nachricht:
0x601 0x2b indexLowByte indexHighByte subIndex datenLowByte datenHighByte 0x0 0x0
Das Auslesen eines speziellen Objekts erfolgt mit :
0x601 0x40 indexLowByte indexHighByte subIndex 0x00 0x00 0x00 0x00 0x00
Das Antworttelegramm enthält den Inhalt der Adresse :
0x581 0x4f indexLowByte indexHighByte subIndex daten 0x00 0x00 0x00 0x00
Bei einem ausgelesenen 16-bit Wert sieht die Nachricht folgendermaßen aus:
0x581 0x4b indexLowByte indexHighByte subIndex datenLowByte datenHighByte 0x0 0x0
3.1.2 Parameter des Moduls SAI SB 4PT100
IndexSubIndexTypBezeichnung
0x22000x00ByteModulübergreifende Einstellungen :
Bit 0: 0=normal/1=Darstellung in
## Vertraulich
Heyfra Electronic GmbHVersion 1.004/11

## Fahrenheit
## Bit 1: 0=normal/ 1=vorzeichenlose
Darstellung (betrifft nicht die
skalierte Ausgabe)
IndexSubIndexTypBezeichnung
0x22010x01ByteSensoreinstellung Kanal 0
## Bit 4 – 0 : Sensortyp Kanal 0
## Bit 7 – 5 : Filtereinstellung Kanal 0
0x22010x02ByteSensoreinstellung Kanal 1
## Bit 4 – 0 : Sensortyp Kanal 1
## Bit 7 – 5 : Filtereinstellung Kanal 1
0x22010x03ByteSensoreinstellung Kanal 2
## Bit 4 – 0 : Sensortyp Kanal 2
## Bit 7 – 5 : Filtereinstellung Kanal 2
0x22010x04ByteSensoreinstellung Kanal 3
## Bit 4 – 0 : Sensortyp Kanal 3
## Bit 7 – 5 : Filtereinstellung Kanal 3
IndexSubIndexTypBezeichnung
0x22020x01ByteSensor/Diagnoseeinstellung Kanal 0
Bit 1 – 0 : Anschluss-Art
00 = 4-Leiter-Anschluss
01 = 3-Leiter-Anschluss
10 = 2-Leiter-Anschluss
Bit 3 – 2 :Konfiguration Alarm1
00 = aus
01 = Low-Alarm
10 = High-Alarm
## Bit 5 – 4 :   Konfiguration Alarm2
00 = aus
01 = Low-Alarm
10 = High-Alarm
Bit 8       :     0=normal/1=Skalierte
Ausgabe aktiviert
0x22020x02ByteSensor/Diagnoseeinstellung Kanal 1
Bit 1 – 0 : Anschluss-Art
00 = 4-Leiter-Anschluss
## Vertraulich
Heyfra Electronic GmbHVersion 1.005/11

01 = 3-Leiter-Anschluss
10 = 2-Leiter-Anschluss
Bit 3 – 2 :Konfiguration Alarm1
00 = aus
01 = Low-Alarm
10 = High-Alarm
## Bit 5 – 4 :   Konfiguration Alarm2
00 = aus
01 = Low-Alarm
10 = High-Alarm
Bit 8       :     0=normal/1=Skalierte
Ausgabe aktiviert
0x22020x02ByteSensor/Diagnoseeinstellung Kanal 2
Bit 1 – 0 : Anschluss-Art
00 = 4-Leiter-Anschluss
01 = 3-Leiter-Anschluss
10 = 2-Leiter-Anschluss
Bit 3 – 2 :Konfiguration Alarm1
00 = aus
01 = Low-Alarm
10 = High-Alarm
## Bit 5 – 4 :   Konfiguration Alarm2
00 = aus
01 = Low-Alarm
10 = High-Alarm
Bit 8       :     0=normal/1=Skalierte
Ausgabe aktiviert
0x22020x03ByteSensor/Diagnoseeinstellung Kanal 3
Bit 1 – 0 : Anschluss-Art
00 = 4-Leiter-Anschluss
01 = 3-Leiter-Anschluss
10 = 2-Leiter-Anschluss
Bit 3 – 2 :Konfiguration Alarm1
00 = aus
01 = Low-Alarm
10 = High-Alarm
## Bit 5 – 4 :   Konfiguration Alarm2
00 = aus
## Vertraulich
Heyfra Electronic GmbHVersion 1.006/11

01 = Low-Alarm
10 = High-Alarm
Bit 8       :     0=normal/1=Skalierte
Ausgabe aktiviert
IndexSubIndexTypBezeichnung
220301Int16Grenzwert 1 Kanal 1
220302Int16Grenzwert 1 Kanal 2
220303Int16Grenzwert 1 Kanal 3
220304Int16Grenzwert 1 Kanal 4
220401Int16Grenzwert 2 Kanal 1
220402Int16Grenzwert 2 Kanal 2
220403Int16Grenzwert 2 Kanal 3
220404Int16Grenzwert 2 Kanal 4
IndexSubIndexTypBezeichnung
220501Int16Hysterese Kanal 1
220502Int16Hysterese Kanal 2
220503Int16Hysterese Kanal 3
220504Int16Hysterese Kanal 4
IndexSubIndexTypBezeichnung
220601Int16Unterer Messwert Skalierung Kanal 1
220602Int16Unterer Messwert Skalierung Kanal 2
220603Int16Unterer Messwert Skalierung Kanal 3
220604Int16Unterer Messwert Skalierung Kanal 4
220701Int16Oberer Messwert Skalierung Kanal 1
220702Int16Oberer Messwert Skalierung Kanal 2
220703Int16Oberer Messwert Skalierung Kanal 3
220704Int16Oberer Messwert Skalierung Kanal 4
## Vertraulich
Heyfra Electronic GmbHVersion 1.007/11

IndexSubIndexTypBezeichnung
220801Int16Unterer Ausgabewert Skalierung Kanal 1
220802Int16Unterer Ausgabewert Skalierung Kanal 2
220803Int16Unterer Ausgabewert Skalierung Kanal 3
220804Int16Unterer Ausgabewert Skalierung Kanal 4
220901Int16Oberer Ausgabewert Skalierung Kanal 1
220902Int16Oberer Ausgabewert Skalierung Kanal 2
220903Int16Oberer Ausgabewert Skalierung Kanal 3
220904Int16Oberer Ausgabewert Skalierung Kanal 4
IndexSubIndexTypBezeichnung
220a01Int16Leitungswiderstand Kanal 1
220a02Int16Leitungswiderstand Kanal 2
220a03Int16Leitungswiderstand Kanal 3
220a04Int16Leitungswiderstand Kanal 4
Folgende Tabelle gibt noch einen Überblick über die möglichen Sensortypen :
SnesortypParameterwert
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
## 3.2 Prozessdaten
Die Applikation wertet zyklisch die 4 Controller aus und sendet bei Veränderung die Messwerte
## Vertraulich
Heyfra Electronic GmbHVersion 1.008/11

über die Sende-PDO 1 (ID = 0x180 + modulAdresse) aus. In der PDO sind 4 16-bit Messwerte
enthalten.
3.3 Diagnose und Fehlermeldungen
Die Sende-PDO 2 des Moduls enthält Status-Daten.
Nummer des BytesBezeichnung
1.Eingangsspannung (in 10tel Volt, 100 subtrahiert)
2.Weitergeschaltete Subbus-Spannung
3.Bereichsüber- und unterschreitung
4.Leitungsbruch-Erkennung
5.Status der Alarme
## 4. Funktionsbeschreibung
## 4.1 Messwerte
Nach Einstellen des Sensortyps für einen Kanal durch Setzen der entsprechenden Bits im 1.
Einstellungsbyte   des   Kanals   liefert   das     Modul   Messwerte   für   diesen   Kanal.   In   der
Standardeinstellung   sind   die   Messwerte   vorzeichenbehaftet   und   werden  in
Zweierkomplementärdarstellung ausgegeben. Falls ein Fehler für den Kanal vorliegt, wird dies über
die Diagnosebytes des Moduls signalisiert. Das Modul besitzt 3 Diagnosebytes, welche sich aus den
Bytes der Status-PDO des Moduls, abzüglich der ersten zwei Bytes, ergeben. Das erste Byte
signalisiert in den unteren 4 Bits eine Bereichsüber- oder unterschreitung des Eingangspegels. Jedes
Bit entspricht dabei einem Kanal. Im 2 Status-Byte wird ein Fehler in den unteren 4 Bits
signalisiert, wenn die Messelektronik einen Leitungsbruch am entsprechenden Kanal erkennt.
Für Sensortypen, die eine Temperaturmessung erlauben, ist es durch Setzen des Bits 0 im globalen
Einstellungsparameter möglich, eine Darstellung mittels der Fahrenheit-Skala einzustellen.
Für alle Bereiche, deren Messbereich bipolar ist, kann durch Setzen des Bits 1 im globalen
Einstellungsparameter eine vorzeichenlose Darstellung eingestellt werden, bei der der Wert 0 durch
den Wert 8000h (32768 dezimal) dargestellt. Diese Einstellung betrifft auch die Temperaturausgabe
(Celsius und Fahrenheit), sowei die Parametrierung und Auswertung der Alarme. Die Skalierte
Ausgabe erfolgt jedoch immer mit der Zweierkomplementdarstellung.
## Vertraulich
Heyfra Electronic GmbHVersion 1.009/11

## 4.1.1 Alarme
Für jeden Kanal lassen sich 2 Grenzwerte definieren. Bei Erreichen dieser Grenzwerte kann
entweder ein High-Alarm oder ein Low-Alarm, abhängig von der Parametrierung, signalisiert
werden. Zusätzlich besteht noch die Möglichkeit, für jeden Kanal eine Hysterese für die Alarm-
Signalisierung einzustellen. Die Signalisierung der Alarme erfolgt durch das 3 Status-Byte des
Moduls, sowie bei Betrieb über das Profibus-Gateway über eine Diagnosemeldung. Die unteren 4
Bits des Bytes signalisieren den ALARM1 für die Kanäle 1..4. Die oberen 4 Bits signalisieren den
ALARM2 für Kanal 1..4.
## 4.1.2 Skalierte Ausgabe
Für   jeden   Kanal   ist   es   möglich,  einem   bestimmten   Bereich   an   Messwerten   einen
benutzerdefinierten Bereich an Ausgabewerten zuzuordnen. Dazu kann ein minimaler und ein
maximaler Messwert, der von der Messelektronik ermittelt wird, parametriert werden. Diesem
Bereich kann dann über einen mininalen Ausgabewert und einen maximalen Ausgabewert, welcher
ebenfalls über die entsprechenden Parameter für jeden Kanal eingestellt wird, ein eigener
Messbereich zugeordnet werden. Diese Parameter müssen in Zweierkomplementärdarstellung
übergeben werden. Zusätzlich muss die skalierte Ausgabe durch Setzen des Bits 7 im zweiten
Einstellungsbyte des Kanals aktiviert werden.
## 4.2 Weiter Einstellmöglichkeiten
Über 4 Parameter (16 bit Werte) kann der Leitungswiderstand für jeden Kanal eingestellt werden.
Über den 2. kanalspezifischen Parameter ist es möglich, die Anschlussart des Sonsors zu wählen.
Mögliche Einstellungen sind 2-Leiter-, 3-Leiter- und 4-Leiter-Anschluss. Der 4-Leiter-Anschluss ist
die Standardeinstellung.
Für jeden Kanal kann weiterhin über den 1. kanalspezifischen Parameter die Wandlungszeit
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
## Vertraulich
Heyfra Electronic GmbHVersion 1.0010/11

450 Hz Unterdrückung, schnell
(Filterzeit:20ms/ Wandlungszeit ca. 60ms)
560 Hz Unterdrückung, schnell
(Filterzeit:16,7ms/ Wandlungszeit ca. 54ms)
## Vertraulich
Heyfra Electronic GmbHVersion 1.0011/11