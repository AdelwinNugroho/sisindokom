# devices.py
# Configuration file untuk jumphost dan target devices

# Jumphost pertama
JUMPHOST_1 = {
    "device_type": "terminal_server",   # Gunakan terminal_server untuk Windows/Linux shell
    "host": "100.75.49.116",           # IP jumphost pertama
    "username": "user1",
    "password": "sisindokom@sshd1",
}

# Jumphost kedua  
JUMPHOST_2 = {
    "device_type": "terminal_server",   # Akan di-hop via SSH dari jumphost-1
    "host": "10.62.170.56",            # IP jumphost kedua
    "username": "930435", 
    "password": "Razor301412",
}

# Target devices (akan diakses dari jumphost-2)
DEVICES = [
    {
        "device_type": "cisco_xr",      # Initial type, akan di-detect ulang
        "host": "R3.STA.PE-MOBILE.1",        # Gunakan IP untuk reliability
        "username": "930435",                 # Kosong jika tidak perlu username
        "password": "12345Qwer",
    },
    {
        "device_type": "cisco_xr", 
        "host": "R3.STA.PE-MOBILE.2",
        "username": "930435",
        "password": "12345Qwer",
    },
    # Tambahkan device lain di sini jika diperlukan
    # {
    #     "device_type": "cisco_ios",
    #     "host": "10.1.1.3", 
    #     "username": "admin",
    #     "password": "password123",
    # },
]
