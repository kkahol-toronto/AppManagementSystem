import os
import subprocess
import tempfile
from typing import List, Dict, Optional
import git
from git import Repo
import pylint.lint
import pytest
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

# Get environment variables - using the exact names Azure OpenAI client expects
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("OPENAI_ENDPOINT")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
OPENAI_DEPLOYMENT = os.getenv("OPENAI_MODEL", "gpt-4.1")  # Using same as model
OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION", "2024-12-01-preview")

class CodeChangeHandler:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.changes: Dict[str, str] = {}  # file_path -> change_description
        
        # Initialize OpenAI client
        self.openai_client = AzureOpenAI(
            api_version=OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
        )
        
        # Initialize git repository if it doesn't exist
        if not os.path.exists(os.path.join(repo_path, '.git')):
            try:
                self.repo = Repo.init(repo_path)
                # Create initial commit if repository is empty
                if not self.repo.heads:
                    self.repo.index.commit("Initial commit")
            except Exception as e:
                print(f"Error initializing git repository: {str(e)}")
                self.repo = None
        else:
            try:
                self.repo = Repo(repo_path)
            except Exception as e:
                print(f"Error opening git repository: {str(e)}")
                self.repo = None

    def create_or_checkout_branch(self, username: str, descriptive_name: str) -> Optional[str]:
        """
        Create or checkout a branch with format feature/username/descriptive-name
        """
        if not self.repo:
            print("No git repository available")
            return None

        try:
            # Format branch name
            branch_name = f"feature/{username}/{descriptive_name.lower().replace(' ', '-')}"
            
            # Check if branch exists
            if branch_name in self.repo.heads:
                # Checkout existing branch
                self.repo.heads[branch_name].checkout()
            else:
                # Create and checkout new branch
                current = self.repo.create_head(branch_name)
                current.checkout()
            
            return branch_name
        except Exception as e:
            print(f"Error managing branch: {str(e)}")
            return None
        
    def accept_changes(self, file_path: str, new_content: str, change_description: str) -> bool:
        """
        Accept changes for a specific file and store the change description.
        """
        try:
            # Validate the file path
            abs_path = os.path.join(self.repo_path, file_path)
            if not os.path.exists(abs_path):
                raise FileNotFoundError(f"File {file_path} does not exist")
            
            # Run pylint on the new content
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
                temp_file.write(new_content)
                temp_file.flush()
                
                pylint_output = subprocess.run(
                    ['pylint', temp_file.name],
                    capture_output=True,
                    text=True
                )
                
                if pylint_output.returncode != 0:
                    print(f"Pylint issues found:\n{pylint_output.stdout}")
                    return False
            
            # Store the changes
            self.changes[file_path] = change_description
            
            # Write the new content
            with open(abs_path, 'w') as f:
                f.write(new_content)
                
            return True
            
        except Exception as e:
            print(f"Error accepting changes: {str(e)}")
            return False

    def generate_pr_description(self, original_prompt: str) -> str:
        """
        Generate PR description using OpenAI based on changes and original prompt
        """
        try:
            # Create a summary of changes
            changes_summary = "\n".join([f"- {file}: {desc}" for file, desc in self.changes.items()])
            
            prompt = f"""Based on the following information, generate a detailed PR description:

Original Request: {original_prompt}

Changes Made:
{changes_summary}

Please provide a comprehensive PR description that includes:
1. A clear title summarizing the changes
2. A detailed description of what was changed and why
3. Any potential impacts or considerations
4. Testing performed
"""

            response = self.openai_client.chat.completions.create(
                stream=False,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that writes clear and professional PR descriptions."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=800,
                temperature=0.7,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0,
                model=OPENAI_DEPLOYMENT,
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating PR description: {str(e)}")
            return "Error generating PR description"
    
    def create_pull_request(self, original_prompt: str) -> Optional[str]:
        """
        Create a pull request with all accepted changes.
        """
        if not self.repo:
            print("No git repository available")
            return None
            
        try:
            # Stage all changes
            self.repo.index.add(list(self.changes.keys()))
            
            # Generate PR description
            pr_description = self.generate_pr_description(original_prompt)
            
            # Create commit message
            commit_message = pr_description.split('\n')[0]  # Use first line as commit message
            
            # Commit changes
            self.repo.index.commit(commit_message)
            
            # Push changes if remote exists
            try:
                origin = self.repo.remote(name='origin')
                origin.push(self.repo.active_branch)
                return pr_description
            except ValueError:
                print("No remote repository configured. Changes are committed locally.")
                return pr_description
            
        except Exception as e:
            print(f"Error creating pull request: {str(e)}")
            return None
    
    def run_tests(self) -> bool:
        """
        Run pytest on the codebase.
        """
        try:
            result = pytest.main([self.repo_path])
            return result == 0
        except Exception as e:
            print(f"Error running tests: {str(e)}")
            return False 