# A Framework for Analysis of LLMs in Debugging and Software Modification

This repository contains the source code and experimental data for a thesis project analyzing the effectiveness of Large Language Models (LLMs) in fixing real-world software bugs.

The core of this project is a semi-automated Python tool that systematically benchmarks LLM performance against human-written solutions from popular open-source Python repositories.

**For a full, interactive project description and a detailed analysis of the results, please visit the official project website:**

**[https://engemkeres.github.io/llm-analysis-thesis/](https://engemkeres.github.io/llm-analysis-thesis/)**


### PS: The tools development and the thesis is still in progress.
---

## Thesis Objective

The primary research question is: **How do the bug-fixing capabilities of modern LLMs compare to those of human developers when applied to real-world software projects?**

To answer this, the tool implements the following methodology:
1.  **Corpus Creation:** It mines GitHub repositories to build a quality dataset of bug-fix commits linked to their original issue reports.
2.  **Context Extraction:** *in progress*
3.  **Automated Test Harness:** It creates a fully isolated virtual environment for each bug, installs the project's exact dependencies, and applies the proposed code patch.
4.  **Empirical Validation:** It runs the project's own comprehensive test suite against both the LLM's fix and the original human's fix, providing an objective measure of correctness.
5.  **Metric Collection:** It gathers software engineering metrics (Cyclomatic Complexity, Cognitive Complexity, etc.) to assess the quality and maintainability of the generated solutions.

The final dataset, `results.csv`, is the foundation of the analysis.

## Getting Started

### Prerequisites

- **WSL (Windows Subsystem for Linux):** The tool is designed and tested in a WSL/Ubuntu environment.
- **Python:** Python 3.9+ is required.
- **Git:** For cloning repositories.
- **GitHub Personal Access Token:** Required for the corpus builder to interact with the GitHub API.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/bmeaut/GenAiAutomationExperiments.git
    cd GenAiAutomationExperiments/BugFixingAnalysis
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    This project uses `pip-tools` for dependency management.
    ```bash
    pip install pip-tools
    pip-compile requirements.in
    pip install -r requirements.txt
    ```

4.  **Set up your API Key:**
    Create a `.env` file in the `BugFixingAnalysis` root directory.
    ```    # .env
    GITHUB_TOKEN="ghp_YourPersonalAccessTokenHere"
    ```

## How to Use the Tool

The application is controlled via a simple graphical user interface.

1.  **Launch the GUI:**
    ```bash
    python llm_bug_analysis/main.py
    ```

2.  **Build a Bug Corpus:**
    - Add one or more target repositories (e.g., `Textualize/rich`) in the GUI.
    - Click the **"1. Build Bug Corpus"** button. The tool will scan the repositories and populate the "Bug Corpus" list with valid, issue-linked bug fixes.

3.  **Run the Analysis:**
    - **Full Run:** Click the **"2. Run Analysis Pipeline"** button to process the entire corpus.
    - **Single Run:** Select a specific commit from the "Bug Corpus" list and click **"Run Selected"**.
    - **Dry Run:** Check the "Skip LLM Fix" box to run the pipeline without the manual LLM step, which is useful for quickly validating a project's test setup.

4.  **Manual LLM Interaction (if not skipped): This is a placeholder until API or Agent integration is added.**
    - The tool will create a `prompt_for_llm.txt` file in the project root.
    - Copy the contents of this file into your preferred chatbot.
    - Save the chatbot's complete response into a new file named `llm_response.txt` in the same directory.
    - The tool will automatically detect the new file and continue the analysis.

## Project Structure

-   `llm_bug_analysis/`: The main source code for the analysis tool.
    -   `core/`: The backend logic (pipeline, project handler, etc.).
    -   `gui/`: The Tkinter-based user interface.
-   `config.json`: Configuration for target repositories and test exclusions.
-   `results/`: The output directory for the final `results.csv` and detailed test failure logs.
-   `analysis.ipynb`: A Jupyter Notebook for analyzing the data from `results.csv`.