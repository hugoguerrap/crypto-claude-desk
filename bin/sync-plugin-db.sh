#!/usr/bin/env bash
# sync-plugin-db.sh
#
# One-way sync from the plugin-cached SQLite DB into the project's
# data/db/learning.db. Useful when the MCP server has been writing to
# its plugin-local default and the dashboard needs to catch up.
#
# After setting CRYPTO_DB_DIR in the cached plugin manifest and
# restarting Claude Code, the MCP server writes directly to the project
# DB and this sync becomes a no-op. Until then it acts as a safety net.
#
# Usage:
#   bin/sync-plugin-db.sh             # sync if plugin DB is newer
#   bin/sync-plugin-db.sh --force     # sync unconditionally
#   bin/sync-plugin-db.sh --status    # just report; don't copy

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_DB="$PROJECT_ROOT/data/db/learning.db"
PLUGIN_DB="${PLUGIN_DB:-$HOME/.claude/plugins/cache/hugoguerrap/crypto-trading-desk/1.0.0/data/db/learning.db}"

FORCE=0
STATUS_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --status) STATUS_ONLY=1 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
  esac
done

if [ ! -f "$PLUGIN_DB" ]; then
  echo "[sync-plugin-db] No plugin DB at: $PLUGIN_DB"
  echo "[sync-plugin-db] Nothing to sync. If you've configured CRYPTO_DB_DIR,"
  echo "[sync-plugin-db] the MCP writes directly to the project DB — no sync needed."
  exit 0
fi

if [ ! -f "$PROJECT_DB" ]; then
  echo "[sync-plugin-db] Project DB missing — initializing from plugin DB."
  mkdir -p "$(dirname "$PROJECT_DB")"
  cp "$PLUGIN_DB" "$PROJECT_DB"
  [ -f "$PLUGIN_DB-wal" ] && cp "$PLUGIN_DB-wal" "$PROJECT_DB-wal" || true
  [ -f "$PLUGIN_DB-shm" ] && cp "$PLUGIN_DB-shm" "$PROJECT_DB-shm" || true
  echo "[sync-plugin-db] Done."
  exit 0
fi

# Compare modification times (in seconds since epoch, portable across BSD/GNU).
mtime_of() {
  python -c "import os,sys; print(int(os.path.getmtime(sys.argv[1])))" "$1" 2>/dev/null \
    || stat -c %Y "$1" 2>/dev/null \
    || stat -f %m "$1"
}

PLUGIN_MTIME=$(mtime_of "$PLUGIN_DB")
PROJECT_MTIME=$(mtime_of "$PROJECT_DB")

if [ "$STATUS_ONLY" = 1 ]; then
  echo "Plugin  DB: $PLUGIN_DB  (mtime $PLUGIN_MTIME)"
  echo "Project DB: $PROJECT_DB  (mtime $PROJECT_MTIME)"
  if [ "$PLUGIN_MTIME" -gt "$PROJECT_MTIME" ]; then
    echo "→ Plugin DB is newer. Run without --status to sync."
  else
    echo "→ Project DB is current."
  fi
  exit 0
fi

if [ "$FORCE" = 1 ] || [ "$PLUGIN_MTIME" -gt "$PROJECT_MTIME" ]; then
  BACKUP="$PROJECT_DB.bak-$(date +%s)"
  cp "$PROJECT_DB" "$BACKUP"
  cp "$PLUGIN_DB" "$PROJECT_DB"
  [ -f "$PLUGIN_DB-wal" ] && cp "$PLUGIN_DB-wal" "$PROJECT_DB-wal" || true
  [ -f "$PLUGIN_DB-shm" ] && cp "$PLUGIN_DB-shm" "$PROJECT_DB-shm" || true
  echo "[sync-plugin-db] Synced plugin → project. Backup: $BACKUP"
else
  echo "[sync-plugin-db] Project DB is up to date (plugin not newer). No sync needed."
fi
