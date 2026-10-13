#!/bin/sh
# Download a read-only snapshot of the live check-in database to a local
# SQLite file, for browsing in DB Browser for SQLite, TablePlus, etc.
# Nothing you do to the snapshot touches the live data; run again for fresh.
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
npx wrangler d1 export pulse-checkins --remote --output "$tmp/dump.sql" >/dev/null
rm -f "$out"
sqlite3 "$out" < "$tmp/dump.sql"
echo "Wrote $out"
sqlite3 -noheader -list "$out" "SELECT 'check-ins: ' || COUNT(*) FROM checkins; SELECT 'units: ' || COUNT(*) FROM unit_status;"

if [ $# -eq 0 ] && command -v open >/dev/null 2>&1; then
  open "$out" 2>/dev/null || true
fi
