# 🔗 URL指定会話履歴共有システム

## 概要
認証システムと統合された**安全な会話共有機能**です。権限付与により、指定URLで過去の会話履歴にアクセスできます。

## 🚀 主要機能

### 1. **会話共有リンク生成**
```bash
POST /api/conversations/{conversation_id}/share
Authorization: Bearer YOUR_JWT_TOKEN

{
  "expires_hours": 48,          # 有効期限（時間）
  "password": "secure123",      # オプショナル保護
  "permissions": ["read"]       # read, comment
}
```

**レスポンス:**
```json
{
  "success": true,
  "share_url": "https://your-domain.com/share/vai_abcd1234...",
  "expires_at": "2024-01-15T10:30:00Z",
  "permissions": ["read"]
}
```

### 2. **共有会話アクセス**

#### HTML表示（ブラウザ用）
```
GET https://your-domain.com/share/{share_token}
GET https://your-domain.com/share/{share_token}?password=secure123
```

#### JSON API（プログラム用）
```
GET https://your-domain.com/api/share/{share_token}
GET https://your-domain.com/api/share/{share_token}?password=secure123
```

### 3. **共有管理**

#### 共有リンク一覧
```bash
GET /api/conversations/{conversation_id}/shares
Authorization: Bearer YOUR_JWT_TOKEN
```

#### 共有リンク無効化
```bash
DELETE /api/shares/{share_token}/revoke
Authorization: Bearer YOUR_JWT_TOKEN
```

## 💡 使用例

### シナリオ1: チーム内共有
```javascript
// 会話を24時間限定で共有
const response = await fetch('/api/conversations/abc-123/share', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + jwt_token,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    expires_hours: 24,
    permissions: ['read']
  })
});

const result = await response.json();
console.log('共有URL:', result.share_url);
// https://your-domain.com/share/vai_abc123xyz...
```

### シナリオ2: パスワード保護共有
```javascript
// 重要な会話をパスワード保護で共有
await fetch('/api/conversations/def-456/share', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + jwt_token,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    expires_hours: 72,
    password: 'team_secret_2024',
    permissions: ['read']
  })
});
```

### シナリオ3: 一時的なリンク
```javascript
// 1時間限定の短期共有
await fetch('/api/conversations/ghi-789/share', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + jwt_token,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    expires_hours: 1,
    permissions: ['read']
  })
});
```

## 🔒 セキュリティ機能

### 1. **アクセス制御**
- ✅ 会話所有者のみ共有リンク生成可能
- ✅ JWT/API Key認証による保護
- ✅ Row Level Security (RLS) でデータ分離

### 2. **時間制限**
- ✅ 指定時間での自動期限切れ
- ✅ アクセス回数追跡
- ✅ 期限切れリンクの自動無効化

### 3. **追加保護**
- ✅ オプショナルパスワード保護
- ✅ 権限レベル制御（read, comment等）
- ✅ 共有リンクの即座無効化

## 📊 表示内容

### HTML表示例
```
🔗 共有された会話
ベテランAI - 会話履歴共有

📝 メイン会話
👤 ユーザー: プロジェクトの進捗はどうですか？
🤖 ベテランAI: 現在、フェーズ2が完了し...

🔍 関連する会話履歴
Q: 予算について教えて...
A: 今期の予算は...

⏰ この共有リンクは 2024-01-15 10:30 まで有効です
```

### API レスペンス例
```json
{
  "success": true,
  "conversation": {
    "id": "abc-123",
    "user_message": "プロジェクトの進捗は？",
    "ai_response": "現在、フェーズ2が完了し...",
    "created_at": "2024-01-14T10:30:00Z"
  },
  "related_conversations": [
    {
      "user_message": "予算について...",
      "ai_response": "今期の予算は...",
      "created_at": "2024-01-13T14:20:00Z"
    }
  ],
  "permissions": ["read"],
  "expires_at": "2024-01-15T10:30:00Z"
}
```

## ⚡ 実装のポイント

### 1. **権限付与システム**
- 認証システムと完全統合
- ユーザー毎のデータ分離
- 細かい権限制御

### 2. **パフォーマンス最適化**
- インデックス最適化
- 関連会話の効率的取得
- アクセス統計の追跡

### 3. **ユーザー体験**
- 美しいHTML表示
- パスワード入力フォーム
- レスポンシブデザイン

---

**これで認証システムと統合された完璧な会話共有機能が実装されました！**

指定URLから**権限付きで**過去の会話履歴にアクセスでき、セキュリティも万全です。