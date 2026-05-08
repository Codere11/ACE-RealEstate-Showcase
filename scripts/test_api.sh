#!/bin/bash
# API smoke test for ACE Platform

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
ORG_ID="${ORG_ID:-1}"
ORG_SLUG="${ORG_SLUG:-demo-agency}"
ACE_TEST_USERNAME="${ACE_TEST_USERNAME:-admin}"
ACE_TEST_PASSWORD="${ACE_TEST_PASSWORD:-test123}"
RUN_ID="$(date +%s)"
SURVEY_SLUG="test-survey-${RUN_ID}"
SID="test-session-${RUN_ID}"

json_get() {
  python3 -c "import sys, json; data=json.load(sys.stdin); print($1)"
}

echo "🧪 ACE Platform API Smoke Tests"
echo "==============================="
echo "BASE_URL: $BASE_URL"
echo "ORG_ID:   $ORG_ID"
echo "ORG_SLUG: $ORG_SLUG"
echo "RUN_ID:   $RUN_ID"
echo ""

# Test 1: Health
printf 'Test 1: Health status\n---------------------\n'
HEALTH=$(curl -sf "$BASE_URL/health/status")
echo "$HEALTH" | python3 -m json.tool
printf '✅ Health OK\n\n'

# Test 2: Login
printf 'Test 2: Login as admin\n----------------------\n'
LOGIN_RESPONSE=$(curl -sf -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$ACE_TEST_USERNAME\",\"password\":\"$ACE_TEST_PASSWORD\"}")

TOKEN=$(echo "$LOGIN_RESPONSE" | json_get 'data["token"]')
echo "✅ Login successful"
echo "Token: ${TOKEN:0:50}..."
echo ""

# Test 3: Get current user
printf 'Test 3: Get current user\n------------------------\n'
ME_RESPONSE=$(curl -sf -X GET "$BASE_URL/api/auth/me" \
  -H "Authorization: Bearer $TOKEN")
echo "$ME_RESPONSE" | python3 -m json.tool
printf '✅ User info retrieved\n\n'

# Test 4: List users
printf 'Test 4: List users in organization\n-----------------------------------\n'
USERS_RESPONSE=$(curl -sf -X GET "$BASE_URL/api/organizations/$ORG_ID/users" \
  -H "Authorization: Bearer $TOKEN")
USER_COUNT=$(echo "$USERS_RESPONSE" | json_get 'len(data)')
echo "✅ Found $USER_COUNT users"
echo ""

# Test 5: Create survey
printf 'Test 5: Create a test survey\n-----------------------------\n'
SURVEY_RESPONSE=$(curl -sf -X POST "$BASE_URL/api/organizations/$ORG_ID/surveys" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Survey",
    "slug": "'"$SURVEY_SLUG"'",
    "survey_type": "regular",
    "status": "draft",
    "organization_id": '"$ORG_ID"',
    "flow_json": {
      "nodes": [
        {
          "id": "q1",
          "type": "choice",
          "question": "How satisfied are you?",
          "choices": [
            {"text": "Very satisfied", "score": 100},
            {"text": "Satisfied", "score": 75},
            {"text": "Neutral", "score": 50}
          ]
        }
      ]
    }
  }')

SURVEY_ID=$(echo "$SURVEY_RESPONSE" | json_get 'data["id"]')
echo "✅ Survey created with ID: $SURVEY_ID and slug: $SURVEY_SLUG"
echo ""

# Test 6: Publish survey
printf 'Test 6: Publish survey\n----------------------\n'
PUBLISH_RESPONSE=$(curl -sf -X POST "$BASE_URL/api/organizations/$ORG_ID/surveys/$SURVEY_ID/publish" \
  -H "Authorization: Bearer $TOKEN")
SURVEY_STATUS=$(echo "$PUBLISH_RESPONSE" | json_get 'data["status"]')
echo "✅ Survey published (status: $SURVEY_STATUS)"
echo ""

# Test 7: Get survey publicly
printf 'Test 7: Get published survey (public endpoint)\n-----------------------------------------------\n'
PUBLIC_SURVEY=$(curl -sf -X GET "$BASE_URL/s/$ORG_SLUG/$SURVEY_SLUG")
SURVEY_NAME=$(echo "$PUBLIC_SURVEY" | json_get 'data["name"]')
echo "$PUBLIC_SURVEY" | python3 -m json.tool
echo "✅ Public survey accessible: $SURVEY_NAME"
echo ""

# Test 8: Submit survey response
printf 'Test 8: Submit survey response\n-------------------------------\n'
RESPONSE=$(curl -sf -X POST "$BASE_URL/s/$ORG_SLUG/$SURVEY_SLUG/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "survey_id": '"$SURVEY_ID"',
    "sid": "'"$SID"'",
    "variant": null,
    "survey_answers": {
      "q1": {"text": "Very satisfied", "score": 100}
    },
    "name": "Test User",
    "email": "test@example.com",
    "phone": "+1234567890"
  }')
RESPONSE_SCORE=$(echo "$RESPONSE" | json_get 'data["score"]')
echo "$RESPONSE" | python3 -m json.tool
echo "✅ Response submitted (score: $RESPONSE_SCORE)"
echo ""

# Test 9: Get survey statistics
printf 'Test 9: Get survey statistics\n------------------------------\n'
STATS=$(curl -sf -X GET "$BASE_URL/api/organizations/$ORG_ID/surveys/$SURVEY_ID/stats" \
  -H "Authorization: Bearer $TOKEN")
echo "$STATS" | python3 -m json.tool
printf '✅ Statistics retrieved\n\n'

# Test 10: Get survey responses
printf 'Test 10: Get survey responses\n------------------------------\n'
RESPONSES=$(curl -sf -X GET "$BASE_URL/api/organizations/$ORG_ID/surveys/$SURVEY_ID/responses" \
  -H "Authorization: Bearer $TOKEN")
RESPONSE_COUNT=$(echo "$RESPONSES" | json_get 'len(data)')
echo "✅ Found $RESPONSE_COUNT responses"
echo ""

# Test 11: Live session preview/go-live/public/end
printf 'Test 11: Live session flow\n--------------------------\n'
PREVIEW=$(curl -sf -X POST "$BASE_URL/api/organizations/$ORG_ID/live-sessions/preview" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"sid\":\"$SID\"}")
SESSION_ID=$(echo "$PREVIEW" | json_get 'data["id"]')
PREVIEW_STATUS=$(echo "$PREVIEW" | json_get 'data["status"]')
echo "✅ Preview started (status: $PREVIEW_STATUS, session_id: $SESSION_ID)"

GO_LIVE=$(curl -sf -X POST "$BASE_URL/api/organizations/$ORG_ID/live-sessions/go-live" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"sid\":\"$SID\"}")
LIVE_STATUS=$(echo "$GO_LIVE" | json_get 'data["status"]')
echo "✅ Live session started (status: $LIVE_STATUS)"

PUBLIC_LIVE=$(curl -sf "$BASE_URL/api/public/organizations/$ORG_SLUG/live-session?sid=$SID")
PUBLIC_LIVE_STATUS=$(echo "$PUBLIC_LIVE" | json_get 'data["status"]')
echo "✅ Public live session visible (status: $PUBLIC_LIVE_STATUS)"

ENDED=$(curl -sf -X POST "$BASE_URL/api/organizations/$ORG_ID/live-sessions/$SESSION_ID/end" \
  -H "Authorization: Bearer $TOKEN")
ENDED_STATUS=$(echo "$ENDED" | json_get 'data["status"]')
echo "✅ Live session ended (status: $ENDED_STATUS)"
echo ""

# Test 12: Payment request
printf 'Test 12: Create payment request\n-------------------------------\n'
PAYMENT=$(curl -sf -X POST "$BASE_URL/api/organizations/$ORG_ID/payment-requests" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sid": "'"$SID"'",
    "amount": 49.99,
    "currency": "EUR",
    "purpose": "Demo consultation",
    "note": "Smoke test payment",
    "expires_in_hours": 24
  }')
PAYMENT_STATUS=$(echo "$PAYMENT" | json_get 'data["status"]')
PAYMENT_PROVIDER=$(echo "$PAYMENT" | json_get 'data["provider"]')
PAYMENT_URL=$(echo "$PAYMENT" | json_get 'data["payment_url"]')
echo "$PAYMENT" | python3 -m json.tool
echo "✅ Payment request created (status: $PAYMENT_STATUS, provider: $PAYMENT_PROVIDER)"
curl -Is "$PAYMENT_URL" | head -5
printf '\n'

# Test 13: Archive survey
printf 'Test 13: Archive survey\n-----------------------\n'
ARCHIVE_RESPONSE=$(curl -sf -X POST "$BASE_URL/api/organizations/$ORG_ID/surveys/$SURVEY_ID/archive" \
  -H "Authorization: Bearer $TOKEN")
ARCHIVED_STATUS=$(echo "$ARCHIVE_RESPONSE" | json_get 'data["status"]')
echo "✅ Survey archived (status: $ARCHIVED_STATUS)"
echo ""

# Test 14: Delete survey
printf 'Test 14: Delete survey\n----------------------\n'
curl -sf -X DELETE "$BASE_URL/api/organizations/$ORG_ID/surveys/$SURVEY_ID" \
  -H "Authorization: Bearer $TOKEN" > /dev/null
echo "✅ Survey deleted"
echo ""

echo "================================"
echo "✅ All smoke tests passed!"
echo "================================"
