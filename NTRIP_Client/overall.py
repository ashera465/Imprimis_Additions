
#!/usr/bin/env python3

'''
This python script will run the NTRIP client and RTCM Decoder in parallel.

'''
# ==============================
# CONFIGURATION
# ==============================

NTRIP_SCRIPT = "NTRIP_Client.py"
DECODER_SCRIPT = "decode_rtcm.py"

# ==============================
# PROCESS MANAGEMENT
# ==============================

ntrip_process = None
decoder_process = None

import subprocess
import sys
import signal


def shutdown(signum=None, frame=None):

    print("\nStopping programs...")

    if ntrip_process is not None:
        ntrip_process.terminate()

    if decoder_process is not None:
        decoder_process.terminate()

    sys.exit(0)


def main():

    global ntrip_process
    global decoder_process

    # --------------------------------
    # Handle Ctrl+C
    # --------------------------------

    signal.signal(
        signal.SIGINT,
        shutdown
    )

    # --------------------------------
    # Start NTRIP client
    # --------------------------------

    print("Starting NTRIP client...")

    ntrip_process = subprocess.Popen(
        [sys.executable, NTRIP_SCRIPT]
    )

    # --------------------------------
    # Start RTCM decoder
    # --------------------------------

    print("Starting RTCM decoder...")

    decoder_process = subprocess.Popen(
        [sys.executable, DECODER_SCRIPT]
    )

    # --------------------------------
    # Wait for processes
    # --------------------------------

    try:

        ntrip_process.wait()
        decoder_process.wait()

    except KeyboardInterrupt:

        shutdown()


if __name__ == "__main__":
    main()
