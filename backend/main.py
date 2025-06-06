import os
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import git
from openai import AzureOpenAI
from prompts import IDENTIFY_TARGET_PROMPT, CODE_GENERATION_PROMPT
import subprocess
from code_change_handler import CodeChangeHandler
from typing import List, Dict, Optional
from github import Github
import time
import datetime
import traceback
import re

load_dotenv()

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# Get environment variables - using the exact names Azure OpenAI client expects
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("OPENAI_ENDPOINT")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
OPENAI_DEPLOYMENT = os.getenv("OPENAI_MODEL", "gpt-4.1")  # Using same as model
OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION", "2024-12-01-preview")

# Validate required environment variables
if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_API_KEY:
    raise ValueError("Missing required environment variables: AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be set")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_ORG = os.getenv("GITHUB_ORG")

app = FastAPI()

# Update CORS middleware with more specific settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Your React app's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

class ChatRequest(BaseModel):
    message: str
    github_link: str
    username: str = "kkahol-toronto"
    descriptive_name: str

class BranchInfo(BaseModel):
    name: str
    is_current: bool
    last_commit: str
    last_commit_date: str

class PRRequest(BaseModel):
    repo_path: str
    source_branch: str
    target_branch: str = "main"
    title: str
    description: str

class PRResponse(BaseModel):
    pr_url: Optional[str]
    diff_files: List[Dict[str, str]]
    pr_content: str

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "detail": "An unexpected error occurred"}
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test OpenAI connection
        client = AzureOpenAI(
            api_version=OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
        )
        return {
            "status": "healthy",
            "openai_connection": "ok",
            "environment": {
                "azure_openai_endpoint": AZURE_OPENAI_ENDPOINT is not None,
                "azure_openai_api_key": AZURE_OPENAI_API_KEY is not None,
                "openai_model": OPENAI_MODEL,
                "openai_api_version": OPENAI_API_VERSION
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        repo_path = None
        plan = code = target_files = None
        if not req.github_link:
            raise HTTPException(status_code=400, detail="GitHub link is required")
            
        repo_name = req.github_link.rstrip('/').split('/')[-1].replace('.git', '')
        repo_path = os.path.join(BACKEND_DIR, 'data', repo_name)
        
        # Create data directory if it doesn't exist
        os.makedirs(os.path.join(BACKEND_DIR, 'data'), exist_ok=True)
        
        if not os.path.exists(repo_path):
            try:
                git.Repo.clone_from(req.github_link, repo_path)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to clone repository: {str(e)}")
                
        # Initialize code handler and create/checkout branch
        try:
            code_handler = CodeChangeHandler(repo_path)
            branch_name = code_handler.create_or_checkout_branch(req.username, req.descriptive_name)
            if not branch_name:
                raise HTTPException(status_code=400, detail="Failed to create/checkout branch")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error with code handler: {str(e)}")

        # Initialize OpenAI client with your environment variables
        client = AzureOpenAI(
            api_version=OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
        )
            
        # Step 1: List files
        files = list_files(repo_path)
        files_str = ', '.join(files)
        
        # Rest of your existing code...
        
        # After saving generated files, create PR
        if code_files and repo_path:
            for filename, filecontent in code_files.items():
                if filename.endswith('.py') or filename.endswith('.txt'):
                    save_dir = repo_path
                    os.makedirs(save_dir, exist_ok=True)
                    file_path = os.path.join(save_dir, filename)
                    try:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(filecontent)
                        # Accept changes through code handler
                        code_handler.accept_changes(
                            file_path,
                            filecontent,
                            f"Generated code for {filename}"
                        )
                    except Exception as e:
                        print(f'Error saving {filename}:', e)
            
            # Create PR with all changes
            pr_description = code_handler.create_pull_request(req.message)
            if pr_description:
                return {
                    "status": "success",
                    "message": "Request processed successfully",
                    "branch_name": branch_name,
                    "repo_path": repo_path,
                    "pr_description": pr_description
                }
        
        return {
            "status": "success",
            "message": "Request processed successfully",
            "branch_name": branch_name,
            "repo_path": repo_path
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/branches/{repo_path:path}")
async def get_branches(repo_path: str):
    """Get all branches for a repository"""
    try:
        repo = git.Repo(repo_path)
        branches = []
        current = repo.active_branch.name
        
        for branch in repo.heads:
            commit = branch.commit
            branches.append(BranchInfo(
                name=branch.name,
                is_current=(branch.name == current),
                last_commit=commit.hexsha[:7],
                last_commit_date=commit.committed_datetime.isoformat()
            ))
        
        return {"branches": branches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/pr/generate")
async def generate_pr(req: PRRequest):
    """Generate PR content and diff"""
    try:
        repo = git.Repo(req.repo_path)
        
        # Get diff between branches
        source = repo.heads[req.source_branch]
        target = repo.heads[req.target_branch]
        
        # Get diff files
        diff_files = []
        for diff in source.commit.diff(target.commit):
            if diff.a_path:
                diff_files.append({
                    "path": diff.a_path,
                    "status": diff.change_type,
                    "diff": diff.diff.decode('utf-8', errors='ignore')
                })
        
        # Generate PR content using OpenAI
        code_handler = CodeChangeHandler(req.repo_path)
        pr_content = code_handler.generate_pr_description(
            f"Title: {req.title}\n\nDescription: {req.description}\n\nFiles changed:\n" + 
            "\n".join([f"- {f['path']} ({f['status']})" for f in diff_files])
        )
        
        return PRResponse(
            pr_url=None,  # Will be set when PR is actually created
            diff_files=diff_files,
            pr_content=pr_content
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/pr/create")
async def create_pr(req: PRRequest):
    """Create the actual PR"""
    try:
        code_handler = CodeChangeHandler(req.repo_path)
        pr_url = code_handler.create_pull_request(
            f"Title: {req.title}\n\nDescription: {req.description}"
        )
        
        return {"pr_url": pr_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_github_repo(repo_name):
    g = Github(GITHUB_TOKEN)
    org = g.get_organization(GITHUB_ORG)
    return org.get_repo(repo_name)

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
    import git
    import os
    import traceback

    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    GITHUB_ORG = os.getenv("GITHUB_ORG")
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("OPENAI_ENDPOINT")
    OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION", "2024-12-01-preview")
    OPENAI_DEPLOYMENT = os.getenv("OPENAI_MODEL", "gpt-4.1")

    try:
        # Auto-clone repo if not present or not a git repo
        if not os.path.exists(repo_path) or not os.path.exists(os.path.join(repo_path, '.git')):
            repo_name = os.path.basename(repo_path)
            if GITHUB_ORG:
                remote_url = f"https://github.com/{GITHUB_ORG}/{repo_name}.git"
            else:
                remote_url = f"https://github.com/{username}/{repo_name}.git"
            git.Repo.clone_from(remote_url, repo_path)
        
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
        # 5. Generate PR description using OpenAI
        diff = repo.git.diff('main', branch_name)
        openai_prompt = f"""You are an expert software engineer. Write a professional pull request description for the following changes.\n\nOriginal user request: {original_query}\n\nGit diff between main and {branch_name}:\n{diff}\n"""
        client = AzureOpenAI(
            api_version=OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
        )
        response = client.chat.completions.create(
            stream=False,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that writes clear and professional PR descriptions."},
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
        print('OpenAI PR description:', pr_body)
        print('OpenAI prompt sent:', openai_prompt)
        print('OpenAI API response:', response)
        if not pr_body:
            print('WARNING: OpenAI PR description is empty!')
        # 6. Create draft PR on GitHub
        repo_url = repo.remotes.origin.url
        repo_name = repo_url.split(":")[-1].replace(".git","").split("/")[-1]
        g = Github(GITHUB_TOKEN)
        gh_repo = None
        if GITHUB_ORG:
            try:
                gh_repo = g.get_organization(GITHUB_ORG).get_repo(repo_name)
            except Exception:
                gh_repo = g.get_user().get_repo(repo_name)
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
            "pr_description": pr_body,
            "pr_title": pr_title
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "trace": traceback.format_exc()}

@app.post("/studio/pr/update")
async def update_pr(pr_url: str = Body(...), title: str = Body(...), body: str = Body(...)):
    """
    Update the PR title and body on GitHub.
    """
    import os
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    g = Github(GITHUB_TOKEN)
    # Extract owner/repo and PR number from the URL
    m = re.match(r'https://github.com/([^/]+)/([^/]+)/pull/(\d+)', pr_url)
    if not m:
        return {"status": "error", "error": "Invalid PR URL"}
    owner, repo_name, pr_number = m.groups()
    repo = g.get_repo(f"{owner}/{repo_name}")
    pr = repo.get_pull(int(pr_number))
    pr.edit(title=title, body=body)
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 