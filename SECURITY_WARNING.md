# ⚠️ 重要なセキュリティ警告

## 緊急対応が必要な事項

以下のAPIキーとシークレットが露出しています。**即座に無効化し、新しいものを生成してください**：

1. **ANTHROPIC_API_KEY** 
   - 現在の値: `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`
   - 対応: [Anthropic Console](https://console.anthropic.com/)でキーを無効化し、新規生成

2. **LINE_CHANNEL_ACCESS_TOKEN**
   - 現在の値: `jCsq/tLhpn4i+EzDY8xBtONEQ4Nbs1F0yz2hN4gkYY3Pzc+e2tuCVsqYzucoeMdnZtiOiar474nT/VmVNqiQOPSrvi/kn7OcWuWqFmS4NetYmQ6Bz4KJhhjr3t38fiHTfz0RIwAoHJ4TOHTVxm0NhgdB04t89/1O/w1cDnyilFU=`
   - 対応: LINE Developersコンソールでトークンを再発行

3. **SUPABASE_KEY**
   - 現在の値: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFmZnl3ZmlnZ29md3NkdmRwaHllIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDM4NDU0MCwiZXhwIjoyMDY1OTYwNTQwfQ.91u10l8VVGtb5ADwQ3rRu3i-duy_Ikj_cZ_uF4Nt0aQ`
   - 対応: Supabaseダッシュボードで新しいサービスロールキーを生成

4. **DATABASE_URL**
   - パスワードが含まれています: `R201704340wx.`
   - 対応: データベースのパスワードを変更

## 今後の対策

1. **環境変数の管理**
   - APIキーは絶対に公開リポジトリにコミットしない
   - `.env`ファイルを使用し、`.gitignore`に追加
   - 本番環境ではRenderの環境変数管理を使用

2. **セキュリティベストプラクティス**
   - 定期的なAPIキーのローテーション
   - 最小権限の原則に従う
   - アクセスログの監視

3. **コードレビュー**
   - APIキーやパスワードがハードコードされていないことを確認
   - セキュリティスキャンツールの導入

## 設定手順

1. 新しいAPIキーを生成
2. Renderの環境変数を更新
3. アプリケーションを再デプロイ
4. 動作確認

## 連絡先

セキュリティに関する質問や懸念事項がある場合は、すぐにシステム管理者に連絡してください。