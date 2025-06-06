import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import git
from openai import AzureOpenAI
from prompts import IDENTIFY_TARGET_PROMPT, CODE_GENERATION_PROMPT
import subprocess
from fastapi import Body
from typing import Dict
from github import Github
import datetime
from openai import AzureOpenAI
from fastapi import APIRouter, Request
from pydantic import BaseModel
import git



load_dotenv(override=True)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

OPENAI_ENDPOINT = os.getenv("OPENAI_ENDPOINT")
OPENAI_KEY = os.getenv("OPENAI_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
OPENAI_DEPLOYMENT = os.getenv("OPENAI_MODEL", "gpt-4.1")
OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION", "2024-12-01-preview")




app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    github_link: str

# Helper to recursively list files in a directory
def list_files(start_path):
    file_list = []
    for root, dirs, files in os.walk(start_path):
        for file in files:
            rel_path = os.path.relpath(os.path.join(root, file), start_path)
            file_list.append(rel_path)
    return file_list

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    repo_path = None
    plan = code = target_files = None
    if req.github_link:
        repo_name = req.github_link.rstrip('/').split('/')[-1].replace('.git', '')
        repo_path = os.path.join(BACKEND_DIR, 'data', repo_name)
        if not os.path.exists(repo_path):
            git.Repo.clone_from(req.github_link, repo_path)
        # Step 1: List files
        files = list_files(repo_path)
        files_str = ', '.join(files)
        # Step 2: Identify target file(s)
        client = AzureOpenAI(
            api_version=OPENAI_API_VERSION,
            azure_endpoint=OPENAI_ENDPOINT,
            api_key=OPENAI_KEY,
        )
        identify_prompt = IDENTIFY_TARGET_PROMPT.format(user_request=req.message, file_list=files_str)
        response1 = client.chat.completions.create(
            stream=False,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": identify_prompt},
            ],
            max_completion_tokens=300,
            temperature=0.2,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            model=OPENAI_DEPLOYMENT,
        )
        target_files = response1.choices[0].message.content.strip()
        # Step 3: Generate plan and code
        code_prompt = CODE_GENERATION_PROMPT.format(user_request=req.message, target_files=target_files)
        response2 = client.chat.completions.create(
            stream=False,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": code_prompt},
            ],
            max_completion_tokens=1200,
            temperature=0.5,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            model=OPENAI_DEPLOYMENT,
        )
        full_response = response2.choices[0].message.content.strip()
        # Try to parse plan and code
        plan, code = None, None
        code_files = {}
        if '---' in full_response:
            parts = full_response.split('---')
            for part in parts:
                if part.strip().startswith('Plan:'):
                    plan = part.strip()[5:].strip()
                if part.strip().startswith('Code:'):
                    code = part.strip()[5:].strip()
        else:
            code = full_response
        # Parse multiple files from code block using # filename.py delimiter
        if code:
            import re
            file_blocks = re.split(r'(?m)^# (\S+)$', code)
            # file_blocks[0] is before the first file, skip it
            for i in range(1, len(file_blocks), 2):
                filename = file_blocks[i].strip()
                file_content = file_blocks[i+1].strip()
                code_files[filename] = file_content
        # Optionally, save code to file (if filename is mentioned in plan or code)
        client.close()
        # Save generated Python files to the repo directory
        if code_files and repo_path:
            for filename, filecontent in code_files.items():
                if filename.endswith('.py') or filename.endswith('.txt'):
                    save_dir = repo_path
                    os.makedirs(save_dir, exist_ok=True)
                    file_path = os.path.join(save_dir, filename)
                    try:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(filecontent)
                    except Exception as e:
                        print(f'Error saving {filename}:', e)
        return {
            "plan": plan,
            "code_files": code_files,
            "target_files": target_files,
            "response": "Plan and code generated."
        }
    return {"response": f"Repo cloned to {repo_path if repo_path else 'N/A'}"}

@app.post('/execute')
async def execute_code(request: Request):
    data = await request.json()
    filename = data.get('filename')
    code = data.get('code')
    repo_name = data['repo_name']
    command = data.get('command')
    repo_path = os.path.join(BACKEND_DIR, 'data', repo_name)
    if filename and code:
        file_path = os.path.join(repo_path, filename)
        os.makedirs(repo_path, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
    # Execute code
    try:
        if command:
            cmd = command.split()
        else:
            cmd = ['python3', filename]
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=10, cwd=repo_path
        )
        return {'stdout': result.stdout, 'stderr': result.stderr}
    except Exception as e:
        return {'stdout': '', 'stderr': str(e)}

@app.post('/install_requirements')
async def install_requirements(request: Request):
    data = await request.json()
    repo_name = data['repo_name']
    repo_path = os.path.join(BACKEND_DIR, 'data', repo_name)
    req_file = os.path.join(repo_path, 'requirements.txt')
    req_new_file = os.path.join(repo_path, 'requirements-new.txt')
    # If requirements-new.txt exists, append its contents to requirements.txt (deduplicated)
    if os.path.isfile(req_new_file):
        existing = set()
        if os.path.isfile(req_file):
            with open(req_file, 'r', encoding='utf-8') as f:
                existing = set(line.strip() for line in f if line.strip())
        with open(req_new_file, 'r', encoding='utf-8') as f:
            new_lines = [line.strip() for line in f if line.strip()]
        combined = list(existing.union(new_lines))
        with open(req_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(combined) + '\n')
    if not os.path.isfile(req_file):
        return {'stdout': '', 'stderr': 'requirements.txt not found'}
    try:
        result = subprocess.run(
            ['pip', 'install', '-r', req_file],
            capture_output=True, text=True, timeout=60, cwd=repo_path
        )
        return {'stdout': result.stdout, 'stderr': result.stderr}
    except Exception as e:
        return {'stdout': '', 'stderr': str(e)} 

@app.post("/studio/pr")
async def studio_pr(
    repo_path: str = Body(...),
    files: Dict[str, str] = Body(...),
    original_query: str = Body(...),
    username: str = Body(...),
    pr_title: str = Body(...),
    pr_description: str = Body("")
):
    """
    Studio PR endpoint: saves files, creates branch, commits, pushes, generates PR, creates draft PR on GitHub.
    """
    

    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    GITHUB_ORG = os.getenv("GITHUB_ORG")

    try:
        # 1. Auto-generate branch name
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        branch_name = f"feature/{username}/{timestamp}"
        repo = git.Repo(repo_path)
        # 2. Create and checkout new branch
        repo.git.checkout('main')
        repo.git.pull()
        repo.git.checkout('-b', branch_name)
        # 3. Save files
        for fname, content in files.items():
            fpath = os.path.join(repo_path, fname)
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(content)
        # 4. Add, commit, push
        repo.git.add(A=True)
        commit_msg = f"[Studio] {pr_title}"
        repo.git.commit('-m', commit_msg)
        repo.git.push('--set-upstream', 'origin', branch_name)
        # 5. Generate PR description using OpenAI (optional, you can use pr_description or original_query)
        diff = repo.git.diff('main', branch_name)
        openai_prompt = f"""You are an expert software engineer. Write a professional pull request description for the following changes. kindly write a detailed description of the changes made in the PR. Self analyze the strengths and weaknesses of the changes and provide a detailed analysis of the changes. ask for specific review from user based on diff and do also note any limitations of the changes.

        Original user request: {original_query}

        Git diff between main and {branch_name}:
        {diff}
        """
        client = AzureOpenAI(
            api_version=OPENAI_API_VERSION,
            azure_endpoint=OPENAI_ENDPOINT,
            api_key=OPENAI_KEY,
        )
        response = client.chat.completions.create(
            stream=False,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that writes clear and professional PR descriptions. kindly write a detailed description of the changes made in the PR. Self analyze the strengths and weaknesses of the changes and provide a detailed analysis of the changes. ask for specific review from user based on diff and do also note any limitations of the changes."},
                {"role": "user", "content": openai_prompt}
            ],
            max_completion_tokens=800,
            temperature=0.7,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            model=OPENAI_DEPLOYMENT,
        )
        pr_body = response.choices[0].message.content.strip()

        print(f"pr_body: {pr_body}")
        if not pr_body:
            print('WARNING: OpenAI PR description is empty!')
        # 6. Create draft PR on GitHub
        repo_url = repo.remotes.origin.url
        repo_name = repo_url.split(":")[-1].replace(".git","").split("/")[-1]
        g = Github(GITHUB_TOKEN)
        if GITHUB_ORG:
            gh_repo = g.get_organization(GITHUB_ORG).get_repo(repo_name)
        else:
            gh_repo = g.get_user().get_repo(repo_name)
        pr = gh_repo.create_pull(
            title=pr_title,
            body=pr_body,
            head=branch_name,
            base="main",
            draft=True
        )
        return {
                    "pr_url": pr.html_url,
                    "status": "success",
                    "pr_title": pr_title,
                    "pr_description": pr_body
               }
    except Exception as e:
        return {"status": "error", "error": str(e)}

class PRUpdateRequest(BaseModel):
    pr_url: str
    title: str
    body: str

@app.post("/studio/pr/update")
async def update_pr(req: PRUpdateRequest):
    try:
        g = Github(os.getenv("GITHUB_TOKEN"))
        pr_url = req.pr_url.split('?', 1)[0].split('#', 1)[0]
        print("Received pr_url:", pr_url)
        # Extract owner/repo and PR number from pr_url
        import re
        m = re.match(r'https://github.com/([^/]+)/([^/]+)/pull/(\d+)', pr_url)
        if not m:
            return {"status": "error", "error": "Invalid PR URL"}
        owner, repo, pr_number = m.group(1), m.group(2), int(m.group(3))
        gh_repo = g.get_repo(f"{owner}/{repo}")
        pr = gh_repo.get_pull(pr_number)
        pr.edit(title=req.title, body=req.body)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "error": str(e)}