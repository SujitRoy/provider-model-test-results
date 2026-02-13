#!/bin/bash
# ABSOLUTE PATHS - NO ASSUMPTIONS
export PROJECT_DIR="/home/ubuntu/provider-model-test-results"
export VENV_DIR="${PROJECT_DIR}/venv"
export LOG_FILE="${PROJECT_DIR}/logs/cron.log"
export G4F_RESULTS_DIR="/home/ubuntu/g4f-tester/working"

# Create timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Start logging
echo "=========================================" >> ${LOG_FILE}
echo "JOB STARTED AT: ${TIMESTAMP}" >> ${LOG_FILE}
echo "=========================================" >> ${LOG_FILE}

# STEP 1: Change to project directory
cd ${PROJECT_DIR} || {
    echo "ERROR: Cannot cd to ${PROJECT_DIR}" >> ${LOG_FILE}
    exit 1
}

# STEP 2: ACTIVATE VIRTUAL ENVIRONMENT (CRITICAL!)
echo "Activating virtual environment..." >> ${LOG_FILE}
if [ -f "${VENV_DIR}/bin/activate" ]; then
    source ${VENV_DIR}/bin/activate
    echo "VENV activated successfully" >> ${LOG_FILE}
else
    echo "ERROR: Virtual environment not found at ${VENV_DIR}" >> ${LOG_FILE}
    exit 1
fi

# STEP 3: Verify VENV is working
echo "Python path: $(which python3)" >> ${LOG_FILE}
echo "Pip path: $(which pip)" >> ${LOG_FILE}

# Check if required packages are installed
python3 -c "import aiohttp; print('aiohotp version:', aiohttp.__version__)" >> ${LOG_FILE} 2>&1
if [ $? -ne 0 ]; then
    echo "ERROR: aiohttp not installed in venv. Installing now..." >> ${LOG_FILE}
    pip install aiohttp python-dotenv >> ${LOG_FILE} 2>&1
fi

# STEP 4: Run the Python script
echo "Running provider_tester.py..." >> ${LOG_FILE}
python3 ${PROJECT_DIR}/provider_tester.py >> ${LOG_FILE} 2>&1
PYTHON_EXIT_CODE=$?

echo "Python script exit code: ${PYTHON_EXIT_CODE}" >> ${LOG_FILE}

# STEP 5: Copy results from g4f-tester
echo "Copying results files..." >> ${LOG_FILE}
if [ -d "${G4F_RESULTS_DIR}" ]; then
    cp ${G4F_RESULTS_DIR}/working_results.txt ${PROJECT_DIR}/working/ 2>/dev/null && echo "✓ Copied working_results.txt" >> ${LOG_FILE} || echo "✗ No working_results.txt found" >> ${LOG_FILE}
    cp ${G4F_RESULTS_DIR}/working_results_detailed.txt ${PROJECT_DIR}/working/ 2>/dev/null && echo "✓ Copied working_results_detailed.txt" >> ${LOG_FILE} || echo "✗ No detailed results found" >> ${LOG_FILE}
else
    echo "✗ g4f-tester results directory not found" >> ${LOG_FILE}
fi

# STEP 6: Git operations
echo "Git operations..." >> ${LOG_FILE}
cd ${PROJECT_DIR}

# Check if there are changes to commit
if [ -n "$(git status --porcelain working/)" ]; then
    git add working/ >> ${LOG_FILE} 2>&1
    git commit -m "Daily test results - $(date '+%Y-%m-%d')" >> ${LOG_FILE} 2>&1
    git push origin main >> ${LOG_FILE} 2>&1
    echo "✓ Changes committed and pushed" >> ${LOG_FILE}
else
    echo "ℹ No changes to commit" >> ${LOG_FILE}
fi

# STEP 7: Deactivate virtual environment
echo "Deactivating virtual environment..." >> ${LOG_FILE}
deactivate 2>/dev/null || true

echo "=========================================" >> ${LOG_FILE}
echo "JOB COMPLETED AT: $(date '+%Y-%m-%d %H:%M:%S')" >> ${LOG_FILE}
echo "=========================================" >> ${LOG_FILE}
echo "" >> ${LOG_FILE}

exit 0
