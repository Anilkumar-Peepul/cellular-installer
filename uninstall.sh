#!/bin/bash

systemctl stop quectel-ppp.service
systemctl stop interface-switcher.service

systemctl disable quectel-ppp.service
systemctl disable interface-switcher.service

rm -f /etc/systemd/system/quectel-ppp.service
rm -f /etc/systemd/system/interface-switcher.service

rm -rf /home/pi/cellular

rm -f /etc/chatscripts/quectel-chat-connect
rm -f /etc/chatscripts/quectel-chat-disconnect

rm -f /etc/ppp/peers/quectel-ppp

systemctl daemon-reload

echo "Uninstall complete"
