@echo off
echo === Git Repository Status ===
echo.

echo Current branch:
git branch --show-current
echo.

echo Remote repository:
git remote -v
echo.

echo Current status:
git status
echo.

echo === Ready to commit and push ===
echo.
echo Next commands to run:
echo.
echo 1. Create initial commit:
echo    git commit -m "Initial commit: Dify Chat System v5.00 with LINE history and reminder features"
echo.
echo 2. Push to GitHub:
echo    git push -u origin main
echo.
echo If push is rejected, try:
echo    git pull origin main --allow-unrelated-histories
echo    (resolve any conflicts)
echo    git push origin main
echo.
pause