#!/bin/bash
export PROJECT_DIR="/home/ubuntu/provider-model-test-results"
export VENV_DIR="${PROJECT_DIR}/venv"
export LOG_FILE="${PROJECT_DIR}/logs/cron.log"
export RESULTS_FILE="${PROJECT_DIR}/working/working_results.txt"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "=========================================" >> ${LOG_FILE}
echo "JOB STARTED AT: ${TIMESTAMP}" >> ${LOG_FILE}
echo "=========================================" >> ${LOG_FILE}

cd ${PROJECT_DIR} || {
    echo "ERROR: Cannot cd to ${PROJECT_DIR}" >> ${LOG_FILE}
    exit 1
}

git rev-parse HEAD > /tmp/prev_commit.txt 2>/dev/null || echo "none" > /tmp/prev_commit.txt

echo "Activating virtual environment..." >> ${LOG_FILE}
if [ -f "${VENV_DIR}/bin/activate" ]; then
    source ${VENV_DIR}/bin/activate
    echo "VENV activated successfully" >> ${LOG_FILE}
else
    echo "ERROR: Virtual environment not found at ${VENV_DIR}" >> ${LOG_FILE}
    exit 1
fi

echo "Python path: $(which python3)" >> ${LOG_FILE}
python3 -c "import aiohttp; print('aiohttp version:', aiohttp.__version__)" >> ${LOG_FILE} 2>&1
if [ $? -ne 0 ]; then
    echo "ERROR: aiohttp not installed. Installing..." >> ${LOG_FILE}
    pip install aiohttp python-dotenv >> ${LOG_FILE} 2>&1
fi

echo "Running provider_tester.py..." >> ${LOG_FILE}
python3 ${PROJECT_DIR}/provider_tester.py >> ${LOG_FILE} 2>&1
PYTHON_EXIT_CODE=$?
echo "Python script exit code: ${PYTHON_EXIT_CODE}" >> ${LOG_FILE}

if [ ! -f "${RESULTS_FILE}" ]; then
    echo "ERROR: ${RESULTS_FILE} not found after running tests!" >> ${LOG_FILE}
    deactivate 2>/dev/null || true
    exit 1
fi

echo "Git operations..." >> ${LOG_FILE}
cd ${PROJECT_DIR}

if git status --porcelain "${RESULTS_FILE}" | grep -q "M"; then
    echo "✓ Changes detected in working_results.txt" >> ${LOG_FILE}
    
    git add "${RESULTS_FILE}" >> ${LOG_FILE} 2>&1
    
    git commit -m "Daily test results - $(date '+%Y-%m-%d')" >> ${LOG_FILE} 2>&1
    
    if git push origin main >> ${LOG_FILE} 2>&1; then
        echo "✓ Successfully pushed to GitHub" >> ${LOG_FILE}
        
        echo "Changes in this commit:" >> ${LOG_FILE}
        git show --stat HEAD >> ${LOG_FILE} 2>&1
    else
        echo "✗ Failed to push to GitHub" >> ${LOG_FILE}
    fi
else
    echo "ℹ No changes detected in working_results.txt - skipping commit" >> ${LOG_FILE}
fi

echo "Deactivating virtual environment..." >> ${LOG_FILE}
deactivate 2>/dev/null || true

echo "=========================================" >> ${LOG_FILE}
echo "JOB COMPLETED AT: $(date '+%Y-%m-%d %H:%M:%S')" >> ${LOG_FILE}
echo "=========================================" >> ${LOG_FILE}
echo "" >> ${LOG_FILE}

exit 0
