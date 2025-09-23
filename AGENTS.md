# AGENTS.md

## 1) Purpose of this document

This document defines **strict rules and security practices** for AI agents (Cursor / Claude-code / Composer / chat inserts) when working on corporate devices and within corporate repositories. The goal is to minimize risks of data leaks, unwanted infrastructure changes, compliance violations, and unstable builds.

This document is **mandatory** for all developers using agents in Cursor, as well as for the agents themselves via system prompts.

---

## 2) Definition of "agent" (in the context of Cursor)

An agent is any automated assistant/script in Cursor that can:
- generate/edit code;  
- execute commands in terminal/Tasks;  
- modify project files;  
- propose dependency installation steps.

---

## 3) Core security principles

1. **Least Privilege.** Do only what is necessary for the specific task, within the current project.  
2. **Explicit Permission.** Actions outside the allowed list are **forbidden** without explicit developer/repo owner approval.  
3. **Reproducibility.** All changes and builds must be reproducible locally and in CI without `sudo` and without system modifications.  
4. **Auditability.** All changes are tracked in Git; configuration edits must include justification in PRs.  
5. **Controlled Network Access.** Network access allowed only to approved corporate sources.

---

## 4) Hard rules (must follow)

**Extended and enforced restrictions for agents:**

1. **Do only what you are asked.**  
   - Do not initiate "improvements", migrations, or refactoring without explicit request.  
   - Do not go beyond the current task, branch, or project directory.  
   - Any assumptions must be proposals, **never auto-applied**.

2. **DO NOT create or update `.md` files.**  
   - Prohibited to create/modify `README.md`, `AGENTS.md`, `SECURITY.md`, or any Markdown files.  
   - **Exception:** this file is maintained **only by humans** via code review; agents must not touch Markdown.

3. **Use ONLY Python virtual environments (`venv`).**  
   - **Forbidden:** modifying/updating global Python installation, using `sudo`, editing system paths, installing global packages.  
   - Each project must have its own isolated `.venv` in the repo root (or per team policy).  
   - Updating `pip` or packages is allowed **only inside the activated `venv`**.

4. **Network safety.**  
   - Access allowed **only** to corporate mirrors/repositories (PyPI mirror, Artifactory, private Git servers) and allow-listed domains.  
   - Access to public registries is **forbidden** without explicit approval.

5. **Do not touch the system.**  
   - Forbidden: installing daemons/services, editing `/etc/*`, system environment variables, shell profiles, configs outside the project.

6. **Secrets and personal data are off-limits.**  
   - Do not read `~/.ssh`, system keys, tokens, or files outside the project.  
   - Do not log/copy secrets, `.env`, keychain, credentials.

7. **Git discipline.**  
   - All changes go in a separate branch via Pull Request, no `--force`, no pushes to protected branches.  
   - Auto-generated commits allowed **only** within the current task and project.

---

## 5) Allowed actions (whitelist)

Agents are **allowed** (within the current task and project):
- Create/modify **source code**, tests, configs **except** `.md`.  
- Create Python dependency files: `requirements.in`, `requirements.txt`, `constraints.txt`, `pyproject.toml` (if per team policy) — **only in active `venv`** and via corporate sources.  
- Modify local project configs (`.editorconfig`, `.gitignore`, `ruff.toml`, `mypy.ini`) — if explicitly requested.  
- Generate DB migrations **only** for local development; do not apply to remote environments.  
- Run local formatting/linting/testing commands that do not require `sudo`.

---

## 6) Forbidden actions (blacklist)

- Any modifications outside the project directory.  
- Any modifications to `.md` files (including this one).  
- Any commands with `sudo` or requiring admin rights.  
- Global installations/updates of Python/Node/Java/system libs.  
- Access to external package registries without approval.  
- Automatic handling of secrets, reading keys, dumping environment variables.  
- Background daemons/long-lived processes, network scans, unauthorized telemetry.  
- Rewriting Git history on protected branches (`rebase -i`, `push --force`).  
- Auto-creating CI/CD pipelines or editing IaC without request.

---

## 7) Python: strictly `venv`

**Creating an environment:**
```bash
# in project root
python3 -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scriptsctivate

# upgrade pip ONLY inside venv
python -m pip install --upgrade pip
```

**Rules:**
- New dependencies go in `requirements.in` → compiled into `requirements.txt` with pins (e.g. via `pip-tools` **inside venv**).  
- No global installs. No system Python modifications.  
- For different Python versions, use approved corporate methods (preinstalled versions, container, CI).

---

## 8) Dependency management

- Packages only from **approved corporate sources**.  
- Strict version pinning is mandatory.  
- New dependencies must include a short justification in PR (why, alternatives, impact).  
- Removing unused/drifting dependencies is encouraged on request.

---

## 9) Network and data

- Outbound traffic only to allow-listed domains (corp Git, Artifactory, PyPI mirror, etc.).  
- Forbidden to send code/data to unapproved external services.  
- Sensitive data: only synthetic/anonymized datasets may be used.

---

## 10) Git process

- Work **in a new branch** from up-to-date `main`/`develop`.  
- Commits must be atomic, with meaningful messages (what/why).  
- PR must describe changes and link to the task.  
- Checks: lint, tests, security — before merging.

---

## 11) Secrets

- Do not read `~/.ssh`, `~/.aws`, `~/.kube`, system Keychains, etc.  
- Do not print secrets to logs/console.  
- `.env` and similar files must be `.gitignore`d; do not open/copy them.

---

## 12) Logging and traces

- Agent logs must be informative but contain **no PII/secrets**.  
- Must record: what was changed, what commands were run, what files affected.  
- Logs stored locally within the project (e.g. `./.cursor/logs/`) and cleaned periodically.

---

## 13) Checklist before running an agent (developer hand-off)

1. Task clearly formulated (one goal, explicit constraints).  
2. Confirmed project directory; no work outside.  
3. `.venv` created and activated; corporate index configured.  
4. Network access limited to allow-list.  
5. `.md` files protected from modification.  
6. Secrets inaccessible (no reads outside project tree).  
7. Dependency plan (if needed) approved.  
8. Git branch prepared.

---

## 14) Document maintenance

- This `AGENTS.md` can be changed **only manually by humans** via PR and code review.  
- Policy changes must be approved by security/compliance.  
- Agents are **strictly forbidden** to edit this or any `.md`.