CREATE TABLE IF NOT EXISTS
  squitters(
    message_type      VARCHAR(3) NOT NULL,
    transmission_type SMALLINT NOT NULL,
    session_id        TEXT,
    aircraft_id       TEXT NOT NULL DEFAULT '',
    icao_addr         INTEGER NOT NULL,
    flight_id         TEXT NOT NULL DEFAULT '',
    callsign          TEXT NOT NULL DEFAULT '',
    altitude          INTEGER,
    ground_speed      SMALLINT,
    track             INTEGER,
    vertical_rate     INTEGER,
    decimal_squawk    INTEGER,
    alert             BOOLEAN,
    emergency         BOOLEAN,
    spi               BOOLEAN,
    is_on_ground      BOOLEAN,
    parsed_time       TIMESTAMP WITH TIME ZONE NOT NULL,
    generated_datetime TIMESTAMP WITH TIME ZONE,
    logged_datetime   TIMESTAMP WITH TIME ZONE,
    is_mlat           BOOLEAN,
    client_id         SMALLINT NOT NULL DEFAULT 0
  );
SELECT AddGeometryColumn ('public','squitters','latlon',4326,'POINT',2);
CREATE INDEX IF NOT EXISTS idx_parsed_time ON squitters(parsed_time);
CREATE INDEX IF NOT EXISTS idx_message_type ON squitters(message_type);
CREATE INDEX IF NOT EXISTS idx_aircraft_id ON squitters(aircraft_id);
CREATE INDEX IF NOT EXISTS idx_flight_id ON squitters(flight_id);
CREATE INDEX IF NOT EXISTS idx_callsign ON squitters(callsign);
CREATE INDEX IF NOT EXISTS idx_transmission_type ON squitters(transmission_type);
CREATE INDEX IF NOT EXISTS idx_icao_addr ON squitters(icao_addr);
CREATE INDEX IF NOT EXISTS idx_is_mlat ON squitters(is_mlat);
CREATE INDEX IF NOT EXISTS idx_client_id ON squitters(client_id);
CREATE INDEX IF NOT EXISTS idx_latlon ON squitters(latlon);
CREATE INDEX IF NOT EXISTS idx_latlon ON squitters(latlon);
CREATE INDEX IF NOT EXISTS idx_decimal_squawk ON squitters(decimal_squawk);
