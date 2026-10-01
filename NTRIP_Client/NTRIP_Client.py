#!/usr/bin/env python3

'''
This python script acts as an NTRIP client, connecting to an NTRIP caster and receiving RTCM data.
The NTRIP Configuration section allows you to specify the connection details.
Note that to login for some mountpoints you may need a username and password.

While the details are defined below, it is also possible to override them using CLARGS.

The default caster is rtk.geodnet.com, which requires authentication and NMEA GGA input for RTCM data.
Also GEODNET Requires NMEA output for RTCM data.
'''

# ==============================
# NTRIP AUTHENTICATION CONFIGURATION
# ==============================
                                #Default is:
CASTER = "rtk.geodnet.com"      #rtk.geodnet.com
PORT = 2101                     #2101
MOUNTPOINT = "AUTO"             #AUTO

USERNAME = "u"
PASSWORD = ""

OUTPUT_FILE = ""
# ==============================

# ==============================
# TOPIC CONFIGURATION
TOPIC_GPS_OUT = "/gps/fix"  #This is the topic for GPS output
RATE = 1.0  #Sends GGA messages @ {RATE} Hz
SOCKET_TIMEOUT = 10
TOPIC_TIMEOUT = 10
# ==============================

#=================================
#GPS PORT CONFIG
GPS_PORT = "/dev/ttyUSB0" #Check this 
BAUD_RATE = 115200
#==================================

import socket
import base64
import time
import argparse
from sensor_msgs.msg import NavSatFix

import rclpy
from rclpy.node import Node
import serial

#Define class header
class NTRIPClient(Node):

    def __init__(
        self,
        caster=None,
        port=None,
        mountpoint=None,
        username=None,
        password=None,
        output_file=None,
    ):
        
        self.caster = caster
        self.port = port
        self.mountpoint = mountpoint
        self.username = username
        self.password = password
        self.output_file = output_file

        self.sock = None
        self.file = None

        #Create timer. Will send GGA and recieve RTCM at specified rate.
        self.gga_timer = self.create_timer(
                RATE,
                self.run()
            )
        
        #Define Port to connect to GPS device
        self.serial_port = serial.Serial(
            port=GPS_PORT,
            baudrate=BAUD_RATE,
            #Returns after 1 sec of no serial input
            timeout=1
        )


        
    #Subscribe to any necessary topics
    def subscribe(self):
        
        try:
            self.fix_sub = self.create_subscription(
                NavSatFix,
                TOPIC_GPS_OUT,
                self.fix_callback,
                TOPIC_TIMEOUT
            )
        except Exception as e:
            print(f"Failed to subscribe to topic {TOPIC_GPS_OUT}: {e}")

    #Callback function containing messages
    def fix_callback(self, msg):
        self.latest_fix = msg

    def connect(self):
        print(f"Connecting to {self.caster}:{self.port}...")

        #Create socket
        self.sock = socket.create_connection(
            (self.caster, self.port),
            timeout=SOCKET_TIMEOUT
        )

        # Build authentication header
        headers = [
            f"GET /{self.mountpoint} HTTP/1.0",
            "User-Agent: NTRIP PythonClient/1.0",
            "Accept: */*",
            "Connection: close",
        ]


        #Compile authenication header
        if self.username is not None:
            credentials = f"{self.username}:{self.password or ''}"
            encoded = base64.b64encode(
                credentials.encode()
            ).decode()

            headers.append(
                f"Authorization: Basic {encoded}"
            )

        request = "\r\n".join(headers) + "\r\n\r\n"

        print("\nSending request:")
        print(request)

        #Send Request to Caster
        self.sock.sendall(request.encode())

        # Read caster response
        response = b""
        while b"\r\n\r\n" not in response:
            data = self.sock.recv(4096)

            if not data:
                break

            response += data

            if len(response) > 16384:
                break

        header, separator, remaining = response.partition(b"\r\n\r\n")

        print("Caster response:")
        print("--------------------------------")
        print(header.decode(errors="replace"))
        print("--------------------------------")

        # Check response
        first_line = header.split(b"\r\n")[0].decode(
            errors="replace"
        )

        #Error Messages if Caster didn't connect/ rejected authentication
        if (
            "200 OK" not in first_line
            and "ICY 200 OK" not in first_line
        ):
            raise RuntimeError(
                f"NTRIP caster rejected connection: {first_line}"
            )

        print("NTRIP connection established.")

        # Open output file if requested
        if self.output_file:
            self.file = open(self.output_file, "ab")
            print(f"Saving RTCM data to: {self.output_file}")

        # The bytes after the HTTP header may already contain
        # the beginning of the RTCM stream.
        if remaining:
            self.process_data(remaining)

    #=====================================
    #Change this function to send the data to the GPS Instead
    def process_data(self, data):
        if self.file:
            self.file.write(data)
            self.file.flush()

    #===================================
    
    #Function to run the NTRIP Client
    #Sends NMEA GGA messages to caster, recieves RTCM Corrections
    def run(self):

        try:
            #Get GPS FIX and create GGA message, then send
            gga = self.create_gga(self.latest_fix)
            self.sock.sendall(
                gga.encode()
            )

            # Receive RTCM corrections
            try:
                data = self.sock.recv(4096)

                if not data:
                    print("Caster closed the connection.")

                    return

                self.process_data(data)

            except socket.timeout:
                pass

        except KeyboardInterrupt:
            print("\nStopping...")

        finally:
            self.close()
    
    #Shut down NTRIP Client
    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

            self.sock = None

        if self.file:
            self.file.close()
            self.file = None

        print("\nConnection closed.")

#This mainf will get ported to the main package 
def main():

    #Optional CLARGS
    parser = argparse.ArgumentParser(
        description="Simple Python NTRIP client"
    )

    parser.add_argument(
        "--caster",
        default = CASTER,
        help="NTRIP caster hostname or IP"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=PORT,
        help="NTRIP caster port (default: 2101)"
    )

    parser.add_argument(
        "--mountpoint",
        default = MOUNTPOINT,
        help="NTRIP mountpoint"
    )

    parser.add_argument(
        "--username",
        default = USERNAME,
        help="NTRIP username"
    )

    parser.add_argument(
        "--password",
        default = PASSWORD,
        help="NTRIP password"
    )

    parser.add_argument(
        "--output",
        default = OUTPUT_FILE,
        help="Save raw RTCM data to this file"
    )

    args = parser.parse_args()

    #Create client object
    client = NTRIPClient(
        caster=args.caster,
        port=args.port,
        mountpoint=args.mountpoint,
        username=args.username,
        password=args.password,
        output_file=args.output,
    )

    #Attempt to set up subscription, connection and run the client
    try:
        client.subscribe()
        client.connect()
        client.run()

    except Exception as e:
        print(f"\nERROR: {e}")
        client.close()

if __name__ == "__main__":
    main()

