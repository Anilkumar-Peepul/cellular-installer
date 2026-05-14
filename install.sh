#!/bin/bash

set -e

echo "======================================="
echo " Cellular Installer"
echo "======================================="

# -----------------------------------
# ROOT CHECK
# -----------------------------------
if [ "$EUID" -ne 0 ]; then
    echo "Run as root"
    exit 1
fi

# -----------------------------------
# USER INPUTS
# -----------------------------------

read -p "Linux username [pi]: " INSTALL_USER
INSTALL_USER=${INSTALL_USER:-pi}

read -p "UART Port [/dev/ttyAMA0]: " UART_PORT
UART_PORT=${UART_PORT:-/dev/ttyAMA0}

read -p "PWRKEY GPIO Pin [6]: " PWRKEY_PIN
PWRKEY_PIN=${PWRKEY_PIN:-6}

echo ""
echo "======================================="
echo "Installation Configuration"
echo "======================================="
echo "User      : $INSTALL_USER"
echo "UART Port : $UART_PORT"
echo "PWRKEY    : GPIO $PWRKEY_PIN"
echo "======================================="

sleep 2

# -----------------------------------
# FORCE IPV4
# -----------------------------------

echo 'Acquire::ForceIPv4 "true";' \
> /etc/apt/apt.conf.d/99force-ipv4

# -----------------------------------
# INSTALL PACKAGES
# -----------------------------------

apt update

apt install -y \
    ppp \
    minicom \
    python3-pip \
    python3-venv \
    network-manager \
    lsof \
    psmisc

# -----------------------------------
# CREATE INSTALL DIRECTORY
# -----------------------------------

INSTALL_DIR="/home/$INSTALL_USER/cellular"

mkdir -p $INSTALL_DIR

# -----------------------------------
# COPY FILES
# -----------------------------------

cp -r cellular/* $INSTALL_DIR/

cp chatscripts/* /etc/chatscripts/

cp peers/quectel-ppp /etc/ppp/peers/

cp config/config.json $INSTALL_DIR/

# -----------------------------------
# TEMPLATE REPLACEMENTS
# -----------------------------------

find $INSTALL_DIR -type f -name "*.py" \
-exec sed -i "s|__UART_PORT__|$UART_PORT|g" {} \;

find $INSTALL_DIR -type f -name "*.py" \
-exec sed -i "s|__PWRKEY_PIN__|$PWRKEY_PIN|g" {} \;

sed -i \
"s|__UART_PORT__|$UART_PORT|g" \
/etc/ppp/peers/quectel-ppp

# -----------------------------------
# CREATE PYTHON VENV
# -----------------------------------

python3 -m venv $INSTALL_DIR/venv

$INSTALL_DIR/venv/bin/pip install --upgrade pip

$INSTALL_DIR/venv/bin/pip install \
-r requirements.txt

# -----------------------------------
# ENABLE UART
# -----------------------------------

CONFIG_FILE="/boot/firmware/config.txt"

grep -qxF 'enable_uart=1' $CONFIG_FILE || \
echo 'enable_uart=1' >> $CONFIG_FILE

grep -qxF 'dtparam=uart0=on' $CONFIG_FILE || \
echo 'dtparam=uart0=on' >> $CONFIG_FILE

grep -qxF 'dtoverlay=disable-bt' $CONFIG_FILE || \
echo 'dtoverlay=disable-bt' >> $CONFIG_FILE

systemctl disable serial-getty@ttyAMA0.service || true

# -----------------------------------
# SERVICE FILES
# -----------------------------------

mkdir -p /etc/systemd/system/

sed \
"s|__INSTALL_USER__|$INSTALL_USER|g" \
services/quectel-ppp.service \
> /etc/systemd/system/quectel-ppp.service

sed \
"s|__INSTALL_USER__|$INSTALL_USER|g" \
services/interface-switcher.service \
> /etc/systemd/system/interface-switcher.service

# -----------------------------------
# ENABLE SERVICES
# -----------------------------------

chmod +x $INSTALL_DIR/*.py

systemctl daemon-reload

systemctl enable quectel-ppp.service

systemctl enable interface-switcher.service

echo ""
echo "======================================="
echo " Installation Complete"
echo "======================================="
echo ""
echo "Reboot Required"

read -p "Reboot now? [Y/n]: " REBOOT

if [[ "$REBOOT" != "n" ]]; then
    reboot
fi
