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
