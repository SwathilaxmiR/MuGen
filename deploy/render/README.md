# Render (free tier) demo

| Service | Type | Notes |
|---|---|---|
| `mugen` | Docker web service from this repo | API + 1 worker in one container (`deploy/render/start.sh`); 512 MB RAM, sleeps when idle |
| `mugen-storage` | image `versity/versitygw` (Apache-2.0), command `versitygw posix /tmp` | S3 gateway; **ephemeral**: files vanish when it restarts or sleeps |
| `mugen-db` | Render Postgres free | expires 30 days after creation unless upgraded |

Extra env vars on `mugen`, beyond `.env.example`:
- `AWS_REQUEST_CHECKSUM_CALCULATION=WHEN_REQUIRED` and `AWS_RESPONSE_CHECKSUM_VALIDATION=WHEN_REQUIRED`. Render's Cloudflare edge rejects boto3's default aws-chunked uploads without them.

Known free-tier limits:
- Tracks longer than about 30 s can run out of memory and restart the container.
- The first request after idling waits for the service to wake (cold start).
