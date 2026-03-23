import time
#import micropython
from esp32 import CAN
#Messagevar
BootupMsg = 0x7ff
Msg0x01 = 0x01
Msg0x81 = 0x81
Msg0x82 = 0x82
Msg0x83 = 0x83
MsgDev1 = 0x701
BootUpStp = 0
AdressStp = 0
ModulCnt = 1
BOOTUP_STOP = 0

print("Bootup")
#function recv from can
def recv_struct(recv):
    struct_recv = {"id": None, "data": []}
    struct_recv["id"] = int(recv[0])
    struct_recv["data"] = list(recv[3])
    return struct_recv

can_msg = {"id": None, "data": []}
# Funktion zum Senden einer CAN-Nachricht
def send_can_message(data, can_id):
    can.send(data, can_id)
    time.sleep(0.1)  # Kurze Verzögerung, um sicherzustellen, dass die Nachricht empfangen wird

# Funktion zum Parametrieren des Moduls
def configure_module():
# Setzen der Producer Heartbeat Time auf 1000 ms
    #send_can_message([0x23, 0x17, 0x10, 0x00, 0xE8, 0x03, 0x00, 0x00], 0x600 + node_id)
    send_can_message([0x23, 0x17, 0x10, 0x00, 0xE8, 0x03, 0x00, 0x00], 0x600 + 1)
    
    # Filtereinstellungen für Eingang 2
    send_can_message([0x40, 0x18, 0x10, 0x02, 0x00, 0x00, 0x00, 0x00], 0x601)
    send_can_message([0x67, 0x24, 0x16, 0x02, 0x01, 0x00, 0x00, 0x00], 0x581)

    # Filtereinstellungen für Eingang 3
    send_can_message([0x40, 0x18, 0x10, 0x03, 0x00, 0x00, 0x00, 0x00], 0x601)
    send_can_message([0x67, 0x24, 0x16, 0x03, 0x06, 0x00, 0x01, 0x00], 0x581)

    # Filtereinstellungen für Eingang 4
    send_can_message([0x40, 0x18, 0x10, 0x04, 0x00, 0x00, 0x00, 0x00], 0x601)
    send_can_message([0x67, 0x24, 0x16, 0x04, 0x32, 0x52, 0x19, 0xD3], 0x581)

    # Konfiguration der Eingangsfilter
    send_can_message([0x47, 0x00, 0x32, 0x00, 0x00, 0x00, 0x00, 0x00], 0x601)
    send_can_message([0x96, 0x00, 0x32, 0x00, 0x00, 0x00, 0x00, 0x00], 0x581)

    # Konfiguration der Eingangsfilter für Eingang 1
    send_can_message([0x47, 0x07, 0x32, 0x01, 0x55, 0x00, 0x00, 0x00], 0x601)
    send_can_message([0x96, 0x07, 0x32, 0x01, 0x00, 0x00, 0x00, 0x00], 0x581)

    # Konfiguration der Eingangsfilter für Eingang 2
    send_can_message([0x47, 0x07, 0x32, 0x02, 0x55, 0x00, 0x00, 0x00], 0x601)
    send_can_message([0x96, 0x07, 0x32, 0x02, 0x00, 0x00, 0x00, 0x00], 0x581)

    # Konfiguration der sicheren Zustände für Ausgänge
    send_can_message([0x47, 0x05, 0x32, 0x00, 0xFF, 0x00, 0x00, 0x00], 0x602)
    send_can_message([0x96, 0x05, 0x32, 0x00, 0x00, 0x00, 0x00, 0x00], 0x582)

    # Konfiguration der sicheren Zustände für Ausgänge 2
    send_can_message([0x47, 0x06, 0x32, 0x00, 0x00, 0x00, 0x00, 0x00], 0x602)
    send_can_message([0x96, 0x06, 0x32, 0x00, 0x00, 0x00, 0x00, 0x00], 0x582)
        
    print("Modul wurde parametriert.")

    send_can_message([0x01], 0x00)
    
    print("Modus Operational")
    
can=CAN(0, tx=5, rx=4, mode=CAN.NORMAL, baudrate=250000)

start_time = time.time()
elapsed_time = 0
while (1):
    if can.any():
        can_msg = recv_struct(can.recv())   
        if AdressStp == 0:   
            if can_msg["id"] == 0x7ff and int(can_msg["data"][0]) == 0x01:            
                print("Bootup MSG from Modul: ", ModulCnt)  
                AdressStp = 1
                
        if AdressStp == 1:
            can.send([0x81,ModulCnt], 0x7FE)#Adresse vergeben
            AdressStp = 2
            
        if AdressStp == 2:
            if can_msg["id"] == BootupMsg and int(can_msg["data"][0]) == 0x81:            
                print("Adresse ACK")
                AdressStp = 3
                
        if AdressStp == 3:
            can.send([0x82,ModulCnt], 0x7FE)#Switch on Next Module
            AdressStp = 4
            
        if AdressStp == 4:
            if can_msg["id"] == BootupMsg and int(can_msg["data"][0]) == 0x82:            
                print("Switch ON Next Module")
                ModulCnt = ModulCnt+1
                start_time = time.time()
                AdressStp = 5               
                
        if AdressStp == 5:   
            if can_msg["id"] == 0x7ff and int(can_msg["data"][0]) == 0x01:
                print("Bootup MSG from Modul: ", ModulCnt)
                can.send([0x81,ModulCnt], 0x7FE)#Adresse vergeben
                AdressStp = 2
            
    if AdressStp == 5:        
        elapsed_time = time.time() - start_time
        
    if elapsed_time >= 1 and AdressStp == 5:
        print("kein weiteres Modul erkannt")
        AdressStp = 6
        
            
        if AdressStp == 6:
            can.send([0x7F], 0x77F)
            print("Start Application ACK")
            i = 1
            while i < ModulCnt:
                can.send([0x83,i], 0x7FE)
                i = i + 1
            can.send([0x7F], 0x77F)
            AdressStp = 7
    if AdressStp == 7:
        print("Module Konfigurieren")
        configure_module()
        
        AdressStp = 10 
    if AdressStp == 10 and can_msg["id"] == 0x700 + ModulCnt -1 and int(can_msg["data"][0]) == 0x05:
        send_can_message([0x05], 0x77F)
