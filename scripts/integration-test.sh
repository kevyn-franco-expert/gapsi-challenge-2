#!/usr/bin/env bash
set -euo pipefail

BASE_URL_ORDERS="${ORDERS_URL:-http://localhost:8000}"
BASE_URL_NOTIFIER="${NOTIFIER_URL:-http://localhost:8002}"
CUSTOMER_ID="cust-$(date +%s)"
IDEMPOTENCY_KEY="idem-$(uuidgen 2>/dev/null || date +%s%N)"

echo "=== Cafe Cloud Integration Test ==="
echo "Customer: $CUSTOMER_ID"
echo "Idempotency-Key: $IDEMPOTENCY_KEY"

# 1. Create order
echo "Creating order..."
ORDER_RESPONSE=$(curl -s -X POST "$BASE_URL_ORDERS/orders" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $IDEMPOTENCY_KEY" \
  -d "{\"customer_id\":\"$CUSTOMER_ID\",\"items\":[{\"name\":\"latte\",\"qty\":1},{\"name\":\"muffin\",\"qty\":2}]}")
echo "Response: $ORDER_RESPONSE"
ORDER_ID=$(echo "$ORDER_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['order_id'])")
echo "Order ID: $ORDER_ID"

# 2. Idempotency check
echo "Retrying same Idempotency-Key..."
IDEMPOTENT_RESPONSE=$(curl -s -X POST "$BASE_URL_ORDERS/orders" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $IDEMPOTENCY_KEY" \
  -d "{\"customer_id\":\"$CUSTOMER_ID\",\"items\":[{\"name\":\"latte\",\"qty\":1}]}")
echo "Response: $IDEMPOTENT_RESPONSE"
IDEMPOTENT_ORDER_ID=$(echo "$IDEMPOTENT_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['order_id'])")
if [ "$ORDER_ID" != "$IDEMPOTENT_ORDER_ID" ]; then
  echo "ERROR: Idempotency failed! Different order IDs returned."
  exit 1
fi
echo "Idempotency OK"

# 3. Wait for processor + notifier
echo "Waiting for processor and notifier..."
for i in $(seq 1 30); do
  NOTIFICATIONS=$(curl -s "$BASE_URL_NOTIFIER/notifications/$CUSTOMER_ID")
  COUNT=$(echo "$NOTIFICATIONS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
  if [ "$COUNT" -gt 0 ]; then
    echo "Notifications received: $COUNT"
    break
  fi
  sleep 1
done

if [ "$COUNT" -eq 0 ]; then
  echo "ERROR: No notifications found after 30 seconds."
  exit 1
fi

echo ""
echo "=== Integration test passed ==="
echo "Notifications: $NOTIFICATIONS"
