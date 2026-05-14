#!/bin/bash

set -e

echo "======================================="
echo " Cellular Installer Starting..."
echo "======================================="

# -----------------------------
# CHECK ROOT
# -----------------------------
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root"
    exit
fi

# -----------------------------
# UPDATE SYSTEM
# -----------------------------
apt update -o Acquire::ForceIPv4=true

# -----------------------------
# INSTALL PACKAGES
# -----------------------------
apt install -y \
    ppp \
    minicom \
    python3-pip \
    network-manager \
    lsof \
    psmisc

# -----------------------------
# INSTALL PYTHON LIBRARIES
# -----------------------------
pip3 install -r requirements.txt

# -----------------------------
# ENABLE UART
# -----------------------------
CONFIG_FILE="/boot/firmware/config.txt"

grep -qxF 'enable_uart=1' $CONFIG_FILE || echo 'enable_uart=1' >> $CONFIG_FILE
grep -qxF 'dtparam=uart0=on' $CONFIG_FILE || echo 'dtparam=uart0=on' >> $CONFIG_FILE
grep -qxF 'dtoverlay=disable-bt' $CONFIG_FILE || echo 'dtoverlay=disable-bt' >> $CONFIG_FILE

# Disable serial console
systemctl disable serial-getty@ttyAMA0.service || true

# -----------------------------
# CREATE DIRECTORIES
# -----------------------------
mkdir -p /home/pi/cellular
mkdir -p /etc/chatscripts
mkdir -p /etc/ppp/peers

# -----------------------------
# COPY FILES
# -----------------------------
cp -r cellular/* /home/pi/cellular/

cp chatscripts/quectel-chat-connect /etc/chatscripts/
cp chatscripts/quectel-chat-disconnect /etc/chatscripts/

cp peers/quectel-ppp /etc/ppp/peers/

cp services/quectel-ppp.service /etc/systemd/system/
cp services/interface-switcher.service /etc/systemd/system/

cp config/config.json /home/pi/cellular/

# -----------------------------
# PERMISSIONS
# -----------------------------
chmod +x /home/pi/cellular/*.py

# -----------------------------
# ENABLE SERVICES
# -----------------------------
systemctl daemon-reload

systemctl enable quectel-ppp.service
systemctl enable interface-switcher.service

# -----------------------------
# FINISH
# -----------------------------
echo "======================================="
echo " Installation Complete"
echo " Rebooting System..."
echo "======================================="

reboot
