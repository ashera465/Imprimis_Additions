#!/usr/bin/env python3

'''
This python script acts as an NTRIP client, connecting to an NTRIP caster and receiving RTCM data.
The NTRIP Configuration section allows you to specify the connection details.
Note that to login for some mountpoints you may need a username and password.

While the details are defined below, it is also possible to override them using CLARGS.

'''

# ==============================
# NTRIP CONFIGURATION
# ==============================

CASTER = "rtk2go.com"
PORT = 2101
MOUNTPOINT = "Cubrundairy"

USERNAME = "abrahama5-at-vcu-d-edu"
PASSWORD = None

OUTPUT_FILE = "out.txt"

# ==============================

import socket
import base64
import time
import argparse

class NTRIPClient:

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

    def connect(self):
        print(f"Connecting to {self.caster}:{self.port}...")

        self.sock = socket.create_connection(
            (self.caster, self.port),
            timeout=10
        )

        # Build authentication header
        headers = [
            f"GET /{self.mountpoint} HTTP/1.0",
            "User-Agent: NTRIP PythonClient/1.0",
            "Accept: */*",
            "Connection: close",
        ]

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

    def process_data(self, data):
        if self.file:
            self.file.write(data)
            self.file.flush()

    def run(self):
        total_bytes = 0
        start_time = time.time()

        try:
            while True:

                data = self.sock.recv(4096)

                if not data:
                    print("Caster closed the connection.")
                    break

                total_bytes += len(data)

                self.process_data(data)

                elapsed = time.time() - start_time

                if elapsed >= 1.0:
                    rate = total_bytes / elapsed

                    print(
                        f"\rReceived: {total_bytes:,} bytes "
                        f"({rate:.1f} bytes/s)",
                        end="",
                        flush=True
                    )

        except KeyboardInterrupt:
            print("\nStopping...")

        finally:
            self.close()

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


def main():

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

    client = NTRIPClient(
        caster=args.caster,
        port=args.port,
        mountpoint=args.mountpoint,
        username=args.username,
        password=args.password,
        output_file=args.output,
    )

    try:
        client.connect()
        client.run()

    except Exception as e:
        print(f"\nERROR: {e}")
        client.close()

if __name__ == "__main__":
    main()

