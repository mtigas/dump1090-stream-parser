#!/usr/bin/env python
# encoding: utf-8
"""
see README in this directory
"""

import socket
from decimal import Decimal
import datetime
import psycopg2
import argparse
import time
import traceback
import sys

#defaults
HOST = "localhost"
PORT = 30003
BUFFER_SIZE = 50
BATCH_SIZE = 20
CONNECT_ATTEMPT_DELAY = 1.0

#
TRANSMISSION_TYPE_TTL = (
  None,  # 0 doesnt exist
  datetime.timedelta(seconds=1),  #1: callsign, infrequently broadcast anyway
  datetime.timedelta(seconds=1),   #2: position
  None, #3: position/alt -> #2
  datetime.timedelta(seconds=5),  #4: speed/heading
  datetime.timedelta(seconds=10),  #5: altitude-only
  datetime.timedelta(seconds=1),  #6: squawk
  None,  #7: altitude-only -> #5
  None,  #8: -> 2
)
TRANSMISSION_TYPE_ALIAS = (
  0,
  1,
  2,
  2, # 3 -> 2
  4,
  5,
  6,
  5, # 7 -> 5
  2, # 8 -> 2
)

# we'll discard any rows with `transmission_type` not in this set.
# 8 (all call reply) is very frequent but does not normally carry data
# for us. 7 (air to air) is also common but only contains altitude.
# your mileage may vary. see the following:
#    http://woodair.net/SBS/Article/Barebones42_Socket_Data.htm
#    https://github.com/wiseman/node-sbs1
ONLY_LOG_TYPES = frozenset({1,2,3,4,5,6,7,8})

def main():
  #set up command line options
  parser = argparse.ArgumentParser(description="A program to process dump1090 messages then insert them into a database")
  parser.add_argument("-l", "--location", type=str, default=HOST, help="This is the network location of your dump1090 broadcast. Defaults to %s" % (HOST,))
  parser.add_argument("-p", "--port", type=int, default=PORT, help="The port broadcasting in SBS-1 BaseStation format. Defaults to %s" % (PORT,))
  parser.add_argument("-c", "--client-id", type=int, default=0, help="A custom identifier to tag rows from different input sources.")

  parser.add_argument("--timezone", type=str, default="UTC")


  parser.add_argument("--psql-host", type=str, default="localhost")
  parser.add_argument("--psql-port", type=int, default=5432)
  parser.add_argument("--psql-user", type=str, default="dump1090")
  parser.add_argument("--psql-pass", type=str, default="dump1090")
  parser.add_argument("--psql-database", type=str, default="dump1090")
  parser.add_argument("--psql-sslmode", type=str, default="prefer")
  parser.add_argument("--psql-sslcert", type=str, default=None)
  parser.add_argument("--psql-sslkey", type=str, default=None)

  parser.add_argument("--buffer-size", type=int, default=BUFFER_SIZE, help="An integer of the number of bytes to read at a time from the stream. Defaults to %s" % (BUFFER_SIZE,))
  parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="An integer of the number of rows to write to the database at a time. If you turn off WAL mode, a lower number makes it more likely that your database will be locked when you try to query it. Defaults to %s" % (BATCH_SIZE,))
  parser.add_argument("--connect-attempt-delay", type=float, default=CONNECT_ATTEMPT_DELAY, help="The number of seconds to wait after a failed connection attempt before trying again. Defaults to %s" % (CONNECT_ATTEMPT_DELAY,))

  # parse command line options
  args = parser.parse_args()

  # Are we receiving data from the flightaware mlat client?
  is_mlat = (args.port == 31003)

  # print args.accumulate(args.in)
  count_since_commit = 0
  count_total = 0

  print "%s: Connecting to psql..." % args.client_id
  conn = psycopg2.connect(
    host=args.psql_host,
    port=args.psql_port,
    user=args.psql_user,
    password=args.psql_pass,
    database=args.psql_database,
    sslmode=args.psql_sslmode,
    sslcert=args.psql_sslcert,
    sslkey=args.psql_sslkey,
  )
  cur = conn.cursor()
  print "%s: Connected." % args.client_id

  # log {(icao, msgtype): timestamp} pairs to eliminate some duplicate
  # entries. based on a timestamp here, we throttle based on
  # the value of TRANSMISSION_TYPE_TTL[msgtype]
  aircraft_msg_ttls = {}

  start_time = datetime.datetime.utcnow()

  # open a socket connection
  print "%s: Connecting to dump1090..." % args.client_id
  s = connect_to_socket(args.location, args.port)

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
        s = connect_to_socket(args.location, args.port)
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
            # 0 message type is 2-3 char
            if idx == 0:
              line[idx] = v.strip("0123456789").strip()
            # 1 transmission type is int or null
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

          # transmission types; skip if it's a type that we
          # don't care to log in the database.
          if line[1] not in ONLY_LOG_TYPES:
            continue

          # Decide whether or not to skip recording datapoint based on
          # a TTL (based on transmission_type).
          msgtype_timeout_alias = TRANSMISSION_TYPE_ALIAS[line[1]]
          msgtype_key = (line[4], msgtype_timeout_alias)
          msgtype_ttl = TRANSMISSION_TYPE_TTL[msgtype_timeout_alias]
          existing_timestamp = aircraft_msg_ttls.get(msgtype_key, datetime.datetime(1970,1,1))
          #print msgtype_key, existing_timestamp
          if (not is_mlat) and (cur_time - existing_timestamp) <= msgtype_ttl:
            # too soon.
            #print "\ttoo soon"
            continue
          #print "\tok"

          # Reset TTL timer now that we're storing data for this packet
          aircraft_msg_ttls[msgtype_key] = cur_time

          # session_id, aircraft_id, flight_id are sometimes censored with '11111'?
          if (line[2] == '111' and line[3] == '11111' and line[5] == '111111') \
          or (line[2] == '1' and line[3] == '1' and line[5] == '1'):
            line[2] = None
            line[3] = None
            line[5] = None

            if line[2] == None:
                line[2] = ''
            if line[3] == None:
                line[3] = ''
            if line[5] == None:
                line[5] = ''
            if line[10] == None:
                line[10] = ''

          # "parsed_time"
          line.append("{} {}".format(cur_time, args.timezone))

          # "generated_datetime"
          if (line[6] and line[7]):
            generated_datetime = datetime.datetime.combine(line[6], line[7])
          else:
            generated_datetime = None
          line.append("{} {}".format(generated_datetime, args.timezone))

          # "logged_datetime"
          if (line[8] and line[9]):
            logged_datetime = datetime.datetime.combine(line[8], line[9])
          else:
            logged_datetime = None
          line.append("{} {}".format(logged_datetime, args.timezone))

          # store whether we got this from the piaware mlat output basestation
          # (otherwise, we got it directly from dump1090)
          line.append(is_mlat)

          line.append(args.client_id)

          # remove the generated & logged date/time fields. we'll just
          # store the combined value that we just calculated
          line.pop(6)
          line.pop(6)
          line.pop(6)
          line.pop(6)

          # move squawk from line[13] to line[0]
          sq = line.pop(13)
          if sq != None:
              sq = int(sq, 8)
          line = [sq] + line
          # move icao address from line[5] (originally 4) to line[0]
          ic = line.pop(5)
          if ic != None:
              ic = int(ic, 16)
          line = [ic] + line


          try:
            lat = line.pop(11)
            lon = line.pop(11)
            if lat != None and lon != None and lat != '' and lon != '':
                qry = """INSERT INTO squitters (
                    icao_addr,
                    decimal_squawk,
                    message_type,
                    transmission_type,
                    session_id,
                    aircraft_id,
                    flight_id,
                    callsign,
                    altitude,
                    ground_speed,
                    track,
                    vertical_rate,
                    alert,
                    emergency,
                    spi,
                    is_on_ground,
                    parsed_time,
                    generated_datetime,
                    logged_datetime,
                    is_mlat,
                    client_id,
                    latlon
                  )
                  VALUES (
                    %s,
                    %s,
                    """ + ", ".join(["%s"] * (len(line)-2)) + """,
                    ST_PointFromText('POINT(%s %s)', 4326)
                )"""
                line.append(lon)
                line.append(lat)
            else:
                qry = """INSERT INTO squitters (
                    icao_addr,
                    decimal_squawk,
                    message_type,
                    transmission_type,
                    session_id,
                    aircraft_id,
                    flight_id,
                    callsign,
                    altitude,
                    ground_speed,
                    track,
                    vertical_rate,
                    alert,
                    emergency,
                    spi,
                    is_on_ground,
                    parsed_time,
                    generated_datetime,
                    logged_datetime,
                    is_mlat,
                    client_id
                  )
                  VALUES (
                    %s,
                    %s,
                    """ + ", ".join(["%s"] * (len(line)-2)) + """)"""

            cur.executemany(qry, [line])

            # increment counts
            count_total += 1
            count_since_commit += 1

            # commit the new rows to the database in batches
            if count_since_commit % args.batch_size == 0:
              conn.commit()
              print "%s: %s:%s - avg %.1f rows/sec" % (args.client_id, args.location, args.port, float(count_total) / (cur_time - start_time).total_seconds(),)
              if count_since_commit > args.batch_size:
                print ts, "All caught up, %s rows, successfully written to database" % (count_since_commit)
              count_since_commit = 0

          except psycopg2.OperationalError:
            print
            print ts, "Could not write to database"
            print line
            traceback.print_exc()
            raise
            sys.exit(1)


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
    sys.exit(0)


  except psycopg2.OperationalError as err:
    print "Error with ", line
    traceback.print_exc()
    raise
    sys.exit(1)

def connect_to_socket(loc,port):
  s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  s.connect((loc, port))
  return s

if __name__ == '__main__':
  main()
