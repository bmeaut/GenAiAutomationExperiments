import re
import os
import time  # Import the time module for the wait loop


def _extract_diff_from_response(response_text):
    match = re.search(r"```diff\n(.*?)```", response_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return response_text.strip()


def extract_patch_from_llm_response(response: str) -> str:
    """Extracts and cleans patch content from LLM response with better validation."""
    import re

    # remove markdown code block markers
    cleaned = re.sub(r"```diff\s*\n", "", response)
    cleaned = re.sub(r"```\s*$", "", cleaned, flags=re.MULTILINE)

    # extract lines that look like diff content
    lines = cleaned.split("\n")
    patch_lines = []
    in_patch = False

    for line in lines:
        # start collecting when we see file headers
        if line.startswith("---") and ("a/" in line or line.count("/") > 0):
            in_patch = True
            patch_lines.append(line)
        elif in_patch:
            # continue collecting diff content
            if (
                line.startswith(("+++", "@@", " ", "+", "-"))
                or line.strip() == ""
                or (line.startswith("\\") and "No newline" in line)
            ):
                patch_lines.append(line)
            else:
                # stop at non-diff content (but allow some common additions)
                if line.strip() and not any(
                    skip in line.lower()
                    for skip in [
                        "debug",
                        "check",
                        "fix",
                        "change",
                        "minimal",
                        "focused",
                    ]
                ):
                    break

    # clean up the patch
    patch_content = "\n".join(patch_lines)

    # ensure proper line endings
    if patch_content and not patch_content.endswith("\n"):
        patch_content += "\n"

    # validate basic patch structure
    if not _validate_patch_structure(patch_content):
        print("WARNING: Generated patch has structural issues")

    return patch_content


def _validate_patch_structure(patch_content: str) -> bool:
    """Basic validation of patch structure."""
    lines = patch_content.splitlines()
    has_file_header = False
    has_hunk_header = False

    for line in lines:
        if line.startswith("---"):
            has_file_header = True
        elif line.startswith("@@"):
            has_hunk_header = True

    return has_file_header and has_hunk_header


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

    # Read response, extract patch, clean up
    with open(response_file_path, "r", encoding="utf-8") as f:
        llm_response = f.read()

    os.remove(prompt_file_path)
    os.remove(response_file_path)

    extracted_patch = _extract_diff_from_response(llm_response)
    print("Patch extracted successfully. Resuming analysis...")
    return extracted_patch


def generate_fix_with_openai(bug_data, file_contents):
    print("\n--- Using Model: Manual (OpenAI Placeholder) ---")
    return generate_fix_manually(bug_data, file_contents)


def generate_fix_with_anthropic(bug_data, file_contents):
    print("\n--- Using Model: Manual (Anthropic Placeholder) ---")
    return generate_fix_manually(bug_data, file_contents)
