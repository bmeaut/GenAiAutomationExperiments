#!/bin/bash

# change directory if needed
if [ "{has_cwd}" = "true" ]; then
    mkdir -p "{cwd}"
    cd "{cwd}" || {{ echo "Failed to cd to {cwd}"; exit 1; }}
fi

echo "{separator}"
echo "{title}"
echo "{separator}"
echo ""

# run command with or without logging
if [ "{has_log}" = "true" ]; then
    mkdir -p "$(dirname "{log_file}")" # run command, show output and save to file
    {command} 2>&1 | tee "{log_file}"
    EXIT_CODE=${{PIPESTATUS[0]}}
else
    {command}
    EXIT_CODE=$?
fi

echo ""
echo "{separator}"
if [ $EXIT_CODE -eq 0 ]; then
    echo "SUCCESS: {title}"
else
    echo "FAILED: {title} (exit code: $EXIT_CODE)"
fi
echo "{separator}"

echo "$EXIT_CODE" > "{done_file}"

echo ""
echo "Press Enter to close this window..."
read