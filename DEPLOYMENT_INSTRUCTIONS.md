# ベテランAI デプロイメント手順

## 🚀 Render.comでの環境変数設定

### 1. Render Dashboardにアクセス
1. https://dashboard.render.com/ にログイン
2. `veteranai-final-test` サービスを選択
3. 左メニューの「Environment」をクリック

### 2. 環境変数を追加
以下の環境変数を設定してください：

```
# API Keys
ANTHROPIC_API_KEY=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
DIFY_API_KEY=app-tXgqxhuEnLazcVn5CT1AmiWu
SECRET_KEY=your-super-secret-key-change-this-in-production

# LINE Bot Configuration
LINE_CHANNEL_SECRET=ea231e1ac03f19f368af300c17104e16
LINE_CHANNEL_ACCESS_TOKEN=jCsq/tLhpn4i+EzDY8xBtONEQ4Nbs1F0yz2hN4gkYY3Pzc+e2tuCVsqYzucoeMdnZtiOiar474nT/VmVNqiQOPSrvi/kn7OcWuWqFmS4NetYmQ6Bz4KJhhjr3t38fiHTfz0RIwAoHJ4TOHTVxm0NhgdB04t89/1O/w1cDnyilFU=

# Supabase Configuration
SUPABASE_URL=https://affywfiggofwsdvdphye.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFmZnl3ZmlnZ29md3NkdmRwaHllIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDM4NDU0MCwiZXhwIjoyMDY1OTYwNTQwfQ.91u10l8VVGtb5ADwQ3rRu3i-duy_Ikj_cZ_uF4Nt0aQ

# Database
DATABASE_URL=postgresql://postgres:[R201704340wx.]@[affywfiggofwsdvdphye].supabase.co:5432/postgres

# Optional
CORS_ORIGINS=*
DIFY_API_BASE_URL=https://api.dify.ai/v1
```

### 3. 保存して再デプロイ
「Save Changes」をクリックすると自動的に再デプロイが開始されます。

## 📱 LINE Bot設定

### LINE Developersでの設定
1. https://developers.line.biz/ にログイン
2. チャネルのWebhook URLを以下に設定：
   ```
   https://veteranai-final-test.onrender.com/webhook/line
   ```
3. Webhook利用を「オン」に設定
4. 応答メッセージを「オフ」に設定

## 🌐 利用可能なエンドポイント

- **ホーム**: https://veteranai-final-test.onrender.com/
- **チャット画面**: https://veteranai-final-test.onrender.com/chat
- **API**: https://veteranai-final-test.onrender.com/api/chat
- **LINE Webhook**: https://veteranai-final-test.onrender.com/webhook/line

## 🔍 動作確認

1. チャット画面にアクセスしてメッセージを送信
2. LINE Botに友達追加してメッセージを送信
3. APIが正しく応答することを確認

## ⚠️ セキュリティ注意事項

現在の環境変数にはセンシティブな情報が含まれています。本番環境では必ず新しいAPIキーに変更してください。