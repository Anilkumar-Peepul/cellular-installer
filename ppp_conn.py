#!/usr/bin/env python3

import serial
import time
import re
import subprocess
import atexit
from gpiozero import OutputDevice
import os
from systemd.daemon import notify
import threading
# ================= CONFIG =================
SERIAL_PORT = "/dev/ttyAMA0"
BAUDRATE = 115200
TIMEOUT = 2
PWRKEY_PIN = 6
PPP_PEER = "quectel-ppp"
APN_MAP = {
    "405854": ("jionet", "IPV4V6"),
    "40449": ("airteliot.com", "IP"),
    "40410": ("airtelgprs.com", "IP"),
    "405799": ("vinet", "IP"),
}

CURRENT_PID = os.getpid()
pwr = None
def watchdog_kick():
    try:
        notify("WATCHDOG=1")
    except Exception:
        pass


def watchdog_thread():
    while True:
        watchdog_kick()
        time.sleep(10)   # must be < WatchdogSec

def start_watchdog():
    t = threading.Thread(target=watchdog_thread, daemon=True)
    t.start()
# ============== CLEANUP ===================
def cleanup():
    global pwr
    if pwr:
        try:
            pwr.close()
            print("[GPIO] Released")
        except:
            pass

atexit.register(cleanup)

# ============== GPIO ======================
def kill_gpio_process():
    try:
        output = subprocess.check_output("lsof -t /dev/gpiochip0", shell=True).decode().strip()
        for pid in output.split():
            pid = int(pid)
            if pid != CURRENT_PID:
                cmd = subprocess.check_output(f"ps -p {pid} -o comm=", shell=True).decode().strip()
                if cmd in ["python", "python3"]:
                    print(f"[GPIO] Killing PID {pid}")
                    subprocess.run(f"kill -9 {pid}", shell=True)

    except:
        pass

def init_pwrkey():
    global pwr

    if pwr:
        return True

    try:
        pwr = OutputDevice(PWRKEY_PIN, active_high=True, initial_value=False)
        return True

    except Exception as e:
        print(f"[GPIO ERROR] {e}")

        if "GPIO busy" in str(e):
            kill_gpio_process()
            time.sleep(1)
            try:
                pwr = OutputDevice(PWRKEY_PIN, active_high=True, initial_value=False)
                return True
            except Exception as e2:
                print(f"[GPIO FAIL] {e2}")

        return False

def press_pwrkey(duration=3):
    if not init_pwrkey():
        return False

    pwr.on()
    time.sleep(duration)
    pwr.off()
    return True

def power_on():
    kill_gpio_process()
    print("[POWER] Triggering PWRKEY")
    if not press_pwrkey(3):
        return False
    time.sleep(8)
    return True

# ============== UART ======================
def kill_uart_process(port):
    print(f"[UART] Checking processes using {port}...")
    print(f"[PID] CURRENT : {CURRENT_PID}")

    # Kill all pppd
    subprocess.run("killall -9 pppd", shell=True)

    try:
        output = subprocess.check_output(f"lsof -t {port}", shell=True).decode().strip()
        pids = [int(pid) for pid in output.split() if pid]

        for pid in pids:
            if pid != CURRENT_PID:
                cmd = subprocess.check_output(f"ps -p {pid} -o comm=", shell=True).decode().strip()

                if cmd in ["pppd", "screen", "minicom", "python","python3"]:
                    print(f"[UART] Killing PID {pid} ({cmd})")
                    subprocess.run(f"kill -9 {pid}", shell=True)

    except subprocess.CalledProcessError:
        print("[UART] No process using port")

def open_serial():
    kill_uart_process(SERIAL_PORT)
    try:
        return serial.Serial(SERIAL_PORT, BAUDRATE, timeout=TIMEOUT)
    except Exception as e:
        print(f"[UART ERROR] {e}")
        return None

# ============== AT ========================
def send_at(ser, cmd, delay=1, timeout=2):
    ser.reset_input_buffer()
    ser.write((cmd + "\r\n").encode())

    time.sleep(delay)

    end_time = time.time() + timeout
    resp = ""

    while time.time() < end_time:
        resp += ser.read_all().decode(errors="ignore")
        time.sleep(0.2)

    print(f">>> {cmd}\n{resp}")
    return resp

def check_at(ser):
    for _ in range(3):
        if "OK" in send_at(ser, "AT"):
            return True
        time.sleep(1)
    return False

# ============== POWER CHECK ===============
def ensure_module_on():
    print("[CHECK] Checking module state...")

    ser = open_serial()
    if ser and check_at(ser):
        ser.close()
        return True

    if ser:
        ser.close()

    for i in range(2):
        print(f"[CHECK] Power attempt {i+1}")
        if not power_on():
            return False

        ser = open_serial()
        if ser and check_at(ser):
            ser.close()
            return True

        if ser:
            ser.close()

    return False

# ============== NETWORK ===================
def check_sim(ser):
    return "READY" in send_at(ser, "AT+CPIN?")
def set_band(ser):
    print("[NET] Setting LTE bands...")
    send_at(ser, 'AT+QCFG="band",0,8000004A80,0', delay=2)
def set_apn_by_operator(ser, mccmnc):
    apn, ip_type = APN_MAP.get(mccmnc, ("internet", "IP"))

    print(f"[NET] Setting APN: {apn}")

    send_at(ser, "AT+CGATT=0", delay=2)
    send_at(ser, f'AT+CGDCONT=1,"{ip_type}","{apn}"')
def select_best_operator(resp):
    matches = re.findall(r'\((\d),"[^"]*","[^"]*","(\d+)",(\d)\)', resp)

    current = []
    available = []

    for stat, mccmnc, rat in matches:
        stat = int(stat)
        rat = int(rat)

        if rat != 7:   # LTE only
            continue

        if stat == 2:
            current.append((mccmnc, rat))
        elif stat == 1:
            available.append((mccmnc, rat))

    if current:
        return current[0]

    if available:
        return available[0]

    return None, None

def get_apn_config(mccmnc):
    if mccmnc.startswith("405"):
        return ("jionet", "IPV4V6")
    elif mccmnc.startswith("40449"):
        return ("airteliot.com", "IP")
    elif mccmnc.startswith("404"):
        return ("airtelgprs.com", "IP")

    return ("internet", "IP")




def check_pdp(ser):
    return "+QIACT: 1,1," in send_at(ser, "AT+QIACT?")

def get_signal(ser):
    resp = send_at(ser, "AT+CSQ")
    match = re.search(r"\+CSQ: (\d+)", resp)
    return int(match.group(1)) if match else 0

def check_registration(ser):
    for _ in range(2):
        resp = send_at(ser, "AT+CEREG?")
        if ",1" in resp or ",5" in resp:
            return True
        time.sleep(1)
    return False

def scan_operators(ser):
    print("[NET] Scanning operators (this takes time)...")

    ser.reset_input_buffer()
    resp = send_at(ser, "AT+COPS=?", delay=2, timeout=10)

    print(resp)

    return resp

def parse_operator(resp):
    matches = re.findall(r'\((\d),"[^"]*","[^"]*","(\d+)",(\d)\)', resp)

    for stat, mccmnc, rat in matches:
        if stat == '2':   # current operator
            return mccmnc, int(rat)

    for stat, mccmnc, rat in matches:
        if stat == '1':   # available fallback
            return mccmnc, int(rat)

    return None, None

def deactivate_qiact(ser):
    print("[NET] Deactivating existing PDP (QIACT)...")
    send_at(ser, "AT+QIDEACT=1", delay=3)

def register_network(ser, mccmnc, rat):
    print(f"[NET] Registering {mccmnc}")

    if mccmnc and mccmnc.startswith("405"):
        rat = 7

    resp = send_at(ser, f'AT+COPS=1,2,"{mccmnc}",{rat}', delay=5)

    if "OK" not in resp:
        print("[NET] Manual failed → AUTO")
        send_at(ser, "AT+COPS=0", delay=5)

def ensure_registered(ser):
    print("[NET] Checking registration...")

    if check_registration(ser):
        return True

    print("[NET] Trying AUTO...")
    send_at(ser, "AT+COPS=0", delay=5)

    if check_registration(ser):
        return True

    print("[NET] Scanning operators...")
    cops = scan_operators(ser)

    mccmnc, rat = parse_operator(cops)

    if not mccmnc:
        return False

    register_network(ser, mccmnc, rat)

    return check_registration(ser)
def force_network_registration(ser):
    print("[NET] Force registration started...")

    send_at(ser, 'AT+QCFG="band",0,8000004A80,0', delay=2)

    cops = scan_operators(ser)

    if "+COPS:" not in cops:
        print("[NET] No operator found")
        return False

    stat, mccmnc, rat = parse_operator(cops)

    if not mccmnc:
        return False

    print(f"[NET] Selected {mccmnc} (stat={stat})")

    # KEY LOGIC
    set_apn_by_operator(ser, mccmnc)

    # Then register
    resp = send_at(ser, f'AT+COPS=1,2,"{mccmnc}",{rat}', delay=5)

    if "OK" not in resp:
        return False

    # Wait for network
    for _ in range(10):
        if check_registration(ser):
            print("[NET] Registered OK")
            return True
        time.sleep(2)

    return False
def setup_data_call(ser, mccmnc):
    apn, ip_type = APN_MAP.get(mccmnc, ("internet", "IP"))
    print(f"[NET] APN: {apn}")

    send_at(ser, "AT+CGATT=0")
    time.sleep(2)

    send_at(ser, f'AT+CGDCONT=1,"{ip_type}","{apn}"')

    send_at(ser, "AT+CGATT=1")

    if "1" not in send_at(ser, "AT+CGATT?"):
        return False

    return "OK" in send_at(ser, "AT+QIACT=1", delay=3)
# ============== PPP =======================
def start_ppp():
    print("[PPP] Starting PPP...")
    subprocess.run(f"pon {PPP_PEER}", shell=True)
    time.sleep(5)

def stop_ppp():
    print("[PPP] Stopping PPP...")
    subprocess.run(f"poff {PPP_PEER}", shell=True)

def check_internet():
    result = subprocess.run("ping -I ppp0 -c 3 8.8.8.8", shell=True)
    return result.returncode == 0

def ping_test(ser):
    resp = send_at(ser, 'AT+QPING=1,"8.8.8.8"', delay=5)
    return "ERROR" not in resp

# ============== MAIN ======================
def main():
    #start_watchdog()
    if not ensure_module_on():
        print("[ERROR] Module OFF")
        return

    ser = open_serial()
    if not ser:
        return

    try:
        if not check_at(ser):
            return

        if not check_sim(ser):
            print("[ERROR] SIM not ready")
            send_at(ser,"AT+CFUN=1,1",delay=10)
            return

        csq = get_signal(ser)
        print(f"[SIGNAL] CSQ: {csq}")

        if not ensure_registered(ser):
            print("[WARN] Normal registration failed → trying force...")

            if not force_network_registration(ser):
                print("[ERROR] Network recovery failed")

                # Optional: modem reset
                send_at(ser, "AT+CFUN=1,1", delay=10)
                time.sleep(10)

                return

        cops = send_at(ser, "AT+COPS?")
        match = re.search(r'"(\d+)"', cops)
        mccmnc = match.group(1) if match else None

        if check_pdp(ser):
            send_at(ser,"AT+QIDEACT=1")


    finally:
        ser.close()
    # Start PPP AFTER closing UART
    start_ppp()

    if check_internet():
        print("\nINTERNET OK (PPP)")
    else:
        print("\n️ PPP connected but no internet")
# ==========================================
if __name__ == "__main__":
 main()
