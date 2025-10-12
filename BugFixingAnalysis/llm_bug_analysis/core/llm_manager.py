import re
import os
import time  # Import the time module for the wait loop


def extract_patch_from_llm_response(response_text: str) -> str | None:
    """
    Extract the diff patch from LLM response.
    Returns None if no valid patch is found.
    """
    print("=" * 60)
    print("DEBUG: Starting patch extraction")
    print(f"DEBUG: Response length: {len(response_text)} chars")
    print(f"DEBUG: First 100 chars: {response_text[:100]}")
    print(f"DEBUG: Last 100 chars: {response_text[-100:]}")

    # Find the diff block - flexible with any amount of whitespace before closing ```
    diff_pattern = r"```diff\s*\n(.*?)\s*```"
    match = re.search(diff_pattern, response_text, re.DOTALL)

    if not match:
        print("DEBUG: FAILED - No match with pattern r'```diff\\s*\\n(.*?)\\s*```'")

        # Try to find where the diff block is
        if "```diff" in response_text:
            print("DEBUG: Found '```diff' in response")
            idx = response_text.index("```diff")
            print(f"DEBUG: Located at position {idx}")
            print(f"DEBUG: Context (50 chars before and after):")
            print(repr(response_text[max(0, idx - 50) : idx + 100]))
        else:
            print("DEBUG: '```diff' not found in response at all!")

        if "```" in response_text:
            count = response_text.count("```")
            print(f"DEBUG: Found {count} occurrences of '```'")

        return None

    print("DEBUG: SUCCESS - Match found!")
    patch = match.group(1)

    patch = _clean_patch(patch)

    print(f"DEBUG: Extracted patch length: {len(patch)} chars")
    print(f"DEBUG: First 200 chars of patch:")
    print(repr(patch[:200]))
    print(f"DEBUG: Last 100 chars of patch:")
    print(repr(patch[-100:]))

    # Clean up: remove trailing whitespace but ensure single trailing newline
    patch = patch.rstrip() + "\n"

    print(f"DEBUG: After cleanup, patch length: {len(patch)} chars")

    # Basic validation
    if not patch.startswith("--- "):
        print(
            f"DEBUG: FAILED - Patch doesn't start with '--- a/', starts with: {repr(patch[:30])}"
        )
        return None

    print("DEBUG: Patch starts with '--- a/' ✓")

    if "\n+++ " not in patch:
        print("DEBUG: FAILED - Patch missing '+++ b/' line")
        return None

    print("DEBUG: Patch has '+++ b/' line ✓")
    print("DEBUG: Patch extraction successful!")
    print("=" * 60)

    return patch


def _clean_patch(patch: str) -> str:
    """
    Clean up common issues in extracted patches.
    """
    lines = patch.split("\n")
    cleaned = []

    for line in lines:
        # remove trailing whitespace from all lines except additions
        if line.startswith("+"):
            # keep additions exactly as-is
            cleaned.append(line)
        elif line.startswith("-"):
            # remove trailing whitespace from deletions
            cleaned.append(line.rstrip())
        elif (
            line.startswith(" ")
            or line.startswith("@@")
            or line.startswith("---")
            or line.startswith("+++")
        ):
            # context lines and headers - remove trailing whitespace
            cleaned.append(line.rstrip())
        elif line.strip() == "":
            # empty lines - keep completely empty (no spaces)
            cleaned.append("")
        else:
            # unknown line type, keep as-is but strip trailing
            cleaned.append(line.rstrip())

    # ensure single trailing newline
    result = "\n".join(cleaned)
    if not result.endswith("\n"):
        result += "\n"

    return result


def generate_fix_manually(bug_data, code_context_snippets):
    """
    File-based interaction for manual LLM input (while I figure out API and Agent access).
    """
    script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(script_path))
    prompt_file_path = os.path.join(project_root, "prompt_for_llm.txt")
    response_file_path = os.path.join(project_root, "llm_response.txt")

    # clean up old response
    if os.path.exists(response_file_path):
        os.remove(response_file_path)

    # construct prompt
    prompt_template_path = os.path.join(project_root, "prompts", "generate_fix.txt")
    try:
        with open(prompt_template_path, "r") as f:
            prompt_template = f.read()
    except FileNotFoundError:
        print(f"ERROR: Prompt template file not found at {prompt_template_path}")
        prompt_template = ""

    code_context = ""
    for context_key, snippet in code_context_snippets.items():
        code_context += f"\n--- {context_key} ---\n```python\n{snippet}\n```\n"

    # fill out prompt
    full_prompt = prompt_template.format(
        issue_title=bug_data.get("issue_title", "N/A"),
        issue_body=bug_data.get("issue_body", "No issue body provided."),
        code_context=code_context,
    )

    with open(prompt_file_path, "w", encoding="utf-8") as f:
        f.write(full_prompt)

    # manual step instructions
    print("\n" + "=" * 60)
    print("ACTION REQUIRED: FILE-BASED LLM INTERACTION")
    print("=" * 60)
    print(f"\nSTEP 1: A prompt has been saved to the file:\n  --> {prompt_file_path}")
    print("\nSTEP 2: Copy the content of that file and paste it into your chatbot.")
    print(
        f"\nSTEP 3: Save the chatbot's complete response into a new file named:\n  --> {response_file_path}"
    )
    print(
        "\n         (The script will automatically detect the file once you save it.)"
    )
    print("\n" + "=" * 60)

    print("\nWaiting for response file...", end="")
    while not os.path.exists(response_file_path):
        print(".", end="", flush=True)
        time.sleep(2)

    print("\nResponse file detected!")

    # read response, extract patch, clean up
    with open(response_file_path, "r", encoding="utf-8") as f:
        llm_response = f.read()

    os.remove(prompt_file_path)
    os.remove(response_file_path)

    # return the full response, not the extracted patch
    # the pipeline will handle extraction
    return llm_response


def generate_fix_with_openai(bug_data, file_contents):
    print("\n--- Using Model: Manual (OpenAI Placeholder) ---")
    return generate_fix_manually(bug_data, file_contents)


def generate_fix_with_anthropic(bug_data, file_contents):
    print("\n--- Using Model: Manual (Anthropic Placeholder) ---")
    return generate_fix_manually(bug_data, file_contents)
