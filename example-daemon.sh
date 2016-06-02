#!/bin/sh

# for now, a totally hackish daemon setup for running this
# in a piaware machine, targeting the default dump1090 output port
# and a mysql server running at `192.168.1.101` (default user `dump1090`,
# password `dump1090`, and database `dump1090`)
#
# has only been tested on a raspbian jessie with a manually-installed
# `dump1090` and `piaware` packages via the deb instructions at
# https://flightaware.com/adsb/piaware/install
# also needs the `python` and `python-mysql.connector` packages installed
# via apt.
#
# if this file lives at /home/pi/bin/stream-30003.sh,
# add a `/home/pi/bin/stream-30003.sh &` line to /etc/rc.local
# and `chmod 755` this file.

cd /home/pi/dump1090-stream-parser
while true
  do
    sleep 20
    python dump1090-stream-parser.py -p 30003 --batch-size 20 --mysql-host 192.168.1.101 -c 0
  done
