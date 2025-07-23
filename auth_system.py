# -*- coding: utf-8 -*-
"""
完璧な認証システム実装
マルチプラットフォーム対応（Web, LINE, API）
"""

import jwt
import time
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, g
from supabase import create_client
import os

# Supabase Auth統合クライアント
class AuthManager:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.jwt_secret = os.getenv('JWT_SECRET_KEY', secrets.token_hex(32))
        self.jwt_algorithm = 'HS256'
        
    def create_jwt_token(self, user_id, user_data=None, expires_hours=24):
        """JWTトークン生成"""
        payload = {
            'user_id': user_id,
            'iat': int(time.time()),
            'exp': int(time.time()) + (expires_hours * 3600),
            'jti': str(uuid.uuid4()),  # Token ID for revocation
            'type': 'access'
        }
        
        if user_data:
            payload.update({
                'email': user_data.get('email'),
                'role': user_data.get('role', 'user'),
                'line_id': user_data.get('line_id'),
                'permissions': user_data.get('permissions', [])
            })
            
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def verify_jwt_token(self, token):
        """JWTトークン検証"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            # Token revocation check (Redis推奨)
            if self.is_token_revoked(payload.get('jti')):
                return None
                
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def authenticate_user(self, email, password):
        """メール/パスワード認証"""
        try:
            # Supabase Auth使用
            auth_response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if auth_response.user:
                user_data = {
                    'email': auth_response.user.email,
                    'role': self.get_user_role(auth_response.user.id),
                    'permissions': self.get_user_permissions(auth_response.user.id)
                }
                
                token = self.create_jwt_token(auth_response.user.id, user_data)
                return {
                    'success': True,
                    'token': token,
                    'user': user_data,
                    'refresh_token': auth_response.session.refresh_token
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def authenticate_line_user(self, line_user_id, line_profile=None):
        """LINE認証統合"""
        try:
            # LINE IDから既存ユーザー検索
            existing_user = self.supabase.table('users')\
                .select('*')\
                .eq('line_id', line_user_id)\
                .single()\
                .execute()
            
            if existing_user.data:
                user_data = existing_user.data
            else:
                # 新規LINE ユーザー作成
                user_data = {
                    'line_id': line_user_id,
                    'display_name': line_profile.get('displayName') if line_profile else f'LINE_{line_user_id[:8]}',
                    'role': 'user',
                    'created_at': datetime.utcnow().isoformat(),
                    'auth_provider': 'line'
                }
                
                new_user = self.supabase.table('users').insert(user_data).execute()
                user_data = new_user.data[0]
            
            # JWT生成
            token = self.create_jwt_token(user_data['id'], {
                'line_id': line_user_id,
                'role': user_data.get('role', 'user'),
                'permissions': self.get_user_permissions(user_data['id'])
            })
            
            return {
                'success': True,
                'token': token,
                'user': user_data
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def create_api_key(self, user_id, name, permissions=None):
        """開発者向けAPI Key生成"""
        api_key = f"vai_{secrets.token_urlsafe(32)}"
        
        api_data = {
            'user_id': user_id,
            'api_key_hash': hashlib.sha256(api_key.encode()).hexdigest(),
            'name': name,
            'permissions': permissions or ['read'],
            'created_at': datetime.utcnow().isoformat(),
            'is_active': True
        }
        
        self.supabase.table('api_keys').insert(api_data).execute()
        return api_key
    
    def verify_api_key(self, api_key):
        """API Key認証"""
        try:
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            
            result = self.supabase.table('api_keys')\
                .select('*, users(*)')\
                .eq('api_key_hash', key_hash)\
                .eq('is_active', True)\
                .single()\
                .execute()
            
            if result.data:
                return {
                    'success': True,
                    'user_id': result.data['user_id'],
                    'permissions': result.data['permissions'],
                    'user': result.data['users']
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_user_role(self, user_id):
        """ユーザーロール取得"""
        try:
            result = self.supabase.table('users')\
                .select('role')\
                .eq('id', user_id)\
                .single()\
                .execute()
            return result.data.get('role', 'user')
        except:
            return 'user'
    
    def get_user_permissions(self, user_id):
        """ユーザー権限取得"""
        role = self.get_user_role(user_id)
        
        permission_map = {
            'admin': ['read', 'write', 'delete', 'manage_users', 'manage_system'],
            'moderator': ['read', 'write', 'delete'],
            'user': ['read', 'write'],
            'readonly': ['read']
        }
        
        return permission_map.get(role, ['read'])
    
    def is_token_revoked(self, jti):
        """トークン無効化チェック（Redis推奨）"""
        # TODO: Redis実装
        return False
    
    def revoke_token(self, jti):
        """トークン無効化"""
        # TODO: Redis実装
        pass

# 認証デコレーター
def require_auth(permissions=None):
    """認証必須デコレーター"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            api_key = request.headers.get('X-API-Key')
            
            if api_key:
                # API Key認証
                auth_result = g.auth_manager.verify_api_key(api_key)
                if not auth_result['success']:
                    return jsonify({'error': 'Invalid API key'}), 401
                
                g.current_user = auth_result['user']
                g.user_permissions = auth_result['permissions']
                
            elif auth_header and auth_header.startswith('Bearer '):
                # JWT認証
                token = auth_header.split(' ')[1]
                payload = g.auth_manager.verify_jwt_token(token)
                
                if not payload:
                    return jsonify({'error': 'Invalid or expired token'}), 401
                
                g.current_user_id = payload['user_id']
                g.user_permissions = payload.get('permissions', ['read'])
                
            else:
                return jsonify({'error': 'Authentication required'}), 401
            
            # 権限チェック
            if permissions:
                user_perms = set(g.user_permissions)
                required_perms = set(permissions) if isinstance(permissions, list) else {permissions}
                
                if not required_perms.issubset(user_perms):
                    return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_line_auth(f):
    """LINE専用認証デコレーター"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # LINE署名検証は既存のverify_line_signature使用
        if not verify_line_signature(request):
            return jsonify({'error': 'Invalid LINE signature'}), 401
        
        return f(*args, **kwargs)
    return decorated_function