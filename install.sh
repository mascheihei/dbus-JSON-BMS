#!/bin/bash

# set permissions for script files
chmod a+x /data/dbus-json-bms/restart.sh
chmod 744 /data/dbus-json-bms/restart.sh

chmod a+x /data/dbus-json-bms/uninstall.sh
chmod 744 /data/dbus-json-bms/uninstall.sh

chmod a+x /data/dbus-json-bms/service/run
chmod 755 /data/dbus-json-bms/service/run



# create sym-link to run script in deamon
ln -s /data/dbus-json-bms/service /service/dbus-json-bms



# add install-script to rc.local to be ready for firmware update
filename=/data/rc.local
if [ ! -f $filename ]
then
    touch $filename
    chmod 755 $filename
    echo "#!/bin/bash" >> $filename
    echo >> $filename
fi

grep -qxF '/data/dbus-json-bms/install.sh' $filename || echo '/data/dbus-json-bms/install.sh' >> $filename

