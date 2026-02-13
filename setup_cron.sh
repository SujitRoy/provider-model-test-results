#!/bin/bash
echo "Setting up daily cron job for provider testing..."

REPO_PATH=$(pwd)
PYTHON_PATH=$(which python3)

CRON_CMD="0 1 * * * cd $REPO_PATH && $PYTHON_PATH provider_tester.py && cd $REPO_PATH && git add working/working_results.txt && git commit -m \"Daily test results - \$(date +\\%Y-\\%m-\\%d)\" && git push >> $REPO_PATH/logs/cron.log 2>&1"

(crontab -l 2>/dev/null | grep -v "$REPO_PATH"; echo "$CRON_CMD") | crontab -

mkdir -p logs

echo "✓ Cron job installed successfully!"
echo "✓ Schedule: Daily at 1:00 AM UTC"
echo "✓ Logs: $REPO_PATH/logs/cron.log"
