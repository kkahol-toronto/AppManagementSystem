# NTTAMSGenie

NTTAMSGenie is a full-stack web application that leverages AI to generate code, automate pull request (PR) creation, and streamline code review workflows. It integrates with Azure OpenAI for code and PR description generation, and with GitHub for repository and PR management.

---

## Features

- **AI-Powered Code Generation:** Generate code and implementation plans from natural language requests using Azure OpenAI.
- **Automated PR Creation:** Create branches, commit code, push to GitHub, and open draft PRs with AI-generated descriptions.
- **In-Browser Code Studio:** Edit generated code in a web-based editor (NTT Studio) before submitting PRs.
- **PR Review Tab:** Edit PR title and description before final submission.
- **Multi-File Support:** Handles multiple code files and requirements updates.
- **Integrated with GitHub:** All PRs are created and updated directly on your GitHub repository.

---

## Project Structure

```
.
├── backend/                # Backend FastAPI app and logic
│   ├── main.py             # Main FastAPI app (API endpoints)
│   ├── code_change_handler.py
│   ├── requirements.txt    # Backend dependencies
│   └── ...                 # Other backend files
├── frontend/               # React frontend app
│   ├── src/                # React source code
│   ├── public/             # Static files and injected scripts
│   ├── package.json        # Frontend dependencies
│   └── ...                 # Other frontend files
├── data/                   # Cloned GitHub repos and generated code
├── apm_env/                # Python virtual environment (ignored)
├── .gitignore
├── main.py                 # (root) Entrypoint for backend (if used)
└── ...
```

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- GitHub account and a personal access token (with repo permissions)
- Azure OpenAI access and API key

---

## Backend Setup

1. **Create and activate a Python virtual environment:**
   ```bash
   python3 -m venv apm_env
   source apm_env/bin/activate
   ```

2. **Install backend dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Set environment variables:**
   Create a `.env` file in the project root or export these in your shell:
   ```
   GITHUB_TOKEN=your_github_token
   GITHUB_ORG=your_github_org   # (optional, if using an org repo)
   OPENAI_ENDPOINT=your_azure_openai_endpoint
   OPENAI_KEY=your_azure_openai_key
   OPENAI_MODEL=gpt-4.1
   OPENAI_API_VERSION=2024-12-01-preview
   ```

4. **Start the backend server:**
   ```bash
   uvicorn main:app --reload
   ```
   The API will be available at `http://localhost:8000`.

---

## Frontend Setup

1. **Install frontend dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Start the frontend development server:**
   ```bash
   npm start
   ```
   The app will be available at `http://localhost:3000`.

---

## Usage Workflow

1. **Submit a Request:**  
   On the main Genie page, enter your code request and GitHub repo link.

2. **AI Code Generation:**  
   Genie generates code files and a plan. You can move these files to NTT Studio for further editing.

3. **Edit in NTT Studio (Optional):**  
   Use the in-browser code editor to review and modify generated files.

4. **Create a Pull Request:**  
   - Click "Create Pull Request" (on main page or in NTT Studio).
   - Genie creates a new branch, saves files, commits, pushes, and generates a PR description using OpenAI.
   - A review tab opens for you to edit the PR title/description.
   - Submit the PR as a draft to GitHub.

5. **Update PR (Optional):**  
   Edit the PR title/description in the review tab and submit updates directly to GitHub.

---

## Key API Endpoints

- `POST /chat`  
  Generate code and plan from a user request and GitHub link.

- `POST /studio/pr`  
  Create a new branch, save files, commit, push, and open a draft PR with an AI-generated description.

- `POST /studio/pr/update`  
  Update the title and description of an existing PR.

- `POST /execute`  
  Run code in the context of the cloned repo.

- `POST /install_requirements`  
  Install Python requirements in the repo.

---

## Customization & Extensibility

- **Prompts:**  
  Edit `prompts.py` to customize the AI's behavior for code and PR generation.

- **NTT Studio Integration:**  
  The `frontend/public/ntt_studio_pr.js` script injects PR creation into the in-browser editor.

- **Data Storage:**  
  All cloned repos and generated files are stored in the `data/` directory.

---

## Development Notes

- The backend uses FastAPI and PyGithub for GitHub integration.
- The frontend is built with React and Material UI.
- All environment variables can be managed via `.env`.
- The project is designed for local development and demo purposes.

---

## License

MIT License (or specify your license here)

---

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://react.dev/)
- [Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
- [PyGithub](https://pygithub.readthedocs.io/) 