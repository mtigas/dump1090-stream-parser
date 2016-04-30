# dump1090 stream parser

This software takes a [dump1090](https://github.com/antirez/dump1090) stream of [ADS-B](https://en.wikipedia.org/wiki/Automatic_dependent_surveillance_%E2%80%93_broadcast) messages and plops them into a database with a timestamp.

You can read about the general ADS-B "basestation" data format [here](http://woodair.net/SBS/Article/Barebones42_Socket_Data.htm) and [here](https://github.com/wiseman/node-sbs1/blob/master/README.md).

> **Note**: This fork optimizes for efficient data storage by using MySQL table compression, native numeric data types, and casting placeholder values to NULL where possible.

## Usage

You'll need a dump1090 instance running somewhere accessable on your network.

The script also currently relies on a MySQL database hosted on the same machine. (`host=127.0.0.1 database=dump1090 user=dump1090 password=dump1090`) [MySQL innodb table compression](https://dev.mysql.com/doc/refman/5.7/en/innodb-compression-background.html) is used, so your mileage may vary depending on your mysql server version and configuration.

If dump1090 is runing on your current machine and you have the database set up, running

```sh
python dump1090-stream-parser.py
```

should automatically connect to it.

Stop the stream by hitting control + c. This will write any remaining uncommitted lines to the database and exit.

> **Note**: This fork also performs some filtering & data processing to turn numeric values into their native mysql times, catch null values, and otherwise optimize for efficient data storage (along with database table compression). This hasn’t been thoroughly tested yet and *may* result in some data loss compared to the original script (and the raw SBS data stream).

###Complete usage and options

```
usage: dump1090-stream-parser.py [-h] [-l LOCATION] [-p PORT]
                                 [--buffer-size BUFFER_SIZE]
                                 [--batch-size BATCH_SIZE]
                                 [--connect-attempt-limit CONNECT_ATTEMPT_LIMIT]
                                 [--connect-attempt-delay CONNECT_ATTEMPT_DELAY]

A program to process dump1090 messages then insert them into a database

optional arguments:
  -h, --help            show this help message and exit
  -l LOCATION, --location LOCATION
                        This is the network location of your dump1090
                        broadcast. Defaults to localhost
  -p PORT, --port PORT  The port broadcasting in SBS-1 BaseStation format.
                        Defaults to 30003
  --buffer-size BUFFER_SIZE
                        An integer of the number of bytes to read at a time
                        from the stream. Defaults to 100
  --batch-size BATCH_SIZE
                        An integer of the number of rows to write to the
                        database at a time. A lower number makes it more
                        likely that your database will be locked when you try
                        to query it. Defaults to 100
  --connect-attempt-limit CONNECT_ATTEMPT_LIMIT
                        An integer of the number of times to try (and fail) to
                        connect to the dump1090 broadcast before qutting.
                        Defaults to 10
  --connect-attempt-delay CONNECT_ATTEMPT_DELAY
                        The number of seconds to wait after a failed
                        connection attempt before trying again. Defaults to
                        5.0
```

## Examples

Connecting to dump1090 instance running on a raspberry pi on your local network

```sh
python dump1090-stream-parser.py -l raspberrypi.local
```

Write every record to the database immediately instead of batching insertions
```sh
python dump1090-stream-parser.py --batch-size 1
```

Read larger chunks from the stream
```sh
python dump1090-stream-parser.py --buffer-size 1024
```

Connect to the local machine via ip address and save records in 20 line batches to todays_squitters.db
```sh
python dump1090-stream-parser.py -l 127.0.0.1 -d todays_squitters.db --batch-size 20
```

---

If you have trouble getting dump1090 to emit [multilateration](https://en.wikipedia.org/wiki/Multilateration) (MLAT) data you receive from flightaware, you can make `piaware-config` provide it's own basestation port by doing something like `basestation,listen,31003`, i.e.:

```sh
sudo piaware-config -mlatResultsFormat "beast,connect,127.0.0.1:30104 beast,connect,feed.adsbexchange.com:30005 basestation,listen,31003"
```

And then you can just run another copy of dump1090-stream-parser to catch that data.
```sh
python dump1090-stream-parser.py -p 30003 &
python dump1090-stream-parser.py -p 31003 --batch-size 10 &
wait
```


## Querying

The ICAO address is stored as the raw base10 integer representation of the
24-bit address (which is usually displayed as a 6-character hex string).

The squawk, which is a [four digit octal code](https://en.wikipedia.org/wiki/Transponder_(aeronautics)#Transponder_codes) (base 8), is also stored as a raw base10 integer.

To query for these or display "normal" output, you can use the `CONV()` function in mysql:

```sql
SELECT transmission_type, CONV(icao_addr, 10, 16) as hex_addr, callsign, altitude, lat, lon, ground_speed, track, CONV(decimal_squawk, 10, 8) as squawk, parsed_time as utctime
  FROM squitters
  WHERE ((lat IS NOT NULL && lon IS NOT NULL) OR (callsign IS NOT NULL))
    AND (icao_addr = CONV("AA3410", 16, 10))
  ORDER BY parsed_time DESC
  LIMIT 50;
```
