#!/usr/bin/env python3
"""データベース接続テストスクリプト"""

import asyncio
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv
import asyncpg

load_dotenv()

async def test_connection():
    """データベース接続をテスト"""
    from src.config import settings
    
    db_url = settings.database_url.strip()
    
    print("=" * 60)
    print("🔍 データベース接続テスト")
    print("=" * 60)
    
    # URLのパース
    print(f"\n1. URLの解析:")
    print(f"   元のURL: {db_url[:80]}...")
    
    try:
        parsed = urlparse(db_url)
        print(f"   スキーム: {parsed.scheme}")
        print(f"   ユーザー名: {parsed.username}")
        print(f"   パスワード: {'*' * len(parsed.password) if parsed.password else 'None'}")
        print(f"   ホスト名: {parsed.hostname}")
        print(f"   ポート: {parsed.port}")
        print(f"   データベース: {parsed.path.lstrip('/')}")
        
        if not parsed.hostname:
            print("\n❌ エラー: ホスト名が解析できませんでした")
            return False
            
    except Exception as e:
        print(f"\n❌ URL解析エラー: {e}")
        return False
    
    # DNS解決テスト
    print(f"\n2. DNS解決テスト:")
    try:
        import socket
        hostname = parsed.hostname
        print(f"   ホスト名を解決中: {hostname}")
        ip_address = socket.gethostbyname(hostname)
        print(f"   ✅ 解決成功: {hostname} -> {ip_address}")
    except socket.gaierror as e:
        print(f"   ❌ DNS解決失敗: {e}")
        print(f"   ネットワーク接続を確認してください")
        return False
    except Exception as e:
        print(f"   ❌ エラー: {e}")
        return False
    
    # データベース接続テスト
    print(f"\n3. データベース接続テスト:")
    try:
        print(f"   接続中...")
        conn = await asyncpg.connect(db_url, timeout=10)
        print(f"   ✅ 接続成功!")
        
        # 簡単なクエリを実行
        version = await conn.fetchval("SELECT version()")
        print(f"   PostgreSQLバージョン: {version[:50]}...")
        
        await conn.close()
        print(f"   ✅ 接続テスト完了")
        return True
        
    except asyncpg.exceptions.InvalidPasswordError:
        print(f"   ❌ 認証エラー: パスワードが間違っています")
        return False
    except asyncpg.exceptions.ConnectionDoesNotExistError:
        print(f"   ❌ 接続エラー: データベースが存在しません")
        return False
    except Exception as e:
        print(f"   ❌ 接続エラー: {e}")
        print(f"   エラータイプ: {type(e).__name__}")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(test_connection())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ テストが中断されました")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 致命的エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

