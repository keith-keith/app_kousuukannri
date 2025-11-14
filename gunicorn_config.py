# Gunicorn設定ファイル
# Azure App Service用の最適化された設定

import multiprocessing
import os

# サーバーソケット設定
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# ワーカー設定
# Azure App Serviceのメモリに応じて調整
workers = int(os.getenv('GUNICORN_WORKERS', '2'))
worker_class = 'sync'
worker_connections = 1000
timeout = 120  # タイムアウトを120秒に設定

# ログ設定
accesslog = '-'  # 標準出力
errorlog = '-'   # 標準エラー出力
loglevel = 'info'

# プロセス名
proc_name = 'kousu_kanri_app'

# 起動前のチェック
# preload_app = True を無効化してデプロイ時の更新を確実に反映
preload_app = False

# セキュリティ設定
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
