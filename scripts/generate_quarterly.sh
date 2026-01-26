#!/bin/bash
# Generate quarterly nightlights tiles for 2024 at z11 only

cd /Users/kaivaid/satellite-data

echo "Generating quarterly nightlights tiles for 2024 (z11 only)..."
echo "Months: January, April, July, October"
echo "Zoom: 11"
echo ""

for month in 1 4 7 10; do
    echo "=========================================="
    echo "Processing 2024-$(printf '%02d' $month)..."
    echo "=========================================="
    python scripts/generate_us_tiles.py --year 2024 --month $month --metrics nightlights --zoom 11
done

echo ""
echo "=========================================="
echo "COMPLETE: Quarterly nightlights 2024 z11"
echo "=========================================="
