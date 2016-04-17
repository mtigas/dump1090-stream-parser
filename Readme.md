# dump1090 stream parser

This software takes a [dump1090](https://github.com/antirez/dump1090) stream of [ADS-B](https://en.wikipedia.org/wiki/Automatic_dependent_surveillance_%E2%80%93_broadcast) messages and plops them into a database with a timestamp.

> **Note**: This fork optimizes for efficient data storage by using MySQL table compression, native numeric data types, and casting placeholder values to NULL where possible.

## Useage

You'll need a dump1090 instance running somewhere accessable on your network.

The script also currently relies on a MySQL database hosted on the same machine. (`host=127.0.0.1 database=dump1090 user=dump1090 password=dump1090`) [MySQL innodb table compression](https://dev.mysql.com/doc/refman/5.7/en/innodb-compression-background.html) is used, so your mileage may vary depending on your mysql server version and configuration.

If dump1090 is runing on your current machine and you have the database set up, running

```
python dump1090-stream-parser.py
```

should automatically connect to it.

Stop the stream by hitting control + c. This will write any remaining uncommitted lines to the database and exit.

> **Note**: This fork also performs some data processing to turn numeric values into their native mysql times, catch null values, and otherwise optimize for efficient data storage (along with database table compression). This hasn’t been thoroughly tested yet and *may* result in some data loss compared to the original script (and the raw SBS data stream).

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
                        to query it. Defaults to 50
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

```
python dump1090-stream-parser.py -l raspberrypi.local
```

Write every record to the database immediately instead of batching insertions 
```
python dump1090-stream-parser.py --batch-size 1
```

Read larger chunks from the stream
```
python dump1090-stream-parser.py --buffer-size 1024
```

Connect to the local machine via ip address and save records in 20 line batches to todays_squitters.db
```
python dump1090-stream-parser.py -l 127.0.0.1 -d todays_squitters.db --batch-size 20
```
