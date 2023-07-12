#!/usr/bin/env python

"""
NMEA2TCP.py: Extract NMEA from Traquitio API mode output strings and push out to TCP port
Allows u-Blox u-center to use Traquitio as a GPS source 
"""
__author__      = "Steve Randall"
__copyright__   = "Copyright 2023, Random Engineering Ltd."
__credits__     = [""]
__license__     = "GPL"
__version__     = "0.2.2"
__maintainer__  = "Steve Randall"
__email__       = "steve@randomaerospace.com"
__status__      = "Development"

import sys
import serial
import socket
import threading

LocalPort = 54321

# put a lock around print to syncronise printing from both threads
#
def lock_print(stuff):
     lock.acquire()
     print (stuff)
     lock.release()

# this thread handles UBX messages coming from the u-center and maps them into Traquito API mode messages
# only HOT / WARM / COLD restart messages are supported currently

def UBX_handler(name):
    while True :
        try:
            data = conn.recv(1024)
            if data:
                if (data == b'\xb5\x62\x06\x04\x04\x00\x00\x00\x02\x00\x10\x68') : # if UBX-CFG-RST Hot Start
                    lock_print ("UBX HOT START")
                    ser.write(b'{"type":"REQ_GPS_RESET","temp":"hot"}' + b'\n')    # Issue API mode 'Reset Hot' 
                if (data == b'\xb5\x62\x06\x04\x04\x00\x01\x00\x02\x00\x11\x6c') : # if UBX-CFG-RST Warm Start
                    lock_print ("UBX WARM START")
                    ser.write(b'{"type":"REQ_GPS_RESET","temp":"warm"}' + b'\n')   # Issue API mode 'Reset Warm'
                if (data == b'\xb5\x62\x06\x04\x04\x00\xff\xff\x02\x00\x0e\x61') : # if UBX-CFG-RST Cold Start
                    lock_print ("UBX COLD START")
                    ser.write(b'{"type":"REQ_GPS_RESET","temp":"cold"}' + b'\n')   # Issue API mode 'Reset Cold'

        except socket.error:
            lock_print ("UBX handler Socket Error")
            break

# this main thread opens the serial and TCP socket and handles serial API modes messages from Traquito 
# and strips out NMEA to send over the TCP socket to u-center
# serial port name should be passed in as a program argument 

if __name__ == "__main__":

    if len(sys.argv) != 2 :
         print('Error no serial port argument. Usage: ' + sys.argv[0] + ' SerialPort')  
         sys.exit(1)

    try:
        ser = serial.Serial(sys.argv[1])                        # open JetPack serial port
    except:
        print('Cant open serial port ' + sys.argv[1])
        sys.exit(1)

    print('Serial on: ' + ser.name)                         # check which port was really used

    host = ''                                               # Means all available interfaces
    port = LocalPort                                        # Bespoke port number for this service
    skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # TCP socket
    skt.bind((host, port))
    print ('Port #: ', port)
    skt.listen(1)
    conn, addr = skt.accept()

    print('Connected by', addr)

    lock = threading.Lock()
    x = threading.Thread(target=UBX_handler, args=(1,))
    x.start()

    while(True):
        s = ser.readline()                                  # read a line from JetPack
        if s.startswith(b'{"type":"GPS_LINE","line":"$') :  # only process GPS line
             nmea = s[27:-3] + b'\r\n'                      # strip out the GPS NMEA from Jetpack message
             lock_print(nmea)                               # echo the GPS NMEA line
             try:
                 conn.sendall(nmea)                         # push the NMEA to u-center

             except socket.error:
                 lock_print ("Main thread Socket Error")
                 break

    ser.close()                                             # close serial port
    skt.close()                                             # close socket
