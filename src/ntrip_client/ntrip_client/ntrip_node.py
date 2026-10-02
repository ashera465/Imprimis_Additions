#!/usr/bin/env python3

'''
This python script acts as an NTRIP client, connecting to an NTRIP caster and receiving RTCM data.
The NTRIP Configuration section allows you to specify the connection details.
Note that to login for some mountpoints you may need a username and password.

While the details are defined below, it is also possible to override them using CLARGS.

GPS serial lines are forwarded to the caster without filtering. Configure the
GPS to output GGA if the caster requires GGA input.
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
# DEBUG CONFIG
DEBUG = True

# ==============================
# GPS/NTRIP CONFIGURATION
RATE = 1.0  # Exchanges GPS data and correction data at this interval.
SOCKET_TIMEOUT = 1
# ==============================

#=================================
#GPS PORT CONFIG
GPS_PORT = "/dev/ttyACM0" #Check this
BAUD_RATE = 38400
#==================================

import socket
import base64
import argparse
import select

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
        self.serial_port = None
        self.latest_gga = None

        # Create timer to receive RTCM corrections at the specified rate.
        self.gga_timer = self.create_timer(RATE, self.run)

        # Define port to connect to GPS device if available.
        try:
            self.serial_port = serial.Serial(
                port=GPS_PORT,
                baudrate=BAUD_RATE,
                timeout=0.1,
            )
        except Exception as exc:
            self.get_logger().warning(
                f"GPS serial port {GPS_PORT} unavailable: {exc}"
            )

    #Connects to NTRIP Caster and authenticates with provided credentials.
    def connect(self):
        if self.sock is not None:
            return

        self.get_logger().info(f"Connecting to {self.caster}:{self.port}...")

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

        if DEBUG:
            self.get_logger().info("Sending NTRIP HTTP request.")
            self.get_logger().info(request)

        #Send Request to Caster
        self.sock.sendall(request.encode())

        # Read caster response
        response = b""
        try:
            while b"\r\n\r\n" not in response:
                data = self.sock.recv(4096)

                if not data:
                    break

                response += data

                if len(response) > 16384:
                    break
        except socket.timeout as exc:
            self.close()
            raise TimeoutError(f"Timed out waiting for NTRIP caster response: {exc}") from exc

        header, separator, remaining = response.partition(b"\r\n\r\n")

        
        self.get_logger().info("Caster response:")
        self.get_logger().info("--------------------------------")
        self.get_logger().info(header.decode(errors="replace"))
        self.get_logger().info("--------------------------------")

        # Check response
        first_line = header.split(b"\r\n")[0].decode(
            errors="replace"
        )

        #Error Messages if Caster didn't connect/ rejected authentication
        if (
            "200 OK" not in first_line
            and "ICY 200 OK" not in first_line
        ):
            self.close()
            raise RuntimeError(
                f"NTRIP caster rejected connection: {first_line}"
            )

        self.get_logger().info("NTRIP connection established.")

        # The bytes after the HTTP header may already contain
        # the beginning of the RTCM stream.
        if remaining:
            self.process_data(remaining)


    # Send RTCM corrections to the GPS serial port if available,
    # otherwise save them to file if configured.
    def process_data(self, data):

        #Check if port available, then send
        if self.serial_port is not None:
            try:
                self.serial_port.write(data)
                self.serial_port.flush()
                if DEBUG:
                    self.get_logger().info(f"Sent RTCM bytes to GPS serial port: {len(data)}")
                return
            except Exception as exc:
                self.get_logger().warning(f"Failed to write RTCM data to GPS serial port: {exc}\n Defaulting to file output.")

        if self.file:
            self.file.write(data)
            self.file.flush()

    def _update_latest_gga(self):
        """
        Will read serial port and obtain GGA messages and set that as the latest GGA message
        """

        if self.serial_port is None:
            return

        try:
            while True:

                #Read serial input
                line = self.serial_port.readline()
                if not line:
                    break

                sentence = line.decode("ascii", errors="ignore").strip()
                sentence_id = sentence[1:].partition(",")[0] if sentence.startswith("$") else ""
                
                if sentence_id.endswith("GGA"):
                    self.latest_gga = f"{sentence}\r\n"
                else:
                    if DEBUG:
                        self.get_logger().warning(f"Invalid sentence: {sentence}")
    

                if not self.serial_port.in_waiting:
                    break
        except Exception as exc:
            self.get_logger().warning(f"Failed to read GPS serial port: {exc}")
    

    def run(self):
        """Forward GPS serial data to the caster and RTCM back to the GPS."""

        if self.sock is None:
            self.get_logger().info("No socket yet; trying to connect to NTRIP caster.")
            try:
                self.connect()
            except Exception as exc:
                self.get_logger().error(f"Unable to connect to NTRIP caster: {exc}")
                return

        try:
            self._update_latest_gga()

            if self.latest_gga is not None:
                gga_data = self.latest_gga.encode("ascii")
                self.sock.sendall(gga_data)
                if DEBUG:
                    self.get_logger().info(
                        f"Sent latest GGA to NTRIP caster: {len(gga_data)} bytes"
                    )

                try:
                    data = self.sock.recv(4096)
                except (BlockingIOError, socket.timeout):
                    return

                if not data:
                    self.get_logger().warn("Caster closed the connection.")
                    self.close()
                    return

                self.get_logger().info(f"Received RTCM bytes: {len(data)}")
                self.process_data(data)

        except KeyboardInterrupt:
            self.get_logger().info("Stopping...")
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

        self.get_logger().info("Connection closed.")

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

    rclpy.spin(client)

    client.close()
    client.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()