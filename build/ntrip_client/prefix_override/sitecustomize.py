import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/media/asher-abraham/42d2a8ed-c0c5-456c-b13f-3c6a4bcae065/home/asher/Asher/Test_WS/install/ntrip_client'
