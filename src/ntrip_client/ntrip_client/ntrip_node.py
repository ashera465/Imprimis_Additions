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

USERNAME = "abrahama5@vcu.edu"
PASSWORD = "f3aohr"

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
        
        super().__init__('ntrip_client')

        self.caster = caster
        self.port = port
        self.mountpoint = mountpoint
        self.username = username
        self.password = password
        self.output_file = output_file

        self.sock = None
        self.file = None
        self.latest_fix = None
        self.serial_port = None

        # Create timer. Will send GGA and receive RTCM at the specified rate.
        self.gga_timer = self.create_timer(RATE, self.run)

        # Define port to connect to GPS device if available.
        try:
            self.serial_port = serial.Serial(
                port=GPS_PORT,
                baudrate=BAUD_RATE,
                timeout=1,
            )
        except Exception as exc:
            self.get_logger().warning(
                f"GPS serial port {GPS_PORT} unavailable: {exc}"
            )


        
    #Subscribe to any necessary topics
    def subscribe(self):
        try:
            self.fix_sub = self.create_subscription(
                NavSatFix,
                TOPIC_GPS_OUT,
                self.fix_callback,
                10,
            )
        except Exception as e:
            print(f"Failed to subscribe to topic {TOPIC_GPS_OUT}: {e}")

    #Callback function containing messages
    def fix_callback(self, msg):
        self.latest_fix = msg


    #Static method to check NMEA checksum
    @staticmethod
    def _nmea_checksum(sentence):
        checksum = 0
        for ch in sentence:
            checksum ^= ord(ch)
        return f"{checksum:02X}"

    #Function to create GGA sentences
    def _build_gga(self):
        
        if self.latest_fix is None:
            return None

        status = getattr(self.latest_fix, "status", None)
        if status is None or getattr(status, "status", -1) <= 0:
            return None

        latitude = float(self.latest_fix.latitude)
        longitude = float(self.latest_fix.longitude)

        if abs(latitude) > 90.0 or abs(longitude) > 180.0:
            return None

        lat_deg = int(abs(latitude))
        lat_min = (abs(latitude) - lat_deg) * 60.0
        lat_dir = "N" if latitude >= 0 else "S"

        lon_deg = int(abs(longitude))
        lon_min = (abs(longitude) - lon_deg) * 60.0
        lon_dir = "E" if longitude >= 0 else "W"

        utc_now = time.gmtime()
        utc_time = time.strftime("%H%M%S", utc_now)

        sentence = (
            f"$GPGGA,{utc_time},"
            f"{lat_deg:02d}{lat_min:07.4f},{lat_dir},"
            f"{lon_deg:03d}{lon_min:07.4f},{lon_dir},"
            "1,10,0.0,0.0,M,0.0,M,,"
        )
        checksum = self._nmea_checksum(sentence[1:])
        return f"{sentence}*{checksum}\r\n"


    #Connects to NTRIP Caster and authenticates with provided credentials.
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


    # Send RTCM corrections to the GPS serial port if available,
    # otherwise save them to file if configured.
    def process_data(self, data):
        if self.serial_port is not None:
            try:
                self.serial_port.write(data)
                self.serial_port.flush()
                return
            except Exception as exc:
                self.get_logger().warning(f"Failed to write RTCM data to GPS serial port: {exc}\n Defaulting to file output.")

        if self.file:
            self.file.write(data)
            self.file.flush()
    
    #Function to run the NTRIP Client
    #Sends NMEA GGA messages to caster, recieves RTCM Corrections
    def run(self):
        if self.sock is None:
            return

        try:
            if self.latest_fix is None:
                return

            gga = self._build_gga()
            if gga is None:
                return

            self.sock.sendall(gga.encode())

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
            self.close()
        except Exception as exc:
            self.get_logger().error(f"NTRIP run loop failed: {exc}")
            self.close()
    
    #Shut down NTRIP Client
    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

            self.sock = None

        if self.serial_port is not None:
            try:
                self.serial_port.close()
            except Exception:
                pass
            self.serial_port = None

        if self.file:
            self.file.close()
            self.file = None

        print("\nConnection closed.")

def main(args=None):
    rclpy.init(args=args)

    client = NTRIPClient(
        caster=CASTER,
        port=PORT,
        mountpoint=MOUNTPOINT,
        username=USERNAME,
        password=PASSWORD,
        output_file=OUTPUT_FILE,
    )

    client.subscribe()
    client.connect()

    rclpy.spin(client)

    client.close()
    client.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()