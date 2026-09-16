import os
import time
from io import BytesIO
from pyrtcm import RTCMReader

'''
This script decodes RTCM3 messages and writes output to console.
'''

# ==============================
# CONFIGURATION
# ==============================

RTCM_FILE = "out.rtcm3"

READ_CHUNK_SIZE = 4096
POLL_INTERVAL = 0.05


def decode_frame(frame):
    """Decode one complete RTCM 3 frame."""

    try:
        reader = RTCMReader(BytesIO(frame))

        for raw_data, parsed_data in reader:
            print(f"Type: {parsed_data.identity}")
            print(parsed_data)
            print("-" * 40)

    except Exception as e:
        print(f"Decode error: {e}")


def main():

    print(f"Waiting for {RTCM_FILE}...")

    # Wait until NTRIP client creates the file
    while not os.path.exists(RTCM_FILE):
        time.sleep(POLL_INTERVAL)

    print(f"Reading {RTCM_FILE}")
    print("Waiting for RTCM messages...\n")

    buffer = bytearray()

    with open(RTCM_FILE, "rb") as f:

        while True:

            # Read new bytes
            data = f.read(READ_CHUNK_SIZE)

            if data:
                buffer.extend(data)

            else:
                # No new data yet.
                # NTRIP client hasn't written anything new.
                time.sleep(POLL_INTERVAL)
                continue

            # Look for complete RTCM frames
            while True:

                # Need at least 3 bytes:
                # D3 + length bytes
                if len(buffer) < 3:
                    break

                # Find RTCM preamble
                if buffer[0] != 0xD3:

                    index = buffer.find(0xD3)

                    if index == -1:
                        buffer.clear()
                        break

                    del buffer[:index]

                    if len(buffer) < 3:
                        break

                # RTCM 3:
                #
                # Byte 0:
                #   11010011 = 0xD3
                #
                # Bytes 1-2:
                #   6 reserved bits + 10-bit payload length

                payload_length = (
                    ((buffer[1] & 0x03) << 8)
                    | buffer[2]
                )

                # Total frame:
                #
                # 3 bytes header
                # + payload
                # + 3 bytes CRC
                #
                frame_length = 3 + payload_length + 3

                # Wait for entire frame
                if len(buffer) < frame_length:
                    break

                # Extract complete frame
                frame = bytes(buffer[:frame_length])

                # Remove it from buffer
                del buffer[:frame_length]

                # Decode it
                decode_frame(frame)


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print("\nDecoder stopped.")