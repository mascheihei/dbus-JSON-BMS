# dbus-json-bms

The dbus-json-bms uses a json-file provided by a webadress to enable a "victron battery" in venus OS. (For the JK-BMS I can provide you a bluetooth solution ;-) 

The concept is based on dbus-serial from Louisvdw

https://github.com/Louisvdw/dbus-serialbattery
and the json part from Fabian Lauer
https://github.com/fabian-lauer/dbus-shelly-3em-smartmeter
Great thanks to both!

The structure of the json-file is explained in json.txt 

How to install/configure?

Login on Raspberry or Cerbo and use the following commands in the terminal

wget https://github.com/mascheihei/dbus-json ... s/main.zip 
unzip main.zip
mv /data/dbus-json-bms-main /data/dbus-json-bms
chmod 755 install.sh
chmod 755 restart.sh
chmod 755 uninstall.sh
chmod 755 install_qml.sh

Now configure:
nano config.ini

Important is ON PREMISE the Host-line. Here you have to add the web-adress of your JSON file.
adjust the battery-capacity and the number of cells

with "./install.sh" you can start the driver 

If you like to enhance the GUI with all cell-voltages please execute "./install_qml.sh"
