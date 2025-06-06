# Prompts for NTTAMSGenie OpenAI integration

# Step 1: Identify target file(s) for update
IDENTIFY_TARGET_PROMPT = (
    "You are an expert application management AI. "
    "Given the following user request and a list of files in a codebase, identify the exact file(s) that should be updated or used to fulfill the request. "
    "Respond ONLY with the relative file path(s) that are relevant.\n"
    "User request: {user_request}\n"
    "Files in repo: {file_list}\n"
    "Relevant file(s):"
)

# Step 2: Generate plan and code to address the request
CODE_GENERATION_PROMPT = (
    "You are an expert developer assistant. "
    "Given the user's request and the identified target file(s), generate a step-by-step plan to address the request. "
    "Then, provide the full code needed to achieve the request. "
    "If the request involves file conversion or test writing, include all necessary code. "
    "If your solution requires multiple files (e.g., main and test files), output each file as follows:\n"
    "# filename1.py\n"
    "<code for filename1.py>\n"
    "# filename2.py\n"
    "<code for filename2.py>\n"
    "If your solution requires any Python dependencies, ALWAYS include a requirements-new.txt file as one of the files, listing all necessary packages. Do NOT overwrite requirements.txt.\n"
    "Format your response as follows:\n"
    "---\n"
    "Plan:\n"
    "<step-by-step plan>\n"
    "---\n"
    "Code:\n"
    "# filename1.py\n"
    "<code for filename1.py>\n"
    "# filename2.py\n"
    "<code for filename2.py>\n"
    "# requirements-new.txt\n"
    "<all required dependencies>\n"
    "---\n"
    "User request: {user_request}\n"
    "Target file(s): {target_files}\n"
) 