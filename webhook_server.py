#!/usr/bin/env python3
"""
GitHub Webhook受信サーバー
GitHubからのpushイベントを受信してアプリケーションを自動更新する
"""

import os
import subprocess
import hmac
import hashlib
import json
from flask import Flask, request, jsonify
import logging

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/webhook.log'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)

# 設定
WEBHOOK_SECRET = "crypto_trading_bot_webhook_secret_2024"  # GitHubで設定する秘密鍵
REPO_PATH = "/home/ubuntu/crypto-trading-bot"
SERVICE_NAME = "trading-bot.service"

def verify_signature(payload_body, signature_header):
    """GitHubからの署名を検証"""
    if not signature_header:
        return False
    
    try:
        hash_type, signature = signature_header.split('=')
        if hash_type != 'sha256':
            return False
        
        mac = hmac.new(
            WEBHOOK_SECRET.encode('utf-8'),
            payload_body,
            hashlib.sha256
        )
        return hmac.compare_digest(mac.hexdigest(), signature)
    except Exception as e:
        logging.error(f"署名検証エラー: {e}")
        return False

def update_application():
    """アプリケーションを更新"""
    try:
        # リポジトリのディレクトリに移動してgit pull
        logging.info("アプリケーション更新開始")
        
        # git pull実行
        result = subprocess.run(
            ['git', 'pull', 'origin', 'main'],
            cwd=REPO_PATH,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logging.info(f"Git pull成功: {result.stdout}")
            
            # サービス再起動
            restart_result = subprocess.run(
                ['sudo', 'systemctl', 'restart', SERVICE_NAME],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if restart_result.returncode == 0:
                logging.info("サービス再起動成功")
                return True, "アプリケーション更新完了"
            else:
                logging.error(f"サービス再起動失敗: {restart_result.stderr}")
                return False, f"サービス再起動失敗: {restart_result.stderr}"
        else:
            logging.error(f"Git pull失敗: {result.stderr}")
            return False, f"Git pull失敗: {result.stderr}"
            
    except subprocess.TimeoutExpired:
        logging.error("コマンド実行タイムアウト")
        return False, "コマンド実行タイムアウト"
    except Exception as e:
        logging.error(f"更新プロセスエラー: {e}")
        return False, f"更新プロセスエラー: {e}"

@app.route('/webhook', methods=['POST'])
def webhook():
    """GitHubからのWebhookを処理"""
    
    # リクエストの署名を検証
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(request.data, signature):
        logging.warning("無効な署名でのWebhookアクセス")
        return jsonify({'error': '無効な署名'}), 401
    
    # JSONペイロードを解析
    try:
        payload = request.get_json()
        
        # pushイベントのみ処理
        if request.headers.get('X-GitHub-Event') == 'push':
            ref = payload.get('ref', '')
            
            # mainブランチへのpushのみ処理
            if ref == 'refs/heads/main':
                logging.info("mainブランチへのpushを検出、更新開始")
                
                success, message = update_application()
                
                if success:
                    return jsonify({
                        'status': 'success',
                        'message': message
                    }), 200
                else:
                    return jsonify({
                        'status': 'error',
                        'message': message
                    }), 500
            else:
                logging.info(f"他のブランチへのpush: {ref} (無視)")
                return jsonify({
                    'status': 'ignored',
                    'message': 'mainブランチ以外のpush'
                }), 200
        else:
            logging.info(f"pushイベント以外: {request.headers.get('X-GitHub-Event')} (無視)")
            return jsonify({
                'status': 'ignored',
                'message': 'pushイベント以外'
            }), 200
            
    except Exception as e:
        logging.error(f"Webhookペイロード処理エラー: {e}")
        return jsonify({
            'status': 'error',
            'message': f'ペイロード処理エラー: {e}'
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """ヘルスチェックエンドポイント"""
    return jsonify({
        'status': 'healthy',
        'service': 'webhook-server'
    }), 200

if __name__ == '__main__':
    # ポート8080でWebhookサーバーを起動
    app.run(host='0.0.0.0', port=8080, debug=False)