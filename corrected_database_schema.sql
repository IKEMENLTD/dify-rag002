-- ============================================================================
-- 修正版データベーススキーマ
-- tl:dv API仕様に基づく正確なデータベース設計
-- LINE連携、マルチメディア対応
-- ============================================================================

-- 拡張機能の有効化
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================================
-- 1. ユーザー管理テーブル
-- ============================================================================

-- プラットフォーム共通ユーザー情報
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(20),
    avatar_url TEXT,
    timezone VARCHAR(50) DEFAULT 'Asia/Tokyo',
    language VARCHAR(10) DEFAULT 'ja',
    preferences JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- LINE固有ユーザー情報
CREATE TABLE line_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    line_user_id VARCHAR(255) UNIQUE NOT NULL,
    line_display_name VARCHAR(255),
    line_picture_url TEXT,
    line_status_message TEXT,
    rich_menu_id VARCHAR(255),
    is_friend BOOLEAN DEFAULT TRUE,
    blocked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- tl:dv API連携ユーザー情報
CREATE TABLE tldv_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    tldv_api_key TEXT NOT NULL,
    tldv_user_email VARCHAR(255),
    api_key_status VARCHAR(50) DEFAULT 'active', -- 'active', 'expired', 'revoked'
    last_sync_at TIMESTAMP WITH TIME ZONE,
    sync_status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'syncing', 'completed', 'failed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 2. 会話管理テーブル
-- ============================================================================

-- 会話セッション
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    platform VARCHAR(50) NOT NULL, -- 'web', 'line', 'tldv'
    platform_conversation_id VARCHAR(255),
    context_summary TEXT,
    keywords TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- メッセージ本体
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    message_type VARCHAR(50) NOT NULL, -- 'text', 'image', 'audio', 'video', 'file', 'sticker', 'tldv_summary'
    sender_type VARCHAR(20) NOT NULL, -- 'user', 'ai', 'system', 'tldv'
    content TEXT,
    original_content TEXT,
    metadata JSONB DEFAULT '{}',
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 3. tl:dv 会議データ管理（正確なAPI仕様に基づく）
-- ============================================================================

-- tl:dv 会議情報
CREATE TABLE tldv_meetings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    tldv_meeting_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(500) NOT NULL,
    date TIMESTAMP WITH TIME ZONE NOT NULL,
    url TEXT,
    duration INTEGER, -- 分単位
    organizer_name VARCHAR(255),
    organizer_email VARCHAR(255),
    meeting_type VARCHAR(50), -- 'internal', 'external'
    platform VARCHAR(50), -- 'zoom', 'teams', 'google_meet'
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'processing', 'completed', 'failed'
    imported_from_url TEXT,
    sync_status VARCHAR(50) DEFAULT 'pending',
    last_synced_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- tl:dv 会議参加者
CREATE TABLE tldv_meeting_participants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID REFERENCES tldv_meetings(id) ON DELETE CASCADE,
    name VARCHAR(255),
    email VARCHAR(255),
    role VARCHAR(50), -- 'organizer', 'attendee', 'guest'
    participation_status VARCHAR(50), -- 'accepted', 'declined', 'tentative', 'unknown'
    joined_at TIMESTAMP WITH TIME ZONE,
    left_at TIMESTAMP WITH TIME ZONE,
    duration_minutes INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- tl:dv トランスクリプト
CREATE TABLE tldv_transcripts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID REFERENCES tldv_meetings(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    language VARCHAR(10) DEFAULT 'ja',
    confidence_score DECIMAL(3,2),
    processing_status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    word_count INTEGER,
    speaker_segments JSONB DEFAULT '[]', -- [{"speaker": "name", "text": "content", "timestamp": "00:01:23"}]
    timestamps JSONB DEFAULT '{}', -- {"start": "00:00:00", "end": "01:30:45"}
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- tl:dv ハイライト・ノート
CREATE TABLE tldv_highlights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID REFERENCES tldv_meetings(id) ON DELETE CASCADE,
    highlight_type VARCHAR(50) NOT NULL, -- 'manual', 'auto_generated', 'ai_summary'
    title VARCHAR(500),
    content TEXT NOT NULL,
    timestamp VARCHAR(20), -- "00:15:30" 形式
    speaker VARCHAR(255),
    tags TEXT[],
    importance_score INTEGER CHECK (importance_score >= 1 AND importance_score <= 5),
    category VARCHAR(100), -- 'action_item', 'decision', 'question', 'insight', 'follow_up'
    created_by VARCHAR(255), -- ハイライトを作成したユーザー
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- tl:dv アクションアイテム
CREATE TABLE tldv_action_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID REFERENCES tldv_meetings(id) ON DELETE CASCADE,
    highlight_id UUID REFERENCES tldv_highlights(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    assignee_name VARCHAR(255),
    assignee_email VARCHAR(255),
    due_date DATE,
    priority VARCHAR(20) DEFAULT 'medium', -- 'low', 'medium', 'high', 'urgent'
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'in_progress', 'completed', 'cancelled'
    completion_percentage INTEGER DEFAULT 0 CHECK (completion_percentage >= 0 AND completion_percentage <= 100),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 4. AI統合分析テーブル
-- ============================================================================

-- tl:dv会議とAIチャットの関連付け
CREATE TABLE meeting_chat_relations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID REFERENCES tldv_meetings(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    relation_type VARCHAR(50) NOT NULL, -- 'follow_up', 'preparation', 'summary_request', 'action_review'
    context_summary TEXT,
    keywords_matched TEXT[],
    relevance_score DECIMAL(3,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- AI会議分析結果
CREATE TABLE ai_meeting_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID REFERENCES tldv_meetings(id) ON DELETE CASCADE,
    analysis_type VARCHAR(50) NOT NULL, -- 'sentiment', 'key_topics', 'action_items', 'decisions', 'follow_ups'
    analysis_result JSONB NOT NULL,
    ai_provider VARCHAR(50), -- 'dify', 'claude', 'custom'
    confidence_score DECIMAL(3,2),
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 5. メディアファイル管理
-- ============================================================================

-- メディアファイル情報
CREATE TABLE media_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    meeting_id UUID REFERENCES tldv_meetings(id) ON DELETE SET NULL, -- tl:dv関連ファイル
    file_type VARCHAR(50) NOT NULL, -- 'image', 'audio', 'video', 'document', 'meeting_recording'
    file_name VARCHAR(255) NOT NULL,
    file_size INTEGER,
    mime_type VARCHAR(100),
    file_url TEXT NOT NULL,
    thumbnail_url TEXT,
    duration_seconds INTEGER,
    transcription TEXT,
    alt_text TEXT,
    processing_status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processed', 'failed'
    storage_provider VARCHAR(50) DEFAULT 'local', -- 'local', 's3', 'tldv', 'line'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 6. AI応答管理
-- ============================================================================

-- AI応答履歴
CREATE TABLE ai_responses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    meeting_id UUID REFERENCES tldv_meetings(id) ON DELETE SET NULL, -- 会議関連AI応答
    ai_provider VARCHAR(50) NOT NULL, -- 'dify', 'claude', 'tldv_ai'
    model_name VARCHAR(100),
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    response_time_ms INTEGER,
    temperature DECIMAL(3,2),
    max_tokens INTEGER,
    context_used TEXT,
    confidence_score DECIMAL(3,2),
    input_data_sources TEXT[], -- ['transcript', 'highlights', 'chat_history']
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 7. 統計・分析テーブル
-- ============================================================================

-- ユーザー行動分析
CREATE TABLE user_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL, -- 'message_sent', 'file_upload', 'meeting_imported', 'transcript_viewed'
    platform VARCHAR(50) NOT NULL,
    event_data JSONB DEFAULT '{}',
    session_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 会議利用統計
CREATE TABLE meeting_usage_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    total_meetings INTEGER DEFAULT 0,
    total_duration_minutes INTEGER DEFAULT 0,
    transcripts_generated INTEGER DEFAULT 0,
    highlights_created INTEGER DEFAULT 0,
    action_items_created INTEGER DEFAULT 0,
    ai_queries_related INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, date)
);

-- ============================================================================
-- 8. システム機能テーブル
-- ============================================================================

-- tl:dv同期ログ
CREATE TABLE tldv_sync_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    sync_type VARCHAR(50) NOT NULL, -- 'full_sync', 'incremental', 'single_meeting'
    status VARCHAR(50) NOT NULL, -- 'started', 'in_progress', 'completed', 'failed'
    meetings_processed INTEGER DEFAULT 0,
    meetings_updated INTEGER DEFAULT 0,
    meetings_created INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    error_details JSONB DEFAULT '{}',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER
);

-- システムログ
CREATE TABLE system_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    log_level VARCHAR(20) NOT NULL, -- 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    component VARCHAR(50) NOT NULL, -- 'api', 'database', 'ai', 'line', 'tldv'
    message TEXT NOT NULL,
    details JSONB DEFAULT '{}',
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    meeting_id UUID REFERENCES tldv_meetings(id) ON DELETE SET NULL,
    session_id VARCHAR(255),
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- 9. インデックス設定
-- ============================================================================

-- ユーザー関連インデックス
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active);
CREATE INDEX idx_line_users_line_user_id ON line_users(line_user_id);
CREATE INDEX idx_tldv_users_user_id ON tldv_users(user_id);

-- 会話・メッセージ関連インデックス
CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_platform ON conversations(platform);
CREATE INDEX idx_conversations_active ON conversations(is_active);
CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_user_id ON messages(user_id);
CREATE INDEX idx_messages_type ON messages(message_type);
CREATE INDEX idx_messages_created_at ON messages(created_at);

-- tl:dv関連インデックス
CREATE INDEX idx_tldv_meetings_user_id ON tldv_meetings(user_id);
CREATE INDEX idx_tldv_meetings_meeting_id ON tldv_meetings(tldv_meeting_id);
CREATE INDEX idx_tldv_meetings_date ON tldv_meetings(date);
CREATE INDEX idx_tldv_meetings_status ON tldv_meetings(status);
CREATE INDEX idx_tldv_participants_meeting_id ON tldv_meeting_participants(meeting_id);
CREATE INDEX idx_tldv_transcripts_meeting_id ON tldv_transcripts(meeting_id);
CREATE INDEX idx_tldv_highlights_meeting_id ON tldv_highlights(meeting_id);
CREATE INDEX idx_tldv_highlights_type ON tldv_highlights(highlight_type);
CREATE INDEX idx_tldv_action_items_meeting_id ON tldv_action_items(meeting_id);
CREATE INDEX idx_tldv_action_items_status ON tldv_action_items(status);

-- AI・分析関連インデックス
CREATE INDEX idx_meeting_chat_relations_meeting_id ON meeting_chat_relations(meeting_id);
CREATE INDEX idx_meeting_chat_relations_conversation_id ON meeting_chat_relations(conversation_id);
CREATE INDEX idx_ai_meeting_analysis_meeting_id ON ai_meeting_analysis(meeting_id);
CREATE INDEX idx_ai_responses_message_id ON ai_responses(message_id);
CREATE INDEX idx_ai_responses_meeting_id ON ai_responses(meeting_id);

-- 統計・ログ関連インデックス
CREATE INDEX idx_user_analytics_user_id ON user_analytics(user_id);
CREATE INDEX idx_user_analytics_event_type ON user_analytics(event_type);
CREATE INDEX idx_user_analytics_created_at ON user_analytics(created_at);
CREATE INDEX idx_meeting_usage_stats_user_date ON meeting_usage_stats(user_id, date);
CREATE INDEX idx_tldv_sync_logs_user_id ON tldv_sync_logs(user_id);
CREATE INDEX idx_system_logs_component ON system_logs(component);
CREATE INDEX idx_system_logs_level ON system_logs(log_level);
CREATE INDEX idx_system_logs_created_at ON system_logs(created_at);

-- 全文検索インデックス
CREATE INDEX idx_messages_content_gin ON messages USING gin(to_tsvector('japanese', content));
CREATE INDEX idx_tldv_transcripts_content_gin ON tldv_transcripts USING gin(to_tsvector('japanese', content));
CREATE INDEX idx_tldv_highlights_content_gin ON tldv_highlights USING gin(to_tsvector('japanese', content));

-- ============================================================================
-- 10. Row Level Security (RLS) 設定
-- ============================================================================

-- RLS有効化
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE line_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE tldv_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE tldv_meetings ENABLE ROW LEVEL SECURITY;
ALTER TABLE tldv_meeting_participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tldv_transcripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE tldv_highlights ENABLE ROW LEVEL SECURITY;
ALTER TABLE tldv_action_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE meeting_chat_relations ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_meeting_analysis ENABLE ROW LEVEL SECURITY;
ALTER TABLE media_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE meeting_usage_stats ENABLE ROW LEVEL SECURITY;

-- Service Role用ポリシー（全データアクセス）
CREATE POLICY "Enable full access for service role" ON users FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Enable full access for service role" ON line_users FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Enable full access for service role" ON tldv_users FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Enable full access for service role" ON conversations FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Enable full access for service role" ON messages FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Enable full access for service role" ON tldv_meetings FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Enable full access for service role" ON tldv_meeting_participants FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Enable full access for service role" ON tldv_transcripts FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Enable full access for service role" ON tldv_highlights FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Enable full access for service role" ON tldv_action_items FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Enable full access for service role" ON meeting_chat_relations FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Enable full access for service role" ON ai_meeting_analysis FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Enable full access for service role" ON media_files FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Enable full access for service role" ON ai_responses FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Enable full access for service role" ON user_analytics FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Enable full access for service role" ON meeting_usage_stats FOR ALL USING (auth.role() = 'service_role');

-- ============================================================================
-- 11. 自動更新トリガー
-- ============================================================================

-- updated_at自動更新関数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- トリガー設定
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_line_users_updated_at BEFORE UPDATE ON line_users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_tldv_users_updated_at BEFORE UPDATE ON tldv_users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_messages_updated_at BEFORE UPDATE ON messages FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_tldv_meetings_updated_at BEFORE UPDATE ON tldv_meetings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_tldv_meeting_participants_updated_at BEFORE UPDATE ON tldv_meeting_participants FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_tldv_transcripts_updated_at BEFORE UPDATE ON tldv_transcripts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_tldv_highlights_updated_at BEFORE UPDATE ON tldv_highlights FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_tldv_action_items_updated_at BEFORE UPDATE ON tldv_action_items FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_media_files_updated_at BEFORE UPDATE ON media_files FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 12. 便利なビュー定義
-- ============================================================================

-- 会議とトランスクリプト結合ビュー
CREATE VIEW meeting_summary_view AS
SELECT 
    m.id as meeting_id,
    m.tldv_meeting_id,
    m.name as meeting_name,
    m.date as meeting_date,
    m.duration,
    m.organizer_name,
    m.platform,
    u.display_name as user_name,
    t.content as transcript,
    t.word_count,
    COUNT(h.id) as highlights_count,
    COUNT(ai.id) as action_items_count
FROM tldv_meetings m
JOIN users u ON m.user_id = u.id
LEFT JOIN tldv_transcripts t ON m.id = t.meeting_id
LEFT JOIN tldv_highlights h ON m.id = h.meeting_id
LEFT JOIN tldv_action_items ai ON m.id = ai.meeting_id
WHERE m.status = 'completed'
GROUP BY m.id, m.tldv_meeting_id, m.name, m.date, m.duration, m.organizer_name, m.platform, u.display_name, t.content, t.word_count;

-- 最近のユーザーアクティビティビュー
CREATE VIEW recent_user_activity AS
SELECT 
    u.id as user_id,
    u.display_name,
    COUNT(DISTINCT c.id) as recent_conversations,
    COUNT(DISTINCT m.id) as recent_meetings,
    COUNT(DISTINCT msg.id) as recent_messages,
    MAX(msg.created_at) as last_activity
FROM users u
LEFT JOIN conversations c ON u.id = c.user_id AND c.created_at >= NOW() - INTERVAL '7 days'
LEFT JOIN tldv_meetings m ON u.id = m.user_id AND m.date >= NOW() - INTERVAL '7 days'
LEFT JOIN messages msg ON u.id = msg.user_id AND msg.created_at >= NOW() - INTERVAL '7 days'
WHERE u.is_active = TRUE
GROUP BY u.id, u.display_name
ORDER BY last_activity DESC;

-- ============================================================================
-- 13. 初期データ
-- ============================================================================

-- システムユーザー
INSERT INTO users (id, username, display_name, is_active) VALUES
    ('00000000-0000-0000-0000-000000000001', 'system', 'System', TRUE),
    ('00000000-0000-0000-0000-000000000002', 'web_user', 'Web User', TRUE),
    ('00000000-0000-0000-0000-000000000003', 'line_bot', 'LINE Bot', TRUE),
    ('00000000-0000-0000-0000-000000000004', 'tldv_sync', 'tl:dv Sync', TRUE);

-- ============================================================================
-- コメント
-- ============================================================================

COMMENT ON TABLE tldv_meetings IS 'tl:dv API仕様に基づく会議データ';
COMMENT ON TABLE tldv_transcripts IS '会議の完全なトランスクリプト';
COMMENT ON TABLE tldv_highlights IS '手動・自動生成ハイライト';
COMMENT ON TABLE tldv_action_items IS 'ハイライトから抽出されたアクションアイテム';
COMMENT ON TABLE meeting_chat_relations IS '会議データとチャット会話の関連付け';
COMMENT ON TABLE ai_meeting_analysis IS 'AI による会議内容分析結果';

-- ============================================================================
-- 完了
-- ============================================================================