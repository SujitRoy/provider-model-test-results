#!/bin/bash
# This script runs 5 minutes before the main job to ensure venv is ready

export PROJECT_DIR="/home/ubuntu/provider-model-test-results"
export VENV_DIR="${PROJECT_DIR}/venv"
export LOG_FILE="${PROJECT_DIR}/logs/venv_prep.log"

echo "$(date): Preparing virtual environment..." >> ${LOG_FILE}

cd ${PROJECT_DIR}

# Activate venv
source ${VENV_DIR}/bin/activate

# Verify and reinstall if needed
python3 -c "import aiohttp" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "$(date): Reinstalling aiohttp..." >> ${LOG_FILE}
    pip install --upgrade aiohttp python-dotenv >> ${LOG_FILE} 2>&1
fi

# Touch a flag file to indicate venv is ready
touch ${PROJECT_DIR}/logs/venv_ready.flag

deactivate
echo "$(date): Virtual environment ready" >> ${LOG_FILE}
