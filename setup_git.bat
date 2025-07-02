@echo off
echo === Dify Chat System Git Setup ===
echo.

:: Check if Git is installed
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Git is not installed
    echo Please install Git from: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo Git is installed
echo.

:: Initialize Git repository
echo Initializing Git repository...
git init
if %errorlevel% equ 0 (
    echo Git repository initialized successfully
) else (
    echo Warning: Git repository might already be initialized
)
echo.

:: Switch to main branch
echo Switching to main branch...
git branch -m main 2>nul || git checkout -b main
echo.

:: Remove existing origin if exists
git remote remove origin 2>nul

:: Add remote repository
echo Adding GitHub remote repository...
git remote add origin https://github.com/IKEMENLTD/dify-chat-system.git
echo Remote repository added
echo.

:: Create .gitignore
echo Creating .gitignore file...
(
echo # Python
echo __pycache__/
echo *.py[cod]
echo *$py.class
echo *.so
echo .Python
echo env/
echo venv/
echo ENV/
echo dify_chat_env/
echo .venv/
echo.
echo # Environment variables
echo .env
echo .env.local
echo .env.*.local
echo.
echo # IDE
echo .vscode/
echo .idea/
echo *.swp
echo *.swo
echo *~
echo.
echo # OS
echo .DS_Store
echo Thumbs.db
echo.
echo # Logs
echo *.log
echo logs/
echo.
echo # Database
echo *.db
echo *.sqlite
echo *.sqlite3
echo.
echo # Sensitive files
echo secrets/
echo private/
echo *.pem
echo *.key
echo.
echo # Temporary files
echo tmp/
echo temp/
echo *.tmp
echo *.temp
echo.
echo # Build files
echo dist/
echo build/
echo *.egg-info/
echo.
echo # Testing
echo .coverage
echo .pytest_cache/
echo htmlcov/
echo.
echo # Security warning
echo SECURITY_WARNING.md
) > .gitignore

echo .gitignore created
echo.

:: Stage all files
echo Staging files...
git add .
echo Files staged
echo.

:: Show status
echo === Current Git Status ===
git status
echo.

echo === Setup Complete ===
echo.
echo Next steps:
echo 1. Create initial commit:
echo    git commit -m "Initial commit: Dify Chat System v5.00"
echo.
echo 2. Fetch remote repository:
echo    git fetch origin
echo.
echo 3. Push to GitHub:
echo    Option A - New repository:
echo    git push -u origin main
echo.
echo    Option B - Force push (overwrites existing):
echo    git push -f origin main
echo.
echo    Option C - Merge with existing:
echo    git pull origin main --allow-unrelated-histories
echo    (resolve conflicts if any)
echo    git push origin main
echo.
echo Note: SECURITY_WARNING.md is excluded in .gitignore
echo       Please manage API keys through environment variables
echo.
pause