# PowerShell Git Setup Script for Dify Chat System

Write-Host "=== Dify Chat System Git Setup ===" -ForegroundColor Green
Write-Host ""

# Check if Git is installed
try {
    $gitVersion = git --version
    Write-Host "Git version: $gitVersion" -ForegroundColor Cyan
} catch {
    Write-Host "Error: Git is not installed" -ForegroundColor Red
    Write-Host "Please install Git from: https://git-scm.com/download/win"
    exit 1
}

Write-Host ""
Write-Host "Current directory: $PWD" -ForegroundColor Yellow
Write-Host ""

# Initialize Git repository
Write-Host "Initializing Git repository..." -ForegroundColor Yellow
git init
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Git repository initialized" -ForegroundColor Green
} else {
    Write-Host "✗ Failed to initialize Git repository" -ForegroundColor Red
}

# Switch to main branch
Write-Host "Switching to main branch..." -ForegroundColor Yellow
git branch -m main
Write-Host "✓ Switched to main branch" -ForegroundColor Green

# Add remote repository
Write-Host "Adding GitHub remote repository..." -ForegroundColor Yellow
git remote remove origin 2>$null
git remote add origin https://github.com/IKEMENLTD/dify-chat-system.git
Write-Host "✓ Remote repository added" -ForegroundColor Green

# Create .gitignore if it doesn't exist
if (!(Test-Path .gitignore)) {
    Write-Host "Creating .gitignore file..." -ForegroundColor Yellow
    @"
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
dify_chat_env/
.venv/

# Environment variables
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Database
*.db
*.sqlite
*.sqlite3

# Sensitive files
secrets/
private/
*.pem
*.key

# Temporary files
tmp/
temp/
*.tmp
*.temp

# Build files
dist/
build/
*.egg-info/

# Testing
.coverage
.pytest_cache/
htmlcov/

# Security warning (contains API keys)
SECURITY_WARNING.md
"@ | Out-File -FilePath .gitignore -Encoding UTF8
    Write-Host "✓ .gitignore created" -ForegroundColor Green
} else {
    Write-Host "✓ .gitignore already exists" -ForegroundColor Green
}

Write-Host ""
Write-Host "Staging files..." -ForegroundColor Yellow
git add .
Write-Host "✓ Files staged" -ForegroundColor Green

Write-Host ""
Write-Host "=== Current Git Status ===" -ForegroundColor Cyan
git status

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Create initial commit:" -ForegroundColor White
Write-Host "   git commit -m `"Initial commit: Dify Chat System v5.00`"" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Fetch remote repository status:" -ForegroundColor White
Write-Host "   git fetch origin" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Push to GitHub:" -ForegroundColor White
Write-Host "   Option A - New repository:" -ForegroundColor White
Write-Host "   git push -u origin main" -ForegroundColor Gray
Write-Host ""
Write-Host "   Option B - Force push (overwrites existing):" -ForegroundColor White
Write-Host "   git push -f origin main" -ForegroundColor Gray
Write-Host ""
Write-Host "   Option C - Merge with existing:" -ForegroundColor White
Write-Host "   git pull origin main --allow-unrelated-histories" -ForegroundColor Gray
Write-Host "   (resolve conflicts if any)" -ForegroundColor Gray
Write-Host "   git push origin main" -ForegroundColor Gray
Write-Host ""
Write-Host "Note: SECURITY_WARNING.md is excluded in .gitignore" -ForegroundColor Red
Write-Host "      Please manage API keys through environment variables" -ForegroundColor Red