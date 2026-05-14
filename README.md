# Cellular Installer for Raspberry Pi

Automated production-ready PPP setup and network failover framework for Raspberry Pi using Quectel LTE modules.

This project automates:

- UART configuration
- PPP interface setup
- LTE modem initialization
- APN configuration
- PPP connection establishment
- Network interface switching between WiFi and LTE
- Auto-recovery and service restart
- Production deployment using systemd services

Designed for industrial IoT gateways and embedded Linux deployments.

---


# Features

## PPP Automation
- Automatic LTE modem bring-up
- Automatic PPP dialing
- Automatic APN configuration
- SIM and network registration handling
- UART process cleanup and recovery

## Network Failover
- Automatic switching between:
  - `wlan0`
  - `ppp0`
- Internet connectivity monitoring
- Dynamic route switching
- WiFi fallback support

## Production Ready
- systemd service management
- Automatic restart on failure
- Python virtual environment support
- Logging support
- Configurable installation

## Installer Based Deployment
During installation user can configure:
- Linux username
- UART port
- GPIO pin for modem PWRKEY

Installer automatically:
- Creates configuration
- Installs dependencies
- Configures UART
- Installs services
- Enables auto-start

---

# Supported Hardware

## Raspberry Pi
- Raspberry Pi 4
- Raspberry Pi CM4
- Raspberry Pi 5

## Quectel Modules
- EC200U
- EC200A
- EC25
- EG25
- Similar UART PPP capable Quectel modules

---

# Project Structure
<img width="1536" height="1024" alt="ChatGPT Image May 14, 2026, 06_51_04 PM" src="https://github.com/user-attachments/assets/8bcea6b4-afd9-4cc0-b727-4a8793b4f79b" />

```text
cellular-installer/
│
├── cellular/
│   ├── ntw_switch.py
│   ├── ppp_conn.py
│   ├── pwrkey.py
│   └── utils.py
│
├── chatscripts/
│   ├── quectel-chat-connect
│   └── quectel-chat-disconnect
│
├── config/
│   └── config.json
│
├── peers/
│   └── quectel-ppp
│
├── services/
│   ├── interface-switcher.service
│   └── quectel-ppp.service
│
├── requirements.txt
├── install.sh
├── uninstall.sh
├── README.md
└── .gitignore

Architecture
Installer
    ↓
Creates config.json
    ↓
Installs services
    ↓
systemd starts services
    ↓
PPP initialization
    ↓
LTE network registration
    ↓
PPP connection established
    ↓
Network switcher monitors interfaces
    ↓
Automatic failover between WiFi and LTE

Installation
1. Clone Repository
git clone https://github.com/Anilkumar-Peepul/cellular-installer.git
2. Enter Project Directory
cd cellular-installer
3. Run Installer
sudo bash install.sh
Installer Configuration

Installer asks:

Linux username [pi]:
UART Port [/dev/ttyAMA0]:
PWRKEY GPIO Pin [6]:

Example:

Linux username [pi]: pi
UART Port [/dev/ttyAMA0]: /dev/ttyAMA0
PWRKEY GPIO Pin [6]: 6
What Installer Does

The installer automatically:

System Setup
Updates apt repositories
Installs required packages
Creates Python virtual environment
UART Configuration

Adds to:

/boot/firmware/config.txt
enable_uart=1
dtparam=uart0=on
dtoverlay=disable-bt

Disables serial console:

serial-getty@ttyAMA0.service
PPP Setup

Copies:

chat scripts
PPP peer configurations
Service Installation

Installs:

quectel-ppp.service
interface-switcher.service
Python Environment

Creates:

/home/<user>/cellular/venv

Installs:

pyserial
gpiozero
Configuration File

Runtime configuration stored at:

/home/<user>/cellular/config.json

Example:

{
  "system": {
    "user": "pi"
  },

  "uart": {
    "port": "/dev/ttyAMA0",
    "baudrate": 115200
  },

  "gpio": {
    "pwrkey_pin": 6
  },

  "ppp": {
    "peer": "quectel-ppp"
  },

  "wifi": {
    "ssid": "",
    "password": ""
  }
}
Services
1. quectel-ppp.service

Responsible for:

modem power control
AT communication
SIM checks
network registration
PPP connection establishment
Service File
[Unit]
Description=Quectel PPP Connection Service
After=network.target
Wants=network.target
StartLimitIntervalSec=0

[Service]
Type=simple

Environment=PYTHONUNBUFFERED=1

ExecStart=/home/__INSTALL_USER__/cellular/venv/bin/python /home/__INSTALL_USER__/cellular/ppp_conn.py

WorkingDirectory=/home/__INSTALL_USER__/cellular

Restart=always
RestartSec=10

User=root
Group=root

StandardOutput=journal
StandardError=journal

KillMode=control-group

TimeoutStartSec=60

[Install]
WantedBy=multi-user.target
2. interface-switcher.service

Responsible for:

monitoring wlan0
monitoring ppp0
route switching
internet failover
WiFi recovery
Service File
[Unit]
Description=Network Interface Switcher Service
After=network.target quectel-ppp.service
Requires=quectel-ppp.service
StartLimitIntervalSec=0

[Service]
Type=simple

Environment=PYTHONUNBUFFERED=1

ExecStart=/home/__INSTALL_USER__/cellular/venv/bin/python /home/__INSTALL_USER__/cellular/ntw_switch.py

WorkingDirectory=/home/__INSTALL_USER__/cellular

Restart=always
RestartSec=10

User=root
Group=root

StandardOutput=journal
StandardError=journal

KillMode=control-group

TimeoutStartSec=60

[Install]
WantedBy=multi-user.target
PPP Chat Script

Location:

/etc/chatscripts/quectel-chat-connect

Used by:

pppd
modem dialing
PPP Peer Configuration

Location:

/etc/ppp/peers/quectel-ppp

Responsible for:

pppd configuration
UART selection
modem interaction
Useful Commands
Check PPP Interface
ip addr show ppp0
Check Service Status
systemctl status quectel-ppp.service
systemctl status interface-switcher.service
View Live Logs
journalctl -u quectel-ppp.service -f
journalctl -u interface-switcher.service -f
Restart Services
sudo systemctl restart quectel-ppp.service
sudo systemctl restart interface-switcher.service
Uninstallation

Run:

sudo bash uninstall.sh

This removes:

services
PPP configuration
chat scripts
installation directory
Troubleshooting
PPP Interface Not Created

Check:

journalctl -u quectel-ppp.service -f

Verify:

SIM inserted
antenna connected
UART wiring correct
APN correct
UART Busy

Check:

lsof /dev/ttyAMA0

Disable serial console:

sudo systemctl disable serial-getty@ttyAMA0.service
No Internet on PPP

Check:

ping -I ppp0 8.8.8.8

Verify:

APN
LTE signal
operator registration
WiFi Not Switching

Check:

journalctl -u interface-switcher.service -f

Verify:

wlan0 available
SSID/password correct
Production Recommendations
Recommended OS
Raspberry Pi OS Bookworm
Recommended Python
Python 3.11+
Recommended Deployment
Dedicated LTE antenna
Stable power supply
UPS for field devices
Future Improvements
Web UI configuration
MQTT integration
EMQX support
AWS IoT integration
OTA updates
Docker deployment
Health monitoring dashboard
Multi-modem support
