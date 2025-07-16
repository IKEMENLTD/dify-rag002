#!/usr/bin/env python3
"""
超シンプルなテストサーバー
Renderでの動作確認用
"""

import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return "Hello from ベテランAI!"

@app.route('/ping')
def ping():
    return "pong"

@app.route('/test')
def test():
    return {
        'status': 'OK',
        'message': 'Simple test server is working',
        'port': os.environ.get('PORT', '5000')
    }

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Simple test server starting on port {port}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False
    )