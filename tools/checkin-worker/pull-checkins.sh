#!/bin/sh
# Download a read-only snapshot of the live check-in database to a local
# SQLite file, for browsing in DB Browser for SQLite, TablePlus, etc.
# Nothing you do to the snapshot touches the live data; run again for fresh,
# then Refresh in the app (no need to reconnect).
#
#   tools/checkin-worker/pull-checkins.sh            # writes ~/Downloads/pulse-checkins.db and opens it
#   tools/checkin-worker/pull-checkins.sh out.db     # somewhere else
#
# Needs: npm ci here once, and `npx wrangler login` as the Cloudflare account
# that owns the database.
set -eu
cd "$(dirname "$0")"
out="${1:-$HOME/Downloads/pulse-checkins.db}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "Exporting pulse-checkins from Cloudflare..."
# The login token is short-lived; the export call fails with "Authentication
# error [code: 10000]" instead of renewing it (seen 2026-10-14). whoami renews
# it first, and one retry covers a renewal that lands mid-request.
npx wrangler whoami >/dev/null 2>&1 || true
if ! npx wrangler d1 export pulse-checkins --remote --output "$tmp/dump.sql" >/dev/null 2>&1; then
  sleep 2
  npx wrangler whoami >/dev/null 2>&1 || true
  npx wrangler d1 export pulse-checkins --remote --output "$tmp/dump.sql" >/dev/null || {
    echo "Export failed. If it says Authentication error, run: npx wrangler login (from $(pwd))" >&2
    exit 1
  }
fi
sqlite3 "$tmp/fresh.db" < "$tmp/dump.sql"
# Copy into the existing file with SQLite's backup API rather than replacing
# it: an app with the file open (DataGrip, TablePlus) keeps reading the same
# file, so its Refresh shows the new data instead of the deleted old copy.
sqlite3 "$tmp/fresh.db" ".backup '$out'"
echo "Wrote $out"
sqlite3 -noheader -list "$out" "SELECT 'check-ins: ' || COUNT(*) FROM checkins; SELECT 'units (any check-in): ' || COUNT(*) FROM units; SELECT 'units running the monitor: ' || COUNT(*) FROM unit_status;"

if [ $# -eq 0 ] && command -v open >/dev/null 2>&1; then
  open "$out" 2>/dev/null || true
fi
