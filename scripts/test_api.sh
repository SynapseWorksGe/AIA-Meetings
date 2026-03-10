#!/usr/bin/env bash
# Quick smoke test for AIA-Meetings API
# Usage: ./scripts/test_api.sh [BASE_URL]

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

ok() { echo -e "${GREEN}✓ $1${NC}"; }
fail() { echo -e "${RED}✗ $1${NC}"; exit 1; }

echo "=== AIA-Meetings API Smoke Test ==="
echo "URL: $BASE_URL"
echo ""

# 1. Health check
echo "--- 1. Health check ---"
HEALTH=$(curl -s "$BASE_URL/health")
echo "$HEALTH" | grep -q '"ok"' && ok "Health check passed" || fail "Health check failed: $HEALTH"

# 2. OpenAPI docs available
echo "--- 2. API docs ---"
DOCS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/docs")
[ "$DOCS_STATUS" = "200" ] && ok "Swagger UI available at $BASE_URL/docs" || fail "Docs not available (HTTP $DOCS_STATUS)"

# 3. Create API key
echo "--- 3. Create API key ---"
KEY_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/keys?name=test-key")
echo "$KEY_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$KEY_RESPONSE"
API_KEY=$(echo "$KEY_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['api_key'])" 2>/dev/null)
[ -n "$API_KEY" ] && ok "API key created: ${API_KEY:0:20}..." || fail "Failed to create API key"

# 4. List meetings (should be empty)
echo "--- 4. List meetings (empty) ---"
MEETINGS=$(curl -s -H "X-API-Key: $API_KEY" "$BASE_URL/api/v1/meetings")
echo "$MEETINGS" | python3 -m json.tool 2>/dev/null
TOTAL=$(echo "$MEETINGS" | python3 -c "import sys,json; print(json.load(sys.stdin)['total'])" 2>/dev/null)
[ "$TOTAL" = "0" ] && ok "Empty meeting list returned" || fail "Expected 0 meetings"

# 5. Auth rejection with bad key
echo "--- 5. Auth rejection ---"
BAD_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: bad_key" "$BASE_URL/api/v1/meetings")
[ "$BAD_STATUS" = "401" ] && ok "Bad API key rejected (401)" || fail "Expected 401, got $BAD_STATUS"

# 6. Upload test audio (if test file exists)
echo "--- 6. Upload audio ---"
TEST_AUDIO="scripts/test_audio.wav"
if [ -f "$TEST_AUDIO" ]; then
    UPLOAD=$(curl -s -X POST \
        -H "X-API-Key: $API_KEY" \
        -F "file=@$TEST_AUDIO" \
        -F "title=Test meeting" \
        -F "language=ru" \
        "$BASE_URL/api/v1/meetings/upload")
    echo "$UPLOAD" | python3 -m json.tool 2>/dev/null
    MEETING_ID=$(echo "$UPLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin)['meeting_id'])" 2>/dev/null)
    [ -n "$MEETING_ID" ] && ok "Uploaded! Meeting ID: $MEETING_ID" || fail "Upload failed"

    # 7. Check status
    echo "--- 7. Check meeting status ---"
    sleep 2
    STATUS=$(curl -s -H "X-API-Key: $API_KEY" "$BASE_URL/api/v1/meetings/$MEETING_ID")
    echo "$STATUS" | python3 -m json.tool 2>/dev/null
    ok "Meeting status retrieved"

    echo ""
    echo "Meeting ID: $MEETING_ID"
    echo "Poll status with:"
    echo "  curl -s -H 'X-API-Key: $API_KEY' $BASE_URL/api/v1/meetings/$MEETING_ID | python3 -m json.tool"
else
    echo "(skipped — no test audio file at $TEST_AUDIO)"
    echo "To test upload, create a short WAV/MP3 and run:"
    echo "  curl -X POST -H 'X-API-Key: $API_KEY' -F 'file=@your_audio.mp3' $BASE_URL/api/v1/meetings/upload"
    ok "Upload test skipped (no audio file)"
fi

echo ""
echo "=== All checks passed ==="
echo ""
echo "API Key for further testing:"
echo "  $API_KEY"
echo ""
echo "Useful commands:"
echo "  # Upload audio:"
echo "  curl -X POST -H 'X-API-Key: $API_KEY' -F 'file=@meeting.mp3' $BASE_URL/api/v1/meetings/upload"
echo ""
echo "  # Get result:"
echo "  curl -H 'X-API-Key: $API_KEY' $BASE_URL/api/v1/meetings/<MEETING_ID> | python3 -m json.tool"
echo ""
echo "  # Swagger UI:"
echo "  open $BASE_URL/docs"
