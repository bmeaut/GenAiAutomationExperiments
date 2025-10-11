#!/bin/bash

# config path
THESIS_REPO_PATH="/home/vesco/llm-analysis-thesis"

echo "Deploying to thesis repo..."

# check if thesis repo exists
if [ ! -d "$THESIS_REPO_PATH" ]; then
    echo "Thesis repo not found at $THESIS_REPO_PATH"
    echo "Please update THESIS_REPO_PATH in the script"
    exit 1
fi

# navigate to thesis repo and pull latest changes
echo "Updating thesis repo..."
cd "$THESIS_REPO_PATH"
git pull origin main

# copy files from main project
echo "Copying files..."
mkdir -p llm_bug_analysis/results/

# copy results.csv and notebook if they exist
cp /home/vesco/GenAiAutomationExperiments/BugFixingAnalysis/llm_bug_analysis/results/results.csv llm_bug_analysis/results/ 2>/dev/null || echo "results.csv not found"
cp /home/vesco/GenAiAutomationExperiments/BugFixingAnalysis/analysis.ipynb . 2>/dev/null || echo "analysis.ipynb not found"

# commit and push
echo "Pushing changes..."

# check if there are any changes
if git diff --quiet && git diff --cached --quiet; then
    echo "No changes to deploy"
else
    git add .
    git commit -m "Auto-update: Results and analysis from $(date '+%Y-%m-%d %H:%M')"
    
    # push with error handling
    if git push; then
        echo "Successfully deployed to thesis repo!"
        echo "Check: https://engemkeres.github.io/llm-analysis-thesis/"
    else
        echo "Failed to push changes"
        exit 1
    fi
fi

echo "Done!"