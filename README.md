# DevDoctor 🩺

> **Deterministic developer machine & project diagnostic doctor.**  
> *Scan your machine/project → Run diagnostic checks → Identify problems → Explain WHY → Give a safe FIX → Generate reports.*

DevDoctor is a CLI-first, deterministic Python tool that inspects your development environment, detects misconfigurations, explains the root cause with evidence, and provides safe, actionable remediations. **No AI chatbot guesswork, no hallucinations—purely deterministic diagnostics.**

---

## 🚀 Quick Start

### Installation

```bash
# Install via pip
pip install devdoctor

# Or install locally in editable mode
git clone https://github.com/your-org/devdoctor.git
cd devdoctor
pip install -e .
```

### Run DevDoctor

```bash
# Scan current directory / project
devdoctor

# Or explicitly
devdoctor scan
```

---

## 📺 Example Output

```text
$ devdoctor scan

DevDoctor 0.1.1
Project: Django + PostgreSQL + Docker
────────────────────────────

✓ Python 3.12.10
✓ pip 25.0.1
✓ Git 2.55.0

❌ Virtual environment
   Current shell is not using a virtual environment.

   Active interpreter is global: C:\Program Files\Python312\python.exe

   Fix:
   Windows:
     .venv\Scripts\activate

⚠ Port 8000
   Port is already occupied.

   Process: python.exe
   PID: 18420

   Fix:
     devdoctor port free 8000

❌ Environment variable
   DATABASE_URL is required but missing.

   Found in:
     settings.py (line 24)

   Fix:
     Add DATABASE_URL to .env

Score: 72/100

3 problems found.
```

---

## 🧠 Diagnostic Structure

Every single DevDoctor diagnostic follows a strict, high-signal structure:

```text
PROBLEM
    ↓
WHY IT HAPPENED
    ↓
EVIDENCE
    ↓
SAFE FIX
    ↓
COMMAND
```

Run with `--verbose` to view the comprehensive breakdown:

```text
$ devdoctor scan --verbose

DevDoctor 0.1.1 (Detailed Diagnostic Report)
────────────────────────────────────────────────────────

PROBLEM:
Incompatible version of pydantic-core installed for Python runtime.

WHY:
Your Python version is 3.13 and requires a compatible wheel.

EVIDENCE:
pydantic-core does not have a compatible wheel for your current environment.

SAFE FIX:
Use Python 3.12 for this project.

COMMAND:
py -3.12 -m venv .venv

Confidence: HIGH
```

---

## 🛠️ The First 10 Diagnostic Checks

| # | Check | Description |
|---|---|---|
| **1** | **Python Version** | Validates active interpreter against `pyproject.toml` (`requires-python`), `.python-version`, or `runtime.txt`. |
| **2** | **pip Availability** | Validates pip installation, version, and bootstrap status. |
| **3** | **Virtual Environment** | Confirms whether shell is operating inside an active venv; provides exact platform activation command. |
| **4** | **Git Availability** | Verifies Git CLI is installed and in PATH. |
| **5** | **Git Configuration** | Checks `user.name` and `user.email`; audits `.gitignore` to ensure `.env` and sensitive files are not committed. |
| **6** | **Required Environment Variables** | Uses Python AST to detect unfulfilled `os.environ[...]` lookups without defaults. |
| **7** | **.env vs .env.example** | Diffs template keys against your `.env` to prevent runtime configuration crashes. |
| **8** | **Port Conflicts** | Scans web dev ports (8000, 3000, 5000, 5173, etc.); maps occupied ports to process name & PID. |
| **9** | **Broken Python Imports** | Scans Python code using AST and flags uninstalled third-party packages in site-packages. |
| **10** | **Dependency Conflicts** | Runs deterministic graph checks and `pip check` to detect version conflicts (e.g., `fastapi` vs `pydantic<3`). |

---

## 🔍 Project Understanding (Phase 3)

DevDoctor inspects your repository and automatically determines its stack without requiring AI:

- Detects `manage.py` → **Django**
- Detects `fastapi` in dependencies or code → **FastAPI**
- Detects `flask` in dependencies or code → **Flask**
- Detects `Dockerfile` / `docker-compose.yml` → **Docker**
- Detects PostgreSQL connection strings / psycopg → **PostgreSQL**
- Detects Redis configuration / compose service → **Redis**
- Detects `package.json` → **Node.js**

```bash
$ devdoctor project

Project Profile: my-web-app
──────────────────────────────────────────
Detected Type:      Django
Stack Summary:      Django + PostgreSQL + Redis + Docker
Technologies:       Python, Django, PostgreSQL, Redis, Docker
Frameworks:         Django
Config Files:       pyproject.toml, docker-compose.yml, .env
Dependencies:       24 declared
```

---

## ⚡ Framework-Specific Diagnostics (Phase 4)

DevDoctor includes dedicated diagnostic suites for major frameworks:

```bash
# Django diagnostics: DEBUG mode, insecure SECRET_KEY, empty ALLOWED_HOSTS, unapplied migrations
devdoctor django

# FastAPI diagnostics: Uvicorn status, default port 8000, reload flag, CORS wildcard check
devdoctor fastapi

# Docker diagnostics: daemon accessibility, exited container error codes, compose port collisions
devdoctor docker

# PostgreSQL diagnostics: port 5432 status, connection string format
devdoctor postgres

# Redis diagnostics: port 6379 status, RESP PING response test
devdoctor redis
```

---

## 🧰 The Killer Feature: `devdoctor fix` (Phase 5)

Never blindly modify a developer's machine. DevDoctor clearly separates **Safe automatic fixes** from **Action-required fixes**.

### Interactive Fix Prompt

```bash
$ devdoctor fix

Found 3 problem(s) with available fixes:

 1. [SAFE] Add .env to .gitignore
    Command: echo .env >> .gitignore
 2. [SAFE] Copy .env.example to .env
    Command: copy .env.example .env
 3. [ACTION] Kill process python.exe (PID: 18420) on port 8000
    Command: devdoctor port free 8000

Apply fixes? [Y/n]: Y

Applying fixes...

✓ Fixed: Add .env to .gitignore
✓ Fixed: Copy .env.example to .env
✓ Fixed: Kill process python.exe (PID: 18420) on port 8000

Completed: 3 applied, 0 failed.
```

### Safe-Only Automation (CI / Scripts)

Apply only safe, non-destructive fixes without touching running processes or external installations:

```bash
devdoctor fix --safe
```

### Dry Run

Preview all proposed remediations without executing anything:

```bash
devdoctor fix --dry-run
```

### Standalone Port Free Utility

Easily free up an occupied port with PID and process name resolution:

```bash
devdoctor port free 8000 --yes
```

---

## 🔌 Extensible Plugin Engine (Phase 6)

DevDoctor can be extended with custom checks via the `@check` decorator or Python entry points (`devdoctor.checks`).

### Writing a Custom Check

Create a Python file in your project under `.devdoctor/checks/my_check.py` or inside an installable package:

```python
from devdoctor import check, Diagnostic, ScanContext, Severity

@check(name="internal_api", title="Internal API Gateway", category="network")
def check_internal_api(context: ScanContext) -> Diagnostic | None:
    api_url = context.env_vars.get("INTERNAL_API_URL")
    if not api_url:
        return Diagnostic(
            title="Internal API Gateway",
            severity=Severity.ERROR,
            message="INTERNAL_API_URL is missing in environment.",
            why="Microservices require INTERNAL_API_URL to reach the auth cluster.",
            fix="Add INTERNAL_API_URL=https://api.internal to .env",
            command="echo INTERNAL_API_URL=https://api.internal >> .env",
        )
    return Diagnostic(
        title="Internal API Gateway",
        severity=Severity.OK,
        message=f"Configured: {api_url}",
    )
```

DevDoctor will automatically discover and execute your custom check!

---

## 🐍 Python API

Integrate DevDoctor diagnostics directly into your Python scripts, pytest test suites, or tooling:

```python
from devdoctor import DevDoctor

doctor = DevDoctor(project_path=".")

# Run scan
report = doctor.scan()

print(f"Health Score: {report.score}/100")
print(f"Total Problems: {report.total_problems}")

for problem in report.problems:
    print(f"[{problem.severity.value}] {problem.title}: {problem.message}")

# Apply safe fixes automatically
if not report.is_healthy:
    doctor.fix(safe_only=True)
```

---

## 🤖 CI/CD Integration & Reporting

Export machine-readable JSON or GitHub-flavored Markdown for CI/CD checks:

```bash
# Output JSON for pipeline evaluation
devdoctor scan --json

# Fail build if errors or warnings exist
devdoctor scan --strict

# Export Markdown report for PR comment
devdoctor report --format markdown -o report.md
```

---

## 📋 CLI Reference

```text
devdoctor [scan] [PATH]           Scan machine and project (default command)
  --json                          Output report in JSON format
  --markdown                      Output report in Markdown format
  -v, --verbose                   Show detailed WHY/EVIDENCE/FIX/COMMAND breakdown
  -o, --output FILE               Save report to file
  --strict                        Exit with code 1 on warnings or errors
  --checks-dir DIR                Load custom check plugins from directory

devdoctor fix [PATH]              Apply fixes for identified issues
  --safe                          Apply only safe non-destructive fixes
  --dry-run                       Show planned fixes without applying changes
  -y, --yes                       Confirm all fixes non-interactively

devdoctor dependencies [PATH]     Check dependency conflicts and broken imports
devdoctor port free <PORT> [-y]   Kill process listening on specified port
devdoctor project [PATH]          Inspect detected project profile and tech stack
devdoctor report [PATH]           Export diagnostic report (terminal/markdown/json)
devdoctor django [PATH]           Run Django-specific diagnostics
devdoctor fastapi [PATH]          Run FastAPI-specific diagnostics
devdoctor docker [PATH]           Run Docker-specific diagnostics
devdoctor postgres [PATH]         Run PostgreSQL-specific diagnostics
devdoctor redis [PATH]            Run Redis-specific diagnostics
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
