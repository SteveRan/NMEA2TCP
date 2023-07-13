# NMEA2TCP
This program allows Traquito (in API mode) to work directly with u-blox u-center.  NMEA2TCP.py both:
* converts between the message formats used by u-center and Traquito
* provides the the point of interconnection (a TCP socket)

u-center may run on the same machine as NMEA2TCP – or run on a remote node in the network.

NMEA2TCP.py provides bi-directional communication:
* NMEA sentences are stripped from Traquito output and sent u-center
* u-center HOT/WARM/COLD restart actions are mapped into Traquito API messages
 
![conectivity](https://github.com/SteveRan/NMEA2TCP/assets/314756/011b94f0-3a4a-47e4-a0e9-a037f5d6d737)

# NMEA2TCP.py :

Opens a PC serial port on which it expects to find Traquito running API mode software.

Opens a local TCP socket  - to which its expecting u-center to connect.

Reads the stream of JSON messages coming from Traquito via the serial port and extracts the GPS NMEA. Writes the NMEA to the TCP socket.

Reads the socket looking for UBX messages from u-center and converts those to Traquito API messages

Echoes the string to the command window.


# How to use:

1 Install u-blox u-center on a windows PC – see: https://www.u-blox.com/en/product/u-center

2 Install NMEA2TCP.py on your computer – usually this will be the same PC as above.

3 Install API mode software on your Traquito – see: https://traquito.github.io/pro/apimode/

4 Verify API mode is working correctly by running a terminal program like Putty.

5 Configure u-center to receive NMEA from a TCP network connection.

6 Run NMEA2TCP.py and pass in the serial port name as an argument e.g. python NMEA2TCP.py COM13 

7 Once started NMEA2TCP should display the serial port, TCP port number and 'Awaiting connection'

8 Run u-center and open the GPS (Receiver>Connection>Network Connection) and enter "tcp://localhost:54321" (or the IP and portnumber for a remote connection e.g. tcp://192.168.0.37:54321)

9 NMEA2TCP should now show the stream of messages going between Traquito and u-center. u-center should start showing activity.
