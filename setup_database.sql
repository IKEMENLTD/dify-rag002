-- ベテランAI認証システム用データベース設定
-- Supabase SQL Editorで実行してください

-- 1. ユーザーテーブル（Supabase Authと統合）
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE,
    display_name TEXT,
    line_id TEXT UNIQUE,
    role TEXT DEFAULT 'user' CHECK (role IN ('admin', 'moderator', 'user', 'readonly')),
    auth_provider TEXT DEFAULT 'email' CHECK (auth_provider IN ('email', 'line', 'api')),
    permissions TEXT[] DEFAULT ARRAY['read', 'write'],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. API Keyテーブル
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    api_key_hash TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    permissions TEXT[] DEFAULT ARRAY['read'],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '1 year')
);

-- 3. 既存テーブルの更新（user_idをUUID対応）
-- conversations テーブルの更新
ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS user_uuid UUID REFERENCES users(id);

-- reminders テーブルの更新  
ALTER TABLE reminders
ADD COLUMN IF NOT EXISTS user_uuid UUID REFERENCES users(id);

-- 4. インデックス作成（パフォーマンス向上）
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_line_id ON users(line_id);
CREATE INDEX IF NOT EXISTS idx_users_auth_user_id ON users(auth_user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(api_key_hash);
CREATE INDEX IF NOT EXISTS idx_conversations_user_uuid ON conversations(user_uuid);
CREATE INDEX IF NOT EXISTS idx_reminders_user_uuid ON reminders(user_uuid);

-- 5. Row Level Security (RLS) 有効化
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE reminders ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_base ENABLE ROW LEVEL SECURITY;

-- 6. RLSポリシー設定

-- Users テーブル: 自分のプロファイルのみアクセス可能
CREATE POLICY "Users can read own profile" ON users
    FOR SELECT USING (auth.uid() = auth_user_id);

CREATE POLICY "Users can update own profile" ON users  
    FOR UPDATE USING (auth.uid() = auth_user_id);

-- API Keys: 自分のAPI Keyのみ管理可能
CREATE POLICY "Users can manage own API keys" ON api_keys
    FOR ALL USING (
        user_id IN (
            SELECT id FROM users WHERE auth_user_id = auth.uid()
        )
    );

-- Conversations: 自分の会話のみアクセス可能
CREATE POLICY "Users can access own conversations" ON conversations
    FOR ALL USING (
        user_uuid IN (
            SELECT id FROM users WHERE auth_user_id = auth.uid()
        ) OR
        user_id IN (
            SELECT id::text FROM users WHERE auth_user_id = auth.uid()
        )
    );

-- Reminders: 自分のリマインダーのみアクセス可能  
CREATE POLICY "Users can access own reminders" ON reminders
    FOR ALL USING (
        user_uuid IN (
            SELECT id FROM users WHERE auth_user_id = auth.uid()
        ) OR
        user_id IN (
            SELECT id::text FROM users WHERE auth_user_id = auth.uid()
        )
    );

-- Knowledge Base: 読み取りは全員、書き込みは認証済みユーザー
CREATE POLICY "Anyone can read knowledge base" ON knowledge_base
    FOR SELECT USING (true);

CREATE POLICY "Authenticated users can insert knowledge" ON knowledge_base
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Users can update own knowledge entries" ON knowledge_base
    FOR UPDATE USING (
        created_by IN (
            SELECT id::text FROM users WHERE auth_user_id = auth.uid()
        )
    );

-- 7. トリガー関数（updated_at自動更新）
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- updated_atトリガー設定
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 8. 管理者ユーザー作成用関数
CREATE OR REPLACE FUNCTION create_user_profile(
    p_auth_user_id UUID,
    p_email TEXT,
    p_display_name TEXT DEFAULT NULL,
    p_role TEXT DEFAULT 'user'
)
RETURNS UUID AS $$
DECLARE
    new_user_id UUID;
BEGIN
    INSERT INTO users (auth_user_id, email, display_name, role)
    VALUES (p_auth_user_id, p_email, p_display_name, p_role)
    RETURNING id INTO new_user_id;
    
    RETURN new_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 9. LINE ユーザー作成用関数
CREATE OR REPLACE FUNCTION create_line_user(
    p_line_id TEXT,
    p_display_name TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    new_user_id UUID;
BEGIN
    INSERT INTO users (line_id, display_name, auth_provider, email)
    VALUES (p_line_id, COALESCE(p_display_name, 'LINE_' || SUBSTRING(p_line_id, 1, 8)), 'line', p_line_id || '@line.temp')
    RETURNING id INTO new_user_id;
    
    RETURN new_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 10. 初期データ挿入（テスト用管理者アカウント）
-- 注意: 本番環境では削除してください
-- INSERT INTO users (email, display_name, role, auth_provider) 
-- VALUES ('admin@example.com', 'システム管理者', 'admin', 'email')
-- ON CONFLICT (email) DO NOTHING;

-- 11. データベース統計更新
ANALYZE users;
ANALYZE api_keys;
ANALYZE conversations;
ANALYZE reminders;
ANALYZE knowledge_base;