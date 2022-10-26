#!/bin/sh
#backup old PageBattery.qml
cp /opt/victronenergy/gui/qml/PageBattery.qml /opt/victronenergy/gui/qml/PageBattery.qml.backup
#copy new PageBattery.qml
cp /data/dbus-json-bms/qml/PageBattery.qml /opt/victronenergy/gui/qml/
#copy new PageBatteryCellVoltages
cp /data/dbus-json-bms/qml/PageBatteryCellVoltages.qml /opt/victronenergy/gui/qml/
#stop gui
svc -d /service/gui
#sleep 1 sec
sleep 1
#start gui
svc -u /service/gui
