#!/usr/bin/env python
# encoding: utf-8

import socket
from decimal import Decimal
import datetime
import mysql.connector
import argparse
import time
import traceback

#defaults
HOST = "localhost"
PORT = 30003
DB = "adsb_messages.db"
BUFFER_SIZE = 100
BATCH_SIZE = 100
CONNECT_ATTEMPT_LIMIT = 10
CONNECT_ATTEMPT_DELAY = 5.0


def main():
  #set up command line options
  parser = argparse.ArgumentParser(description="A program to process dump1090 messages then insert them into a database")
  parser.add_argument("-l", "--location", type=str, default=HOST, help="This is the network location of your dump1090 broadcast. Defaults to %s" % (HOST,))
  parser.add_argument("-p", "--port", type=int, default=PORT, help="The port broadcasting in SBS-1 BaseStation format. Defaults to %s" % (PORT,))
  parser.add_argument("--buffer-size", type=int, default=BUFFER_SIZE, help="An integer of the number of bytes to read at a time from the stream. Defaults to %s" % (BUFFER_SIZE,))
  parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="An integer of the number of rows to write to the database at a time. If you turn off WAL mode, a lower number makes it more likely that your database will be locked when you try to query it. Defaults to %s" % (BATCH_SIZE,))
  parser.add_argument("--connect-attempt-limit", type=int, default=CONNECT_ATTEMPT_LIMIT, help="An integer of the number of times to try (and fail) to connect to the dump1090 broadcast before qutting. Defaults to %s" % (CONNECT_ATTEMPT_LIMIT,))
  parser.add_argument("--connect-attempt-delay", type=float, default=CONNECT_ATTEMPT_DELAY, help="The number of seconds to wait after a failed connection attempt before trying again. Defaults to %s" % (CONNECT_ATTEMPT_DELAY,))

  # parse command line options
  args = parser.parse_args()

  # print args.accumulate(args.in)
  count_since_commit = 0
  count_total = 0
  count_failed_connection_attempts = 1

  conn = mysql.connector.connect(user='dump1090', password='dump1090', database='dump1090')
  cur = conn.cursor()

  # set up the table if neccassary
  table_setup(cur)


  start_time = datetime.datetime.utcnow()

  # open a socket connection
  while count_failed_connection_attempts < args.connect_attempt_limit:
    try:
      s = connect_to_socket(args.location, args.port)
      count_failed_connection_attempts = 1
      print "Connected to dump1090 broadcast"
      break
    except socket.error:
      count_failed_connection_attempts += 1
      print "Cannot connect to dump1090 broadcast. Making attempt %s." % (count_failed_connection_attempts)
      time.sleep(args.connect_attempt_delay)
  else:
    quit()


  # listen to socket for data
  data_str = ""
  try:
    #loop until an exception
    while True:
      #get current time
      cur_time = datetime.datetime.utcnow()
      ts = cur_time.strftime("%H:%M:%S")

      # receive a stream message
      try:
        message = ""
        message = s.recv(args.buffer_size)
        data_str += message.strip("\n")
      except socket.error:
        # this happens if there is no connection and is delt with below
        pass

      if len(message) == 0:
        print ts, "No broadcast received. Attempting to reconnect"
        time.sleep(args.connect_attempt_delay)
        s.close()

        while count_failed_connection_attempts < args.connect_attempt_limit:
          try:
            s = connect_to_socket(args.location, args.port)
            count_failed_connection_attempts = 1
            print "Reconnected!"
            break
          except socket.error:
            count_failed_connection_attempts += 1
            print "The attempt failed. Making attempt %s." % (count_failed_connection_attempts)
            time.sleep(args.connect_attempt_delay)
        else:
          quit()

        continue

      # it is possible that more than one line has been received
      # so split it then loop through the parts and validate

      data = data_str.split("\n")

      for d in data:
        line = d.split(",")

        #if the line has 22 items, it's valid
        if len(line) == 22:

          # clean up some values first
          for (idx, val) in enumerate(line):
            v = val.strip()
            # 0 is 2-3 char
            if idx == 0:
              line[idx] = v.strip("0123456789").strip()
            # 1 is int or null
            if idx == 1:
              if v == '':
                line[idx] = None
              else:
                line[idx] = int(v)
            # 2-10 string
            elif idx in range(2,11):
              if v == '':
                line[idx] = None
              elif idx in set([6,8]): # generated_date, logged_date
                line[idx] = datetime.datetime.strptime(v, '%Y/%m/%d').date()
              elif idx in set([7,9]): # generated_time, logged_time
                line[idx] = datetime.datetime.strptime(v, '%H:%M:%S.%f').time()
              else:
                line[idx] = v
            # 11-13 is int or null
            elif idx in range(11,14):
              if v == '':
                line[idx] = None
              else:
                line[idx] = int(v)
            # 14,15 is float-ish or null
            elif idx in range(14,16):
              if v == '':
                line[idx] = None
              else:
                line[idx] = Decimal(v)
            # 16 is int or null
            elif idx == 16:
              if v == '':
                line[idx] = None
              else:
                line[idx] = int(v)
            # 17 string
            elif idx == 17:
              if v == '':
                line[idx] = None
              else:
                line[idx] = v
            # 18-21 bool or null
            elif idx in range(18,22):
              if v == '0':
                line[idx] = False
              elif v == '':
                line[idx] = None
              else:
                line[idx] = True

          # session_id, aircraft_id, flight_id are censored with '11111'
          if (line[2] == '111' and line[3] == '11111' and line[5] == '111111') \
          or (line[2] == '1' and line[3] == '1' and line[5] == '1'):
            line[2] = None
            line[3] = None
            line[5] = None

          # "parsed_time"
          line.append(cur_time)

          # "generated_datetime"
          if (line[6] and line[7]):
            generated_datetime = datetime.datetime.combine(line[6], line[7])
          else:
            generated_datetime = None
          line.append(generated_datetime)

          # "logged_datetime"
          if (line[8] and line[9]):
            logged_datetime = datetime.datetime.combine(line[8], line[9])
          else:
            logged_datetime = None
          line.append(logged_datetime)

          is_mlat = (args.port == 31003)
          line.append(is_mlat)

          line.pop(6)
          line.pop(6)
          line.pop(6)
          line.pop(6)

          try:
            # add row to database
            qry = """INSERT INTO squitters (
                message_type,
                transmission_type,
                session_id,
                aircraft_id,
                hex_ident,
                flight_id,
                callsign,
                altitude,
                ground_speed,
                track,
                lat,
                lon,
                vertical_rate,
                squawk,
                alert,
                emergency,
                spi,
                is_on_ground,
                parsed_time,
                generated_datetime,
                logged_datetime,
                is_mlat
              )
              VALUES (""" + ", ".join(["%s"] * len(line)) + ")"
            cur.executemany(qry, [line])

            # increment counts
            count_total += 1
            count_since_commit += 1

            # commit the new rows to the database in batches
            if count_since_commit % args.batch_size == 0:
              conn.commit()
              print "%s:%s - avg %.1f rows/sec" % (args.location, args.port, float(count_total) / (cur_time - start_time).total_seconds(),)
              if count_since_commit > args.batch_size:
                print ts, "All caught up, %s rows, successfully written to database" % (count_since_commit)
              count_since_commit = 0

          except mysql.connector.Error:
            print
            print ts, "Could not write to database, will try to insert %s rows on next commit" % (count_since_commit + args.batch_size,)
            print line
            traceback.print_exc()
            print


          # since everything was valid we reset the stream message
          data_str = ""
        else:
          # the stream message is too short, prepend to the next stream message
          data_str = d
          continue

  except KeyboardInterrupt:
    print "\n%s Closing connection" % (ts,)
    s.close()
    conn.commit()
    conn.close()
    print ts, "%s squitters added to your database" % (count_total,)

  except mysql.connector.Error as err:
    print "Error with ", line
    traceback.print_exc()
    quit()

def connect_to_socket(loc,port):
  s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  s.connect((loc, port))
  return s


def table_setup(dbcursor):
  # data format info:
  #    http://woodair.net/SBS/Article/Barebones42_Socket_Data.htm
  #    https://github.com/wiseman/node-sbs1
  dbcursor.execute("DROP TABLE IF EXISTS squitters")
  dbcursor.execute("""CREATE TABLE IF NOT EXISTS
    squitters(
      message_type      VARCHAR(3) NOT NULL,
      transmission_type TINYINT(1) UNSIGNED NOT NULL,
      session_id        TEXT,
      aircraft_id       TEXT,
      hex_ident         VARCHAR(6) NOT NULL,
      flight_id         TEXT,
      callsign          TEXT,
      altitude          MEDIUMINT,
      ground_speed      SMALLINT,
      track             INT,
      lat               DECIMAL(8,5),
      lon               DECIMAL(8,5),
      vertical_rate     INT,
      squawk            TEXT,
      alert             BOOLEAN,
      emergency         BOOLEAN,
      spi               BOOLEAN,
      is_on_ground      BOOLEAN,
      parsed_time       DATETIME NOT NULL,
      generated_datetime DATETIME,
      logged_datetime   DATETIME,
      is_mlat           BOOLEAN,
      INDEX idx_parsed_time(parsed_time),
      INDEX idx_message_type(message_type),
      INDEX idx_transmission_type(transmission_type),
      INDEX idx_hex_ident(hex_ident),
      INDEX idx_is_mlat(is_mlat)
    )
    ENGINE=InnoDB
    ROW_FORMAT=COMPRESSED KEY_BLOCK_SIZE=4
    CHARACTER SET utf8
    COLLATE utf8_general_ci
  """)





if __name__ == '__main__':
  main()
