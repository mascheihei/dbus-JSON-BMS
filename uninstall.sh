

#!/bin/bash

rm /service/dbus-json-bms
kill $(pgrep -f 'supervise dbus-json-bms')
chmod a-x /data/dbus-json-bms/service/run
./restart.sh

