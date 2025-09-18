# -*- coding: utf-8 -*-

import csv
import re
import os
import sys

# --- Nama file CSV output ---
CSV_FILE_NAME = "cisco_device_info.csv"
LOG_FILES = []

def clear_terminal():
    """Membersihkan tampilan terminal."""
    os.system('cls' if os.name == 'nt' else 'clear')

def parse_log_file(filepath: str) -> dict:
    """
    Mengurai hostname, loopback0 IP, platform, dan version dari file log.
    """
    data = {}
    output = ""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            output = f.read()
    except FileNotFoundError:
        return {"hostname": "N/A", "loopback0_ip": "File not found", "platform": "N/A", "version": "N/A"}

    # --- Ekstraksi Data dari Output Log ---
    
    # Hostname (Mengambil dari 'hostname <nama>' atau prompt '#')
    m = re.search(r"^hostname\s+(\S+)", output, re.MULTILINE | re.IGNORECASE)
    if not m:
        m = re.search(r"^\S+?([A-Za-z0-9_-]+)(?:[>#]|[(])", output, re.MULTILINE | re.IGNORECASE)
    data["hostname"] = m.group(1).strip() if m else "N/A"

    # Loopback0 IP (Mencari 'Internet address is', 'Loopback0', atau 'ip address')
    m = re.search(r"Loopback0\s+(\d{1,3}(?:\.\d{1,3}){3})", output)
    if not m:
        m = re.search(r"Internet address is\s+(\d{1,3}(?:\.\d{1,3}){3})/\d{1,2}", output, re.IGNORECASE)
    if not m:
        m = re.search(r"interface Loopback0\n\s+ip address\s+(\d{1,3}(?:\.\d{1,3}){3})", output, re.MULTILINE | re.IGNORECASE)
    data["loopback0_ip"] = m.group(1) if m else "N/A"

    # Platform (Mencari 'Cisco <platform> platform')
    m = re.search(r"Cisco\s+(.+?)\s+platform", output, re.IGNORECASE)
    if not m:
        m = re.search(r"Cisco\s+(.+?)\s+chassis", output, re.IGNORECASE)
    data["platform"] = m.group(1).strip() if m else "N/A"

    # Version (Mencari 'Cisco IOS Software' atau 'Cisco IOS XR Software')
    m = re.search(r"Cisco IOS Software, (.+?), Version (.+?),", output, re.IGNORECASE)
    if m:
        data["version"] = f"{m.group(1)}, Version {m.group(2)}"
    else:
        m = re.search(r"Cisco IOS XR Software, Version (.+?)\[", output, re.IGNORECASE)
        if m:
            data["version"] = f"Cisco IOS XR Software, Version {m.group(1)}"
        else:
            m = re.search(r"Linux Software\s+\((.+?)\), Version (.+?),", output, re.IGNORECASE)
            if m:
                data["version"] = f"Linux Software ({m.group(1)}), Version {m.group(2)}"
            else:
                data["version"] = "N/A"

    return data

def show_menu():
    """Menampilkan banner dan menu utama."""
    clear_terminal()
    banner = r"""
 __          ___          _______        _     
 \ \        / (_)        |__   __|      | |    
  \ \  /\  / / _ _ __ ______| | ___  ___| |__  
   \ \/  \/ / | | '_ \______| |/ _ \/ __| '_ \ 
    \  /\  /  | | | | |     | |  __/ (__| | | |
     \/  \/   |_|_| |_|     |_|\___|\___|_| |_|
                                                
           .: AdelwinNL FT NurSyafaq :.
    Skrip Parser Log Perangkat Jaringan Cisco
"""
    print(banner)
    if LOG_FILES:
        print(f"[*] {len(LOG_FILES)} file log telah di-load.")
        print("    File yang akan diproses:", ", ".join(LOG_FILES))
    print("-" * 55)
    print("1. Masukkan Path file log")
    print("2. Mulai proses parsing")
    print("3. Keluar")
    print("-" * 55)

def get_log_files():
    """Meminta pengguna untuk memasukkan path file log."""
    global LOG_FILES
    clear_terminal()
    print("[+] Masukkan path file log (pisahkan dengan spasi jika lebih dari satu).")
    input_paths = input("Path file: ").strip()
    if input_paths:
        LOG_FILES = input_paths.split()
        print("\n[*] File log berhasil dimuat. Pilih opsi 2 untuk memproses.")
    else:
        LOG_FILES = []
        print("\n[-] Tidak ada file yang dimuat.")

def run_parsing():
    """Menjalankan parsing pada file log yang sudah dimuat."""
    if not LOG_FILES:
        print("\n[-] Belum ada file log yang dimuat. Silakan pilih opsi 1.")
        return

    print("\n[+] Memulai parsing log...")

    if os.path.exists(CSV_FILE_NAME):
        try:
            os.remove(CSV_FILE_NAME)
            print(f"[*] File '{CSV_FILE_NAME}' yang lama telah dihapus.")
        except PermissionError:
            print(f"[-] Gagal menghapus file '{CSV_FILE_NAME}'. Pastikan tidak sedang terbuka.")
            return

    with open(CSV_FILE_NAME, "a", newline="") as csvfile:
        fieldnames = ["hostname", "loopback0_ip", "platform", "version"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

    for file_path in LOG_FILES:
        print(f"[*] Memproses file log: {file_path}")
        parsed_data = parse_log_file(file_path)
        
        with open(CSV_FILE_NAME, "a", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writerow(parsed_data)
        
        if parsed_data.get("loopback0_ip") == "File not found":
            print(f"[-] GAGAL: File '{file_path}' tidak ditemukan.")
        else:
            print(f"[*] Berhasil memproses {file_path}.")

    print("\n[+] Proses parsing selesai. Cek hasilnya di:", CSV_FILE_NAME)

def main():
    """Fungsi utama program."""
    while True:
        show_menu()
        choice = input("Masukkan pilihan (1/2/3): ").strip()

        if choice == "1":
            get_log_files()
            input("\nTekan Enter untuk lanjut...")
        elif choice == "2":
            run_parsing()
            input("\nTekan Enter untuk lanjut...")
        elif choice == "3":
            print("Terima kasih.")
            sys.exit(0)
        else:
            print("Pilihan tidak valid.")
            time.sleep(1)

if __name__ == "__main__":
    main()
