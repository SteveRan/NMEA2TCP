#!/usr/bin/env python

"""
NMEA2TCP.py: Extract NMEA from Traquitio API mode output strings and push out to TCP port
Convert BeiDou message into a format u-center understands
Allows u-Blox u-center to use Traquitio as a GPS source 
"""
__author__      = "Steve Randall"
__copyright__   = "Copyright 2023, Random Engineering Ltd."
__credits__     = ["Kevin Normoyle"]
__license__     = "GPL"
__version__     = "0.3.1"
__maintainer__  = "Steve Randall"
__email__       = "steve@randomaerospace.com"
__status__      = "Development"

import sys
import serial
import socket
import threading
import json
from functools import reduce
import operator

LocalPort = 54321

# put a lock around print to syncronise printing from both threads
#
def lock_print(stuff):
     lock.acquire()
     print (stuff)
     # print (stuff)
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

# nmeaData doesn't have the $ and no *<checksum> stuff at the end
def NMEA_checksum_gen(nmeaData):
    # hmm can we gen for length 0? is that required
    if not (len(nmeaData)>=1):
        # this covers the None case also
        print("ERROR: NMEA_checksum_gen: NMEA nmeaData needs at least 1 char", nmeaData)
        sys.exit(1)
    if "\n" in nmeaData:
        print("ERROR: NMEA_checksum_gen NMEA nmeaData shouldn't have any lineend, windows or unix/mac", nmeaData)
        sys.exit(1)
    if "$" in nmeaData:
        print("ERROR: NMEA_checksum_gen NMEA nmeaData shouldn't have any $", nmeaData)
        sys.exit(1)
    if "*" in nmeaData:
        print("ERROR: NMEA_checksum_gen NMEA nmeaData shouldn't have any *", nmeaData)
        sys.exit(1)

    checksumInt = reduce(operator.xor, (ord(s) for s in nmeaData), 0)
    # change it to base 16
    # return a string, but without the 0x
    # better, use string formatting to make it hex without 0x
    checksumHex = '%x' % checksumInt
    ## print("checksumHex", checksumHex)

    # alternative
    # checksumHex = hex(checksumInt).replace("0x","")
    return checksumHex

#**************************

# this main thread opens the serial and TCP socket and handles serial API modes messages from Traquito 
# and strips out NMEA to send over the TCP socket to u-center
# serial port name should be passed in as a program argument 

if __name__ == "__main__":
    # test checksum gen
    # should return a string
    checksum = NMEA_checksum_gen('GPGSV,1,1,04,10,,,41,18,,,31,27,,,36,32,,,42')
    if checksum!="75":
        print("ERROR: checksum gen test failed. checksum", checksum,  "should be '75'")
        sys.exit(1)

    if len(sys.argv) != 2 :
         print('Error no serial port argument. Usage: ' + sys.argv[0] + ' SerialPort')  
         sys.exit(1)

    try:
        # if a webpage is open and connected with the configurator, 
        # opening this port could also read if not exclusive
        # two readers will each being absorbing read data randomly.
        # this will fail if the configurator has a page open
        ser = serial.Serial(sys.argv[1], exclusive=True)

    except:
        # note: arg1 should be of form /dev/ttyACM0 for linux, COM5 for windows
        print('Cant open serial port ' + sys.argv[1])

        print('Could you have something connected to the jetpack already? (webpage or this program?)')
        # Note: if you are a linux user, you may have to add user to tty or dialout group to get user access to port
        sys.exit(1)

    print('Serial on: ' + ser.name)                         # check which port was really used

    host = ''                                               # Means all available interfaces
    port = LocalPort                                        # Bespoke port number for this service
    skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # TCP socket
    skt.bind((host, port))
    print ('Port #: ', port)
    skt.listen(1)
    print('Awaiting connection')
    conn, addr = skt.accept()

    print('Connected by', addr)

    lock = threading.Lock()
    x = threading.Thread(target=UBX_handler, args=(1,))
    x.start()

    while(True):
        # sometimes if you start while jetpack is broadcasting, you'll get a half-formed line
        # that will look like bad json. There can also be empty json

        s = ser.readline()                                  # read a line from JetPack
        # a good check is to only look at valid json lines. This will help if you're connecting to a wrong port
        # as bad lines will be printed. Or if something is wrong with your pyserial library.

        # don't have to print the non-NMEA sentences, but it's useful to know if bad json is coming from this port
        # this also covers the case of malformed GPS_LINE lines, where they are not correct json
        # ignore empty lines you get at first
        if s == b'\n':
            continue

        jsonDict = None
        jsonType = None
        try:
            # strip the newline at end (windows CR+LF and linux/mac LF)
            stripped = s.strip()
            jsonDict = json.loads(stripped)
            # all jetpack json output has a "type" key
        except Exception as e:
            print("ERROR: something wasn't right about this readline..ignoring", s, "Exception", e)

        if jsonDict is not None:
            try:
                jsonType = jsonDict["type"]
                # if all you're getting are TEMP sentences, it's like the GPS is powered off. reboot by unplug/plug-in usb
                # print the TEMP sentences so you'll see them and realize the problem
                if jsonType == "TEMP":
                    print(str(stripped))

            except Exception as e:
                print("ERROR: all jetpack sentences should have a valid json 'type' field ..Ignoring",  stripped, e)

        # if s.startswith(b'{"type":"GPS_LINE","line":"$') :  # only process GPS line
        if jsonType is not None and jsonType == "GPS_LINE":
            sentence = (jsonDict["line"])                      # pull out the GPS NMEA from Jetpack message
            # strip the the current checksum, and the leading $
            nmeaData = sentence[1:][:-3]
            # change the Baidu '$BDxxx' sentences to '$GBxxx'
            nmeaData = nmeaData.replace("BDGSA","GBGSA").replace("BDGSV","GBGSV")
            # returns a string
            nmeaChecksum = NMEA_checksum_gen(nmeaData)
            nmea = "$" + nmeaData + "*" + nmeaChecksum

            # always send the windows lineend
            nmeaPrint = nmea.encode() + b'\r\n'
            lock_print(nmeaPrint)                               # echo the GPS NMEA line
            try:
                conn.sendall(nmeaPrint)                         # push the NMEA to u-center

            except socket.error:
                lock_print ("Main thread Socket Error")
                break

    ser.close()                                             # close serial port
    skt.close()                                             # close socket
