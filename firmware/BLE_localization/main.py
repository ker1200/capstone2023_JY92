from micropython import const
import struct
import bluetooth
import time

from ble_advertising import decode_services, decode_name
from lib.networking import *

#set up wifi and TCP communication protocols
host, port = '192.168.159.115', 64000
server_address = (host, port)

network_obj = Networking()
network_obj.connect()
network_obj.createTCPSocket(server_address)

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)
_IRQ_GATTS_READ_REQUEST = const(4)
_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)
_IRQ_PERIPHERAL_CONNECT = const(7)
_IRQ_PERIPHERAL_DISCONNECT = const(8)
_IRQ_GATTC_SERVICE_RESULT = const(9)
_IRQ_GATTC_SERVICE_DONE = const(10)
_IRQ_GATTC_CHARACTERISTIC_RESULT = const(11)
_IRQ_GATTC_CHARACTERISTIC_DONE = const(12)
_IRQ_GATTC_DESCRIPTOR_RESULT = const(13)
_IRQ_GATTC_DESCRIPTOR_DONE = const(14)
_IRQ_GATTC_READ_RESULT = const(15)
_IRQ_GATTC_READ_DONE = const(16)
_IRQ_GATTC_WRITE_DONE = const(17)
_IRQ_GATTC_NOTIFY = const(18)
_IRQ_GATTC_INDICATE = const(19)
_IRQ_GAP_RSSI_RESULT = const(20)

_ADV_IND = const(0x00)
_ADV_DIRECT_IND = const(0x01)
_ADV_SCAN_IND = const(0x02)
_ADV_NONCONN_IND = const(0x03)

_UART_SERVICE_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
_UART_RX_CHAR_UUID = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")
_UART_TX_CHAR_UUID = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")

current_room = 1

class BLESimpleCentral:
    def __init__(self, ble):
        self._ble = ble
        self._ble.active(True)
        self._ble.irq(self._irq)
        self._reset()

    def _reset(self):
        self._name = None
        self._addr_type = None
        self._addr = None
        self._scan_callback = None
        self._conn_callback = None
        self._read_callback = None
        self._notify_callback = None
        self._conn_handle = None
        self._start_handle = None
        self._end_handle = None
        self._tx_handle = None
        self._rx_handle = None

    def _irq(self, event, data):
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            if adv_type in (_ADV_IND, _ADV_DIRECT_IND) and _UART_SERVICE_UUID in decode_services(adv_data):
                self._addr_type = addr_type
                self._addr = bytes(addr)
                self._name = decode_name(adv_data) or "?"
                self._rssi = rssi
                self._ble.gap_scan(None)
        elif event == _IRQ_SCAN_DONE:
            if self._scan_callback:
                if self._addr:
                    self._scan_callback(self._addr_type, self._addr, self._name, self._rssi)
                    self._scan_callback = None
                else:
                    self._scan_callback(None, None, None, None)
        elif event == _IRQ_PERIPHERAL_CONNECT:
            conn_handle, addr_type, addr = data
            if addr_type == self._addr_type and addr == self._addr:
                self._conn_handle = conn_handle
                self._ble.gattc_discover_services(self._conn_handle)
        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            conn_handle, _, _ = data
            if conn_handle == self._conn_handle:
                self._reset()
        elif event == _IRQ_GATTC_SERVICE_RESULT:
            conn_handle, start_handle, end_handle, uuid = data
            print("service", data)
            if conn_handle == self._conn_handle and uuid == _UART_SERVICE_UUID:
                self._start_handle, self._end_handle = start_handle, end_handle
        elif event == _IRQ_GATTC_SERVICE_DONE:
            if self._start_handle and self._end_handle:
                self._ble.gattc_discover_characteristics(self._conn_handle, self._start_handle, self._end_handle)
            else:
                print("Failed to find uart service.")
        elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
            conn_handle, def_handle, value_handle, properties, uuid = data
            if conn_handle == self._conn_handle and uuid == _UART_RX_CHAR_UUID:
                self._rx_handle = value_handle
            if conn_handle == self._conn_handle and uuid == _UART_TX_CHAR_UUID:
                self._tx_handle = value_handle
        elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
            if self._tx_handle is not None and self._rx_handle is not None:
                if self._conn_callback:
                    self._conn_callback()
            else:
                print("Failed to find uart rx characteristic.")
        elif event == _IRQ_GATTC_WRITE_DONE:
            conn_handle, value_handle, status = data
            print("TX complete")
        elif event == _IRQ_GATTC_NOTIFY:
            conn_handle, value_handle, notify_data = data
            if conn_handle == self._conn_handle and value_handle == self._tx_handle:
                if self._notify_callback:
                    self._notify_callback(notify_data)
        elif event == _IRQ_GAP_RSSI_RESULT:
            conn_handle, rssi = data
            if conn_handle == self._conn_handle:
                print("RSSI:", rssi)

    def is_connected(self):
        return self._conn_handle is not None and self._tx_handle is not None and self._rx_handle is not None

    def scan(self, callback=None):
        self._addr_type = None
        self._addr = None
        self._scan_callback = callback
        self._ble.gap_scan(2000, 30000, 30000)

    def connect(self, addr_type=None, addr=None, callback=None):
        self._addr_type = addr_type or self._addr_type
        self._addr = addr or self._addr
        self._conn_callback = callback
        if self._addr_type is None or self._addr is None:
            return False
        self._ble.gap_connect(self._addr_type, self._addr)
        return True

    def disconnect(self):
        if self._conn_handle is None:
            return
        self._ble.gap_disconnect(self._conn_handle)
        self._reset()

    def write(self, v, response=False):
        if not self.is_connected():
            return
        self._ble.gattc_write(self._conn_handle, self._rx_handle, v, 1 if response else 0)

    def on_notify(self, callback):
        self._notify_callback = callback

def on_scan(addr_type, addr, name, rssi):
    global current_room
    
    if addr_type is not None:
        #print(name,rssi)
        if(name == "Room 1" and rssi > -65):
            print("Inside",name)
            current_room = 1
            network_obj.sendTCPPacket("Inside Room " + str(current_room))
        elif(name == "Room 2" and rssi > -73):
            print("Inside",name)
            current_room = 2
            network_obj.sendTCPPacket("Inside Room " + str(current_room))
        elif(name == "Room 1" and rssi <= -65 and current_room == 1):
            print("Corridor")
            current_room = 3
            network_obj.sendTCPPacket("Inside Corridor")
        elif(name == "Room 2" and rssi <= -73 and current_room == 2):
            print("Corridor")
            current_room = 3
            network_obj.sendTCPPacket("Inside Corridor")
        elif(current_room == 3):
            print("Corridor")
            network_obj.sendTCPPacket("Inside Corridor")
        else:
            print("Inside Room",current_room)
            network_obj.sendTCPPacket("Inside Room " + str(current_room))
        #Need to onvert rssi to distance
        #Distance = 10^((Measured Power - Instant RSSI)/(10*N))
        #Measured Power: rssi at a distance of 1m (need to measure), normally N=2
        #or find a rssi_threshold
        
            
    else:
        print("NOTHING")


def demo():
    ble = bluetooth.BLE()
    central = BLESimpleCentral(ble)
    not_found = False

    while True:
        central.scan(on_scan)
        time.sleep(1)
        
if __name__ == "__main__":
    demo()

