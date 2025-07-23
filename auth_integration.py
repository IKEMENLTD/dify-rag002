# -*- coding: utf-8 -*-
"""
既存app.pyへの認証統合パッチ
"""

from auth_system import AuthManager, require_auth, require_line_auth
from flask import g, request, jsonify

# アプリ初期化時に追加
def initialize_auth(app, supabase_client):
    """認証システム初期化"""
    
    @app.before_request
    def load_auth_manager():
        g.auth_manager = AuthManager(supabase_client)
    
    # 認証エンドポイント追加
    @app.route('/api/auth/login', methods=['POST'])
    def login():
        """Web認証エンドポイント"""
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        result = g.auth_manager.authenticate_user(email, password)
        
        if result['success']:
            return jsonify({
                'token': result['token'],
                'user': result['user'],
                'refresh_token': result['refresh_token']
            })
        else:
            return jsonify({'error': result['error']}), 401
    
    @app.route('/api/auth/register', methods=['POST'])
    def register():
        """新規ユーザー登録"""
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        try:
            # Supabase Auth登録
            auth_response = g.auth_manager.supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            
            if auth_response.user:
                # ユーザーデータをusersテーブルに保存
                user_data = {
                    'id': auth_response.user.id,
                    'email': email,
                    'role': 'user',
                    'created_at': datetime.utcnow().isoformat(),
                    'auth_provider': 'email'
                }
                
                g.auth_manager.supabase.table('users').insert(user_data).execute()
                
                return jsonify({
                    'message': 'Registration successful. Please check your email for verification.',
                    'user_id': auth_response.user.id
                })
            else:
                return jsonify({'error': 'Registration failed'}), 400
                
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
    @app.route('/api/auth/refresh', methods=['POST'])
    def refresh_token():
        """トークン更新"""
        data = request.get_json()
        refresh_token = data.get('refresh_token')
        
        if not refresh_token:
            return jsonify({'error': 'Refresh token required'}), 400
        
        try:
            session = g.auth_manager.supabase.auth.refresh_session(refresh_token)
            
            if session.user:
                user_data = {
                    'email': session.user.email,
                    'role': g.auth_manager.get_user_role(session.user.id)
                }
                
                new_token = g.auth_manager.create_jwt_token(session.user.id, user_data)
                
                return jsonify({
                    'token': new_token,
                    'refresh_token': session.refresh_token
                })
        except Exception as e:
            return jsonify({'error': str(e)}), 401
    
    @app.route('/api/auth/profile', methods=['GET'])
    @require_auth()
    def get_profile():
        """ユーザープロファイル取得"""
        try:
            user_data = g.auth_manager.supabase.table('users')\
                .select('id, email, display_name, role, created_at, line_id')\
                .eq('id', g.current_user_id)\
                .single()\
                .execute()
            
            return jsonify({
                'user': user_data.data,
                'permissions': g.user_permissions
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/auth/api-keys', methods=['POST'])
    @require_auth(['write'])
    def create_api_key():
        """API Key生成"""
        data = request.get_json()
        name = data.get('name', 'Default API Key')
        permissions = data.get('permissions', ['read'])
        
        api_key = g.auth_manager.create_api_key(g.current_user_id, name, permissions)
        
        return jsonify({
            'api_key': api_key,
            'name': name,
            'permissions': permissions,
            'note': 'このキーは再表示されません。安全に保管してください。'
        })
    
    @app.route('/api/auth/logout', methods=['POST'])
    @require_auth()
    def logout():
        """ログアウト（トークン無効化）"""
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            payload = g.auth_manager.verify_jwt_token(token)
            if payload:
                g.auth_manager.revoke_token(payload.get('jti'))
        
        return jsonify({'message': 'Logged out successfully'})

# 既存エンドポイントの更新例
def secure_existing_endpoints():
    """既存エンドポイントのセキュリティ強化パッチ"""
    
    # app.pyの各エンドポイントを以下のように修正：
    
    # @app.route('/api/chat', methods=['POST'])
    # @require_auth(['write'])  # 追加
    # def api_chat():
    #     # user_id = g.current_user_id  # 信頼できるuser_id使用
    
    # @app.route('/api/reminder', methods=['POST'])
    # @require_auth(['write'])  # 追加
    # def create_reminder():
    #     # user_id = g.current_user_id  # 信頼できるuser_id使用
    
    # @app.route('/api/reminders', methods=['GET'])
    # @require_auth(['read'])  # 追加
    # def get_user_reminders():
    #     # user_id = g.current_user_id  # 信頼できるuser_id使用
    
    # @app.route('/api/reminder/<int:reminder_id>', methods=['DELETE'])
    # @require_auth(['delete'])  # 追加
    # def delete_reminder(reminder_id):
    #     # user_id = g.current_user_id  # 信頼できるuser_id使用
    
    # @app.route('/webhook/line', methods=['POST'])
    # @require_line_auth  # 追加（署名検証）
    # def line_webhook():
    #     # LINE認証を通過したもののみ処理
    
    pass

# Supabase RLS (Row Level Security) 設定用SQL
SUPABASE_RLS_POLICIES = """
-- Conversations テーブル
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only access their own conversations" 
ON conversations FOR ALL 
USING (auth.uid()::text = user_id);

-- Reminders テーブル  
ALTER TABLE reminders ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only access their own reminders"
ON reminders FOR ALL
USING (auth.uid()::text = user_id);

-- Knowledge Base - 読み取りは全員、書き込みは認証済みユーザー
ALTER TABLE knowledge_base ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read knowledge base"
ON knowledge_base FOR SELECT
USING (true);

CREATE POLICY "Authenticated users can insert knowledge"
ON knowledge_base FOR INSERT
WITH CHECK (auth.role() = 'authenticated');

-- Users テーブル
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own profile"
ON users FOR SELECT
USING (auth.uid()::text = id);

CREATE POLICY "Users can update own profile"  
ON users FOR UPDATE
USING (auth.uid()::text = id);
"""