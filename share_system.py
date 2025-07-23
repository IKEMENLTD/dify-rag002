# -*- coding: utf-8 -*-
"""
URL指定での過去会話履歴共有システム
権限ベースアクセス制御付き
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from flask import request, jsonify, g, render_template_string

def create_share_conversations_table(supabase):
    """共有会話テーブル作成"""
    sql = """
    -- 共有会話テーブル
    CREATE TABLE IF NOT EXISTS shared_conversations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
        share_token TEXT UNIQUE NOT NULL,
        created_by UUID REFERENCES users(id) ON DELETE CASCADE,
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        permissions TEXT[] DEFAULT ARRAY['read'],
        password_hash TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        access_count INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- インデックス
    CREATE INDEX IF NOT EXISTS idx_shared_conversations_token ON shared_conversations(share_token);
    CREATE INDEX IF NOT EXISTS idx_shared_conversations_expires ON shared_conversations(expires_at);
    
    -- RLS有効化
    ALTER TABLE shared_conversations ENABLE ROW LEVEL SECURITY;
    
    -- RLSポリシー
    CREATE POLICY "Users can manage own shared conversations" ON shared_conversations
        FOR ALL USING (
            created_by IN (
                SELECT id FROM users WHERE auth_user_id = auth.uid()
            )
        );
    """
    return sql

def create_conversation_share_link(supabase, conversation_id, user_id, expires_hours=24, password=None, permissions=None):
    """会話共有リンク生成"""
    try:
        # 会話の所有者確認
        conversation = supabase.table('conversations')\
            .select('*')\
            .eq('id', conversation_id)\
            .eq('user_uuid', user_id)\
            .single()\
            .execute()
        
        if not conversation.data:
            return {'error': '会話が見つかりません'}
        
        # 共有トークン生成
        share_token = secrets.token_urlsafe(32)
        share_data = {
            'conversation_id': conversation_id,
            'share_token': share_token,
            'created_by': user_id,
            'expires_at': (datetime.utcnow() + timedelta(hours=expires_hours)).isoformat(),
            'permissions': permissions or ['read'],
            'password_hash': hashlib.sha256(password.encode()).hexdigest() if password else None,
            'is_active': True,
            'created_at': datetime.utcnow().isoformat()
        }
        
        # shared_conversationsテーブルに保存
        result = supabase.table('shared_conversations').insert(share_data).execute()
        
        return {
            'success': True,
            'share_token': share_token,
            'expires_at': share_data['expires_at'],
            'permissions': permissions or ['read']
        }
        
    except Exception as e:
        return {'error': f'共有リンク生成エラー: {str(e)}'}

def verify_share_token(supabase, share_token, password=None):
    """共有トークン検証"""
    try:
        # 共有データ取得
        share_data = supabase.table('shared_conversations')\
            .select('*, conversations(*)')\
            .eq('share_token', share_token)\
            .eq('is_active', True)\
            .single()\
            .execute()
        
        if not share_data.data:
            return {'error': '無効な共有トークン'}
        
        # 有効期限チェック
        expires_at = datetime.fromisoformat(share_data.data['expires_at'].replace('Z', '+00:00'))
        if datetime.utcnow().replace(tzinfo=expires_at.tzinfo) > expires_at:
            return {'error': '共有リンクの有効期限切れ'}
        
        # パスワード保護チェック
        if share_data.data['password_hash']:
            if not password:
                return {'error': 'パスワードが必要', 'require_password': True}
            
            if hashlib.sha256(password.encode()).hexdigest() != share_data.data['password_hash']:
                return {'error': 'パスワードが間違っています'}
        
        # アクセス回数更新
        supabase.table('shared_conversations')\
            .update({'access_count': share_data.data['access_count'] + 1})\
            .eq('id', share_data.data['id'])\
            .execute()
        
        return {
            'success': True,
            'conversation': share_data.data['conversations'],
            'permissions': share_data.data['permissions'],
            'expires_at': share_data.data['expires_at']
        }
        
    except Exception as e:
        return {'error': f'検証エラー: {str(e)}'}

def get_related_conversations(supabase, user_uuid, current_conversation_id, limit=5):
    """関連会話履歴取得"""
    try:
        related_messages = supabase.table('conversations')\
            .select('*')\
            .eq('user_uuid', user_uuid)\
            .neq('id', current_conversation_id)\
            .order('created_at', desc=True)\
            .limit(limit)\
            .execute()
        
        return related_messages.data or []
    except:
        return []

# HTML テンプレート
SHARED_CONVERSATION_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>共有会話 - ベテランAI</title>
    <style>
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: #2c3e50;
            color: white;
            padding: 20px;
            text-align: center;
        }
        .conversation {
            padding: 30px;
        }
        .message {
            margin-bottom: 20px;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #3498db;
            background: #f8f9fa;
        }
        .message.user {
            border-left-color: #27ae60;
            background: #e8f5e8;
        }
        .message.ai {
            border-left-color: #e74c3c;
            background: #fdf2f2;
        }
        .timestamp {
            color: #666;
            font-size: 0.85em;
            margin-top: 5px;
        }
        .related-section {
            background: #f1f3f4;
            padding: 20px;
            margin-top: 20px;
            border-radius: 8px;
        }
        .related-title {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
            margin-bottom: 15px;
        }
        .related-item {
            background: white;
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 6px;
            border-left: 3px solid #95a5a6;
        }
        .footer {
            background: #34495e;
            color: #bdc3c7;
            padding: 15px 20px;
            text-align: center;
            font-size: 0.9em;
        }
        .password-form {
            text-align: center;
            padding: 40px;
        }
        .password-input {
            padding: 10px;
            border: 2px solid #ddd;
            border-radius: 6px;
            margin-right: 10px;
            font-size: 16px;
        }
        .password-button {
            padding: 10px 20px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
        }
        .password-button:hover {
            background: #2980b9;
        }
        .expire-info {
            background: #fff3cd;
            color: #856404;
            padding: 10px;
            border-radius: 6px;
            margin-top: 20px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔗 共有された会話</h1>
            <p>ベテランAI - 会話履歴共有</p>
        </div>
        
        {% if require_password %}
        <div class="password-form">
            <h2>🔒 パスワード認証</h2>
            <p>この会話を閲覧するにはパスワードが必要です</p>
            <form method="get">
                <input type="password" name="password" class="password-input" placeholder="パスワードを入力" required>
                <button type="submit" class="password-button">アクセス</button>
            </form>
        </div>
        {% else %}
        <div class="conversation">
            <h2 class="related-title">📝 メイン会話</h2>
            <div class="message user">
                <strong>👤 ユーザー:</strong><br>
                {{ conversation.user_message }}
                <div class="timestamp">{{ conversation.created_at }}</div>
            </div>
            <div class="message ai">
                <strong>🤖 ベテランAI:</strong><br>
                {{ conversation.ai_response }}
            </div>
            
            {% if related_conversations %}
            <div class="related-section">
                <h2 class="related-title">🔍 関連する会話履歴</h2>
                {% for msg in related_conversations %}
                <div class="related-item">
                    <strong>Q:</strong> {{ msg.user_message[:150] }}{% if msg.user_message|length > 150 %}...{% endif %}<br>
                    <strong>A:</strong> {{ msg.ai_response[:200] }}{% if msg.ai_response|length > 200 %}...{% endif %}
                    <div class="timestamp">{{ msg.created_at }}</div>
                </div>
                {% endfor %}
            </div>
            {% endif %}
            
            <div class="expire-info">
                ⏰ この共有リンクは {{ expires_at }} まで有効です
            </div>
        </div>
        {% endif %}
        
        <div class="footer">
            <p>🚀 Powered by ベテランAI | 企業レベル認証システム搭載</p>
        </div>
    </div>
</body>
</html>
"""