#!/usr/bin/env python3
"""
ローカルテスト用スクリプト
"""

import os
import sys
sys.path.insert(0, '.')

try:
    from app import app
    print("✅ app.py import successful")
    
    # Test routes
    with app.test_client() as client:
        response = client.get('/')
        print(f"✅ / route: {response.status_code}")
        
        response = client.get('/ping')
        print(f"✅ /ping route: {response.status_code}")
        print(f"   Response: {response.get_data(as_text=True)}")
        
        response = client.get('/dashboard')
        print(f"✅ /dashboard route: {response.status_code}")
        
    print("\n🎯 All tests passed - app.py is working correctly")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()