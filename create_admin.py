#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理者アカウント作成スクリプト
"""
import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv
import hashlib
import secrets
from datetime import datetime
import uuid

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')

if not supabase_url or not supabase_key:
    print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env file")
    sys.exit(1)

supabase: Client = create_client(supabase_url, supabase_key)

def hash_password(password: str, salt: str = None) -> tuple:
    """Hash password with salt"""
    if not salt:
        salt = secrets.token_hex(32)
    
    # Create hash with salt
    password_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000  # iterations
    )
    
    return password_hash.hex(), salt

def create_admin_user(email: str, password: str, username: str = None):
    """Create admin user account"""
    try:
        # Generate password hash
        password_hash, salt = hash_password(password)
        
        # Create user record
        user_data = {
            'id': str(uuid.uuid4()),
            'email': email,
            'username': username or email.split('@')[0],
            'password_hash': password_hash,
            'salt': salt,
            'role': 'admin',
            'permissions': ['read', 'write', 'delete', 'admin'],
            'is_active': True,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        # Check if user already exists
        existing = supabase.table('users').select('*').eq('email', email).execute()
        
        if existing.data:
            print(f"User with email {email} already exists. Updating to admin...")
            # Update existing user to admin
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
            # Insert new user
            result = supabase.table('users').insert(user_data).execute()
        
        if result.data:
            print(f"✅ Admin account created successfully!")
            print(f"Email: {email}")
            print(f"Password: {password}")
            print(f"Role: admin")
            print(f"Permissions: read, write, delete, admin")
            
            # Create API key for the user
            api_key = f"sk-{secrets.token_urlsafe(32)}"
            api_key_data = {
                'user_id': result.data[0]['id'] if not existing.data else existing.data[0]['id'],
                'key': api_key,
                'name': 'Admin API Key',
                'permissions': ['read', 'write', 'delete', 'admin'],
                'is_active': True,
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Create API key
            api_result = supabase.table('api_keys').insert(api_key_data).execute()
            
            if api_result.data:
                print(f"\n🔑 API Key generated: {api_key}")
                print("\nSave this API key securely. It won't be shown again.")
            
            return True
        else:
            print("❌ Failed to create admin account")
            return False
            
    except Exception as e:
        print(f"❌ Error creating admin account: {str(e)}")
        return False

if __name__ == "__main__":
    # Create admin account
    email = "ooxmichaelxoo@gmail.com"
    password = "akutu4256"
    
    print(f"Creating admin account for {email}...")
    create_admin_user(email, password)