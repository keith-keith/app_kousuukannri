#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Azure App Service用スタートアップスクリプト
Gunicornを使用してFlaskアプリケーションを起動
"""

import os
from app import app

# Gunicorn用のエクスポート
# Gunicornは "startup:app" として起動される
application = app

if __name__ == "__main__":
    # ローカル開発用（Azure App Serviceではこのブロックは実行されない）
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
