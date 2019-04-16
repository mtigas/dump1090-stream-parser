### experimental postgresql/postgis-based logger client


Requires `psycopg2`.

Assumes that database has been created via `create.sql`.

Has some extra (optional) flags, for things like SSL client certificate-based authentication.

example usage:

```bash
	./dump1090-stream-parser-psql.py \
	  --client-id=2 \
	  --psql-host=foo.example.com \
	  --psql-port=55432 \
	  --psql-user=dump1090 \
	  --psql-pass='dump1090' \
	  --psql-sslmode='require' \
	  --psql-sslcert='/home/pi/client-dump1090.pem' \
	  --psql-sslkey='/home/pi/client-dump1090.key' \
	  --psql-database=flightdata
```

---

using a postgis backend allows the use of some geometry-based queries, like the following (which fetches the 10 records closest to a given point `40.7252912, -74.0050364`)
```sql
SELECT parsed_time,
       icao_addr,
       ST_AsText(latlon),
       ST_Distance_Sphere(latlon, st_setsrid(ST_MakePoint(-74.0050364,40.7252912),4326)) AS distance_meters
FROM squitters
WHERE latlon IS NOT NULL
  AND ST_DistanceSphere(latlon, ST_SetSRID(ST_MakePoint(-74.0050364,40.7252912),4326)) <= 10000
ORDER BY latlon <-> ST_SetSRID(ST_MakePoint(-74.0050364,40.7252912),4326)
LIMIT 10;
```
