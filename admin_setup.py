#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理者アカウント作成用APIエンドポイント
一時的に追加して、管理者作成後に削除します
"""
from flask import jsonify
from app import app, supabase
import hashlib
import secrets
from datetime import datetime
import uuid

@app.route('/setup/create-admin-temp-endpoint-20250723', methods=['POST'])
def create_admin_temporary():
    """一時的な管理者作成エンドポイント"""
    try:
        email = "ooxmichaelxoo@gmail.com"
        password = "akutu4256"
        
        # Generate salt and hash
        salt = secrets.token_hex(32)
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
        
        # Check if user exists
        existing = supabase.table('users').select('*').eq('email', email).execute()
        
        if existing.data:
            # Update existing user
            user_id = existing.data[0]['id']
            result = supabase.table('users')\
                .update({
                    'password_hash': password_hash,
                    'salt': salt,
                    'role': 'admin',
                    'permissions': ['read', 'write', 'delete', 'admin'],
                    'is_active': True,
                    'updated_at': datetime.utcnow().isoformat()
                })\
                .eq('email', email)\
                .execute()
        else:
            # Create new user
            user_id = str(uuid.uuid4())
            user_data = {
                'id': user_id,
                'email': email,
                'username': 'ooxmichaelxoo',
                'password_hash': password_hash,
                'salt': salt,
                'role': 'admin',
                'permissions': ['read', 'write', 'delete', 'admin'],
                'is_active': True,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            result = supabase.table('users').insert(user_data).execute()
        
        # Create API key
        api_key = f"sk-admin-{secrets.token_urlsafe(32)}"
        api_key_data = {
            'user_id': user_id,
            'key': api_key,
            'name': 'Admin API Key',
            'permissions': ['read', 'write', 'delete', 'admin'],
            'is_active': True,
            'created_at': datetime.utcnow().isoformat()
        }
        
        api_result = supabase.table('api_keys').insert(api_key_data).execute()
        
        return jsonify({
            'success': True,
            'message': 'Admin account created',
            'email': email,
            'api_key': api_key,
            'note': 'Save the API key securely. Delete this endpoint after use.'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Temporary admin setup endpoint added")
    print("Access: POST /setup/create-admin-temp-endpoint-20250723")
    print("Remember to remove this endpoint after creating the admin!")