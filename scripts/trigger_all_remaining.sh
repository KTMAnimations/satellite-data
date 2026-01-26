#!/bin/bash
# Trigger background collections for all remaining regions

API_BASE="http://localhost:8000/api/v1"

# Regions without data (ID | Name)
REGIONS=(
  "91fd310b-cf06-42ef-b241-6ecc1d41daeb|Dallas, TX"
  "5239e375-d2e0-44a5-9fae-f20dfc0af735|San Jose, CA"
  "11d27655-f970-48c2-b3fe-95c2a278a4c5|Austin, TX"
  "35d00577-08c1-450a-b9fb-af18d12fabd5|San Francisco, CA"
  "d2d569d0-15d1-4e08-ba51-c8d42333acc4|Seattle, WA"
  "29e4ad2f-d119-4e65-8f00-9a7ebdfb6d23|Denver, CO"
  "838bd06a-b015-4349-b6df-901a3dd26a68|Boston, MA"
  "698c1a34-ae03-4189-8a75-6b20cb6f6158|Tampa, FL"
  "9edb8519-d5b5-46fd-b1ca-4726f729ba1a|Orlando, FL"
  "a3792809-ba45-43f6-bd3e-df55e8fbfeba|Atlanta, GA"
  "e32b6710-1172-4432-989d-e01db382bb6e|Tokyo, Japan"
  "7de26e29-bc6c-400a-8521-f294ea3c2311|Delhi, India"
  "8188e1f2-4ba5-4ac1-b3b4-ef31b2b00095|Shanghai, China"
  "8e7d06d9-75a1-4887-a36d-4be64b4213b2|Sao Paulo, Brazil"
  "d2f9b5f8-6a6a-495f-8d89-ac0396af9462|Mexico City, Mexico"
  "5ada41b8-c754-4cc6-aada-0a693bf7f5db|Cairo, Egypt"
  "f0b32a5b-4f1d-46c9-b20f-0cde769e246c|Mumbai, India"
  "ef34843f-2b55-4457-bda4-b57eebb1dad8|Beijing, China"
  "f5ef2c38-a3e4-472e-a1e8-2aedb8844497|London, UK"
  "ca947b2c-0c0f-4634-8425-19d5014a0af9|Paris, France"
)

echo "Triggering collections for ${#REGIONS[@]} regions..."
echo "========================================"

for entry in "${REGIONS[@]}"; do
  IFS='|' read -r id name <<< "$entry"
  echo "Triggering: $name"

  result=$(curl -s -X POST "${API_BASE}/collect/${id}/start" \
    -H "Content-Type: application/json" \
    -d '{
      "start_date": "2023-01-01",
      "end_date": "2024-12-31",
      "metrics": ["ndvi", "nightlights", "urban_density", "parking"],
      "granularity": "monthly"
    }' 2>/dev/null)

  task_id=$(echo "$result" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('task_id', 'N/A'))" 2>/dev/null || echo "error")
  echo "  Task: ${task_id:0:8}..."

  # Small delay between triggers
  sleep 1
done

echo "========================================"
echo "All collections triggered!"
