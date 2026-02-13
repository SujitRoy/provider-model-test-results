#!/bin/bash
# Test script to verify venv activation works

echo "=== TESTING VENV ACTIVATION ==="
echo ""

echo "1. Without venv (should FAIL):"
python3 -c "import aiohttp; print('✓ aiohttp found')" 2>/dev/null || echo "✗ aiohttp NOT found - GOOD (this should fail)"

echo ""
echo "2. With venv activation (should SUCCEED):"
source /home/ubuntu/provider-model-test-results/venv/bin/activate
python3 -c "import aiohttp; print('✓ aiohttp version:', aiohttp.__version__)" 2>/dev/null && echo "✓ SUCCESS - venv working!" || echo "✗ FAILED - venv not working"
deactivate

echo ""
echo "3. Testing wrapper script:"
/home/ubuntu/provider-model-test-results/scripts/run_tests.sh

echo ""
echo "4. Check log file:"
tail -20 /home/ubuntu/provider-model-test-results/logs/cron.log
