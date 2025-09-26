# devices.py
# Configuration file untuk jumphost dan target devices

# Jumphost pertama
JUMPHOST_1 = {
    "device_type": "terminal_server",   # Gunakan terminal_server untuk Windows/Linux shell
    "host": "",           # IP jumphost pertama
    "username": "",
    "password": "",
}

# Jumphost kedua  
JUMPHOST_2 = {
    "device_type": "",   # Akan di-hop via SSH dari jumphost-1
    "host": "",            # IP jumphost kedua
    "username": "", 
    "password": "",
}

# Target devices (akan diakses dari jumphost-2)
DEVICES = [
    {
        "device_type": "cisco_xr",      # Initial type, akan di-detect ulang
        "host": "",        # Gunakan IP untuk reliability
        "username": "",                 # Kosong jika tidak perlu username
        "password": "",
    },
    {
        "device_type": "cisco_xr", 
        "host": "",
        "username": "",
        "password": "",
    },
    # Tambahkan device lain di sini jika diperlukan
    # {
    #     "device_type": "cisco_ios",
    #     "host": "10.1.1.3", 
    #     "username": "admin",
    #     "password": "password123",
    # },
]
