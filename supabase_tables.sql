-- Supabaseテーブル作成SQL
-- このSQLをSupabaseのSQL Editorで実行してください

-- 1. conversationsテーブル
CREATE TABLE IF NOT EXISTS conversations (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    conversation_id VARCHAR(255),
    user_message TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    keywords TEXT[],
    context_used TEXT,
    source_platform VARCHAR(50) DEFAULT 'web',
    response_time_ms INTEGER,
    satisfaction_rating INTEGER CHECK (satisfaction_rating >= 1 AND satisfaction_rating <= 5),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- conversationsのインデックス
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at);

-- 2. remindersテーブル
CREATE TABLE IF NOT EXISTS reminders (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    reminder_time TIME NOT NULL,
    repeat_pattern VARCHAR(50) DEFAULT 'once',
    repeat_days TEXT[],
    last_sent_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- remindersのインデックス
CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id);
CREATE INDEX IF NOT EXISTS idx_reminders_active ON reminders(is_active);
CREATE INDEX IF NOT EXISTS idx_reminders_time ON reminders(reminder_time);

-- 3. Row Level Security (RLS) を有効化
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE reminders ENABLE ROW LEVEL SECURITY;

-- 4. Service Roleのアクセスポリシー
CREATE POLICY "Service role can access all conversations" ON conversations
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role can access all reminders" ON reminders
    FOR ALL USING (auth.role() = 'service_role');