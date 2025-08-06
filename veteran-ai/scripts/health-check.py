#!/usr/bin/env python3
"""
ベテランAI システムヘルスチェック
"""
import os
import sys
import asyncio
import importlib.util
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
backend_path = project_root / "backend"
sys.path.insert(0, str(backend_path))

async def check_imports():
    """重要なモジュールのインポートチェック"""
    print("📦 モジュールインポートチェック...")
    
    try:
        # 設定
        from core.config import settings
        print("  ✅ 設定モジュール")
        
        # データベース
        from database.connection import supabase
        print("  ✅ データベース接続")
        
        # サービス
        from services.embedding_service import embedding_service
        from services.rag_engine import rag_engine
        print("  ✅ AI サービス")
        
        # API ルーター
        from routers import chat, search, upload, integrations
        print("  ✅ API ルーター")
        
        # 統合
        from integrations.slack_client import slack_client
        print("  ✅ チャット統合")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ インポートエラー: {e}")
        return False
    except Exception as e:
        print(f"  ❌ 予期しないエラー: {e}")
        return False

async def check_environment():
    """環境変数チェック"""
    print("\n⚙️  環境変数チェック...")
    
    required_vars = [
        "SUPABASE_URL",
        "SUPABASE_KEY", 
        "OPENAI_API_KEY"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
            print(f"  ❌ {var} が設定されていません")
        else:
            print(f"  ✅ {var}")
    
    return len(missing_vars) == 0

async def check_dependencies():
    """依存関係チェック"""
    print("\n📋 依存関係チェック...")
    
    required_packages = [
        "fastapi",
        "uvicorn", 
        "supabase",
        "openai",
        "anthropic",
        "numpy",
        "pytesseract",
        "whisper"
    ]
    
    missing_packages = []
    for package in required_packages:
        spec = importlib.util.find_spec(package)
        if spec is None:
            missing_packages.append(package)
            print(f"  ❌ {package} がインストールされていません")
        else:
            print(f"  ✅ {package}")
    
    return len(missing_packages) == 0

async def check_files():
    """重要ファイルの存在チェック"""
    print("\n📄 ファイル存在チェック...")
    
    required_files = [
        "backend/main.py",
        "backend/core/config.py",
        "backend/database/schema.sql",
        "backend/database/functions.sql",
        "frontend/package.json",
        "requirements.txt",
        ".env.example"
    ]
    
    missing_files = []
    for file_path in required_files:
        full_path = project_root / file_path
        if not full_path.exists():
            missing_files.append(file_path)
            print(f"  ❌ {file_path} が見つかりません")
        else:
            print(f"  ✅ {file_path}")
    
    return len(missing_files) == 0

async def main():
    """メインヘルスチェック"""
    print("🏥 ベテランAI システムヘルスチェック開始\n")
    
    checks = [
        ("ファイル", check_files()),
        ("環境変数", check_environment()),
        ("依存関係", check_dependencies()),
        ("モジュール", check_imports())
    ]
    
    results = []
    for name, check in checks:
        try:
            result = await check
            results.append((name, result))
        except Exception as e:
            print(f"  ❌ {name}チェック中にエラー: {e}")
            results.append((name, False))
    
    print("\n" + "="*50)
    print("📊 チェック結果サマリー")
    print("="*50)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("🎉 すべてのチェックが成功しました！")
        print("システムは正常に動作する準備ができています。")
    else:
        print("⚠️  一部のチェックが失敗しました。")
        print("上記のエラーを修正してから再度実行してください。")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    # .envファイルを読み込み
    env_file = project_root / ".env"
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)