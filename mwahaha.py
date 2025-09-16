#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Win-Tech – Otomasi Logging Cisco (run dari Jumphost-1)
Flow:
  JH1 (jalanin script) -> SSH ke JH2 (Netmiko linux shell) -> SSH hop ke device XR
  Ambil:
    - show running-config | include ^hostname
    - show version
    - show platform
    - show ipv4 interface brief | include Loopback0
    - show cdp neighbors
    - show lldp neighbors
  Simpan:
    - Semua output per-device ke folder logs/
    - CSV (hostname, loopback0_ip, platform, version)
"""

import os
import re
import csv
import sys
import time
import logging
from typing import Dict, Any

from netmiko import ConnectHandler
from netmiko import redispatch
from devices import JUMPHOST_2, DEVICES

# ======== Konfigurasi umum ========
CSV_FILE = "cisco_device_info.csv"
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Netmiko debug log (opsional, berguna saat trouble)
logging.basicConfig(filename="netmiko-debug.log", level=logging.INFO)
logging.getLogger("netmiko").setLevel(logging.INFO)


# ======== Utilitas kecil ========
def clear():
    os.system("cls" if os.name == "nt" else "clear")


def save_text(fname: str, text: str) -> None:
    with open(fname, "w", encoding="utf-8", newline="") as f:
        f.write(text if text else "")


def append_csv_row(path: str, row: Dict[str, Any], header: bool = False) -> None:
    fieldnames = ["hostname", "loopback0_ip", "platform", "version"]
    new_file = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fieldnames)
        if header or new_file:
            wr.writeheader()
        wr.writerow(row)


# ======== Parser output ========
def parse_device_info(combined_output: str) -> Dict[str, str]:
    """
    Input: gabungan output (hostname + version + platform + loopback)
    Return: dict dengan hostname, loopback0_ip, platform, version
    """
    data = {"hostname": "N/A", "loopback0_ip": "N/A", "platform": "N/A", "version": "N/A"}

    # hostname
    m = re.search(r"^hostname\s+(\S+)", combined_output, re.M)
    if m:
        data["hostname"] = m.group(1)

    # loopback0_ip (XR: 'Loopback0' biasanya muncul di show ipv4 interface brief)
    m = re.search(
        r"Loopback0.*?\b(\d{1,3}(?:\.\d{1,3}){3})\b", combined_output, re.I
    )
    if m:
        data["loopback0_ip"] = m.group(1)

    # platform (XR kadang ada 'chassis')
    m = re.search(r"Cisco\s+(.+?)\s+(?:platform|chassis)", combined_output, re.I)
    if m:
        data["platform"] = m.group(1).strip()

    # version (XR)
    m = re.search(r"Cisco IOS XR Software,\s*Version\s*([^\s\[]+)", combined_output, re.I)
    if m:
        data["version"] = f"IOS XR {m.group(1)}"
    else:
        # fallback umum IOS
        m = re.search(r"Cisco IOS Software, (.+?), Version ([^,]+),", combined_output, re.I)
        if m:
            data["version"] = f"{m.group(1)} v{m.group(2)}"

    return data


# ======== SSH hop helper (dari JH2 linux shell ke device) ========
def ssh_hop_from_jh2(conn, target_user: str, target_host: str, pwd: str,
                     prompt_regex: str = r"(?m)[>#]\s*$", wait_s: int = 90) -> None:
    """
    Dari sesi JH2 (linux shell) lakukan `ssh -tt ...` ke device.
    Handle: hostkey, Username:, Password:, banner panjang.
    Setelah sukses, fungsinya return dengan kondisi channel sudah di prompt device.
    """
    assert pwd is not None, "Password device kosong"

    base = (
        "ssh -tt "
        "-o StrictHostKeyChecking=no "
        "-o UserKnownHostsFile=/dev/null "
        "-o PreferredAuthentications=password "
        "-o PubkeyAuthentication=no "
        "-o NumberOfPasswordPrompts=1 "
        "-o ConnectTimeout=8 "
        "-o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group-exchange-sha1,diffie-hellman-group1-sha1 "
        "-o HostkeyAlgorithms=+ssh-rsa "
        "-o PubkeyAcceptedKeyTypes=+ssh-rsa "
    )
    cmd = f"{base}-l {target_user} {target_host}" if target_user else f"{base}{target_host}"

    conn.write_channel(cmd + "\n")

    end = time.time() + wait_s
    buf = ""
    re_yes = re.compile(r"Are you sure you want to continue connecting", re.I)
    re_user = re.compile(r"username[: ]", re.I)
    re_pass = re.compile(r"password[: ]", re.I)
    re_denied = re.compile(r"permission denied", re.I)
    re_prompt = re.compile(prompt_regex)

    sent_user = False
    sent_pass = False

    while time.time() < end:
        time.sleep(0.4)
        out = conn.read_channel()
        if out:
            buf += out

        if re_yes.search(buf):
            conn.write_channel("yes\n")
            buf = ""
            continue

        if re_user.search(buf) and not sent_user:
            conn.write_channel((target_user or "") + "\n")
            sent_user = True
            buf = ""
            continue

        if re_pass.search(buf) and not sent_pass:
            conn.write_channel(pwd + "\n")
            sent_pass = True
            # ketok enter beberapa kali sampai prompt muncul
            for _ in range(4):
                time.sleep(0.6)
                conn.write_channel("\n")
            # coba sinkron prompt
            try:
                conn.read_until_pattern(pattern=prompt_regex, read_timeout=12)
            except Exception:
                pass
            return

        # Jika prompt sudah terdeteksi tanpa minta password (SSO/whatever)
        if re_prompt.search(buf):
            return

        if re_denied.search(buf):
            raise Exception("Permission denied saat SSH hop ke device.")

    raise Exception("Timeout menunggu prompt/credential saat SSH hop ke device.")


# ======== Connect ke JH2 langsung (karena script jalan di JH1) ========
def connect_to_jh2():
    """
    Konek ke Jumphost-2 (shell linux / powershell yang bisa jalankan ssh)
    """
    print("[*] Konek ke JH2:", JUMPHOST_2["host"])
    conn = ConnectHandler(
        device_type=JUMPHOST_2.get("device_type", "linux"),
        host=JUMPHOST_2["host"],
        username=JUMPHOST_2["username"],
        password=JUMPHOST_2["password"],
        fast_cli=False,
        auth_timeout=60,
        banner_timeout=60,
        timeout=60,
        global_delay_factor=1.5,
        session_log="jh2_session.log",
    )

    # Verifikasi banner “Selamat Datang, <username>” (jika ada)
    try:
        welcome_pat = rf"Selamat\s+Datang,\s*{re.escape(JUMPHOST_2['username'])}"
        conn.read_until_pattern(pattern=welcome_pat, read_timeout=10)
    except Exception:
        # Nggak semua JH2 ada banner — kita sync ke prompt umum [>\$#]
        pass

    # Ketok enter supaya prompt jelas
    conn.write_channel("\n")
    try:
        conn.read_until_pattern(pattern=r"(?m).*[>\$#]\s*$", read_timeout=10)
    except Exception:
        pass

    print("[+] Terhubung ke JH2.")
    return conn


# ======== Ambil data device ========
def collect_from_device(conn, device: Dict[str, str]) -> Dict[str, str]:
    """
    Dari channel JH2 (conn), hop ke device, redispatch jadi cisco_xr,
    jalankan show command, kembalikan info hasil parsing.
    """
    host = device["host"]
    print(f"\n[+] Hop ke device: {host}")

    # 1) hop ke device
    ssh_hop_from_jh2(
        conn,
        device.get("username", "") or "",
        device["host"],
        device["password"],
        prompt_regex=r"(?m)[>#]\s*$",
        wait_s=90
    )

    # 2) redispatch supaya perintah Netmiko paham XR
    try:
        redispatch(conn, device_type=device.get("device_type", "cisco_xr"))
    except Exception:
        # kalau gagal redispatch, tetap coba raw send_command
        pass

    # 3) jalankan show commands
    out_hostname = conn.send_command(
        "show running-config | include ^hostname", read_timeout=30
    )
    out_version = conn.send_command("show version", read_timeout=60)
    out_platform = conn.send_command("show platform", read_timeout=60)
    out_loop = conn.send_command(
        "show ipv4 interface brief | include Loopback0", read_timeout=30
    )
    out_cdp = conn.send_command("show cdp neighbors", read_timeout=30)
    out_lldp = conn.send_command("show lldp neighbors", read_timeout=30)

    # 4) simpan log per-device
    dev_tag = re.sub(r"[^\w\-.]+", "_", host)
    save_text(os.path.join(LOG_DIR, f"{dev_tag}_hostname.txt"), out_hostname)
    save_text(os.path.join(LOG_DIR, f"{dev_tag}_version.txt"), out_version)
    save_text(os.path.join(LOG_DIR, f"{dev_tag}_platform.txt"), out_platform)
    save_text(os.path.join(LOG_DIR, f"{dev_tag}_loopback.txt"), out_loop)
    save_text(os.path.join(LOG_DIR, f"{dev_tag}_cdp.txt"), out_cdp)
    save_text(os.path.join(LOG_DIR, f"{dev_tag}_lldp.txt"), out_lldp)

    # 5) parsing untuk CSV
    combined = "\n".join([out_hostname, out_loop, out_platform, out_version])
    info = parse_device_info(combined)
    return info


# ======== Menu & Main ========
def show_menu():
    clear()
    print(r"""
 __        __ _       _______         _     
 \ \      / /(_)     |__   __|       | |    
  \ \ /\ / /  _ _ __    | | ___  ___ | |__  
   \ V  V /  | | '_ \   | |/ _ \/ _ \| '_ \ 
    \_/\_/   | | | | |  | |  __/ (_) | | | |
            _/ |_| |_|  |_|\___|\___/|_| |_|
           |__/                              
   .: Win-Tech – Otomasi Logging Cisco :.
    (Run di JH1 -> JH2 -> Device)
""")
    print("1. Login ke Jumphost-2")
    print("2. Mulai koleksi informasi perangkat")
    print("3. Keluar")
    print("-------------------------------------------------")


def main():
    active = None
    while True:
        show_menu()
        choice = input("Masukkan pilihan (1/2/3): ").strip()
        if choice == "1":
            try:
                if active:
                    print("[!] Sudah terhubung ke JH2.")
                else:
                    active = connect_to_jh2()
            except Exception as e:
                print(f"[-] Gagal konek JH2: {e}")
            input("\nTekan Enter untuk lanjut...")
        elif choice == "2":
            if not active:
                print("[-] Belum login ke JH2 (pilih opsi 1 dulu).")
                input("\nTekan Enter...")
                continue

            # reset CSV lama
            if os.path.exists(CSV_FILE):
                os.remove(CSV_FILE)
            append_csv_row(CSV_FILE, {
                "hostname": "", "loopback0_ip": "",
                "platform": "", "version": ""
            }, header=True)

            for dev in DEVICES:
                try:
                    info = collect_from_device(active, dev)
                    append_csv_row(CSV_FILE, info)
                    print(f"[+] OK: {dev['host']} -> {info}")
                except Exception as e:
                    print(f"[-] Gagal pada {dev['host']}: {e}")
                    append_csv_row(CSV_FILE, {
                        "hostname": dev['host'],
                        "loopback0_ip": "ERROR",
                        "platform": "ERROR",
                        "version": "ERROR"
                    })
                finally:
                    # setelah selesai 1 device, ketok ~. dua kali untuk keluar ssh device (jaga-jaga),
                    # tapi banyak platform XR cukup 'exit'
                    try:
                        active.write_channel("exit\n")
                        time.sleep(0.6)
                    except Exception:
                        pass

            print(f"\n[+] Selesai. Cek file CSV: {CSV_FILE} dan folder logs/")
            input("\nTekan Enter untuk lanjut...")
        elif choice == "3":
            print("Bye!")
            try:
                if active:
                    active.disconnect()
            except Exception:
                pass
            sys.exit(0)
        else:
            print("Pilihan tidak valid.")
            input("\nTekan Enter untuk lanjut...")


if __name__ == "__main__":
    main()
