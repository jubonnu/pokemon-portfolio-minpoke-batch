#!/usr/bin/env python3
"""
Pokemon Card Scraping Batch
pokeca-chart.com からカード情報をスクレイピングしてPostgreSQLに保存
"""

import asyncio
import sys
import time
from datetime import datetime
from typing import Optional, Tuple, List

from dotenv import load_dotenv
from tqdm import tqdm

from src.api_client import PokecaAPIClient, fetch_card_details
from src.config import settings
from src.database import Database
from src.models import CardItem, ChartData, GradingInfo, PriceInfo, WordPressPost

# .envファイルを読み込み
load_dotenv()


async def process_card(
    client: PokecaAPIClient,
    db: Database,
    wp_post: WordPressPost,
    pbar: tqdm,
) -> Tuple[Optional[int], int, int, int]:
    """
    1枚のカードを処理
    Returns: (db_item_id, price_count, chart_count, grading_count)
    """
    try:
        card, price_info, chart_data, grading_info = await fetch_card_details(client, wp_post)

        if not card:
            pbar.write(f"⚠️ スキップ: {wp_post.title} (item_id取得失敗)")
            return None, 0, 0, 0

        # アイテムをDBに保存してIDを取得
        try:
            db_item_id = await db.upsert_item(card)
        except Exception as e:
            pbar.write(f"⚠️ アイテム保存エラー: {wp_post.title} - {e}")
            return None, 0, 0, 0

        # データ取得状況をログ出力（最初の5件のみ）
        if not hasattr(process_card, '_debug_count'):
            process_card._debug_count = 0
        
        if process_card._debug_count < 5:
            pbar.write(f"🔍 デバッグ [{wp_post.title}]: price_info={price_info is not None}, chart_data={len(chart_data) if chart_data else 0}件, grading_info={grading_info is not None}")
            process_card._debug_count += 1

        # 価格情報を保存
        price_count = 0
        if price_info:
            try:
                await db.upsert_price_info(price_info, db_item_id)
                price_count = 1
                if process_card._debug_count <= 5:
                    pbar.write(f"✅ 価格情報保存成功: {wp_post.title}")
            except Exception as e:
                pbar.write(f"⚠️ 価格情報保存エラー: {wp_post.title} - {e}")
                import traceback
                pbar.write(f"   詳細: {traceback.format_exc()}")
        else:
            # デバッグ: 価格情報が取得できていない
            if card.id:  # item_idが存在する場合のみ
                pbar.write(f"⚠️ 価格情報が取得できませんでした: {wp_post.title} (item_id: {card.id})")

        # チャートデータを保存
        chart_count = 0
        if chart_data:
            for chart in chart_data:
                try:
                    await db.upsert_chart_data(chart, db_item_id)
                    chart_count += 1
                except Exception as e:
                    pbar.write(f"⚠️ チャートデータ保存エラー: {wp_post.title} (date: {chart.date}) - {e}")
                    import traceback
                    pbar.write(f"   詳細: {traceback.format_exc()}")
            if process_card._debug_count <= 5 and chart_count > 0:
                pbar.write(f"✅ チャートデータ保存成功: {wp_post.title} ({chart_count}件)")
        else:
            # デバッグ: チャートデータが取得できていない
            if card.id:  # item_idが存在する場合のみ
                pbar.write(f"⚠️ チャートデータが取得できませんでした: {wp_post.title} (item_id: {card.id})")

        # グレーディング情報を保存
        grading_count = 0
        if grading_info:
            try:
                await db.upsert_grading(grading_info, db_item_id)
                grading_count = 1
                if process_card._debug_count <= 5:
                    pbar.write(f"✅ グレーディング情報保存成功: {wp_post.title}")
            except Exception as e:
                pbar.write(f"⚠️ グレーディング情報保存エラー: {wp_post.title} - {e}")
                import traceback
                pbar.write(f"   詳細: {traceback.format_exc()}")
        else:
            # デバッグ: グレーディング情報が取得できていない
            if card.id:  # item_idが存在する場合のみ
                pbar.write(f"⚠️ グレーディング情報が取得できませんでした: {wp_post.title} (item_id: {card.id})")

        return db_item_id, price_count, chart_count, grading_count

    except Exception as e:
        pbar.write(f"❌ エラー: {wp_post.title} - {e}")
        import traceback
        pbar.write(f"   詳細: {traceback.format_exc()}")
        return None, 0, 0, 0


async def process_cards_batch(
    client: PokecaAPIClient,
    db: Database,
    wp_posts: List[WordPressPost],
    pbar: tqdm,
) -> Tuple[int, int, int, int]:
    """
    カードをバッチで並列処理
    Returns: (items_count, price_count, chart_count, grading_count)
    """
    tasks = [
        process_card(client, db, wp_post, pbar)
        for wp_post in wp_posts
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    items_count = 0
    price_count = 0
    chart_count = 0
    grading_count = 0

    for result in results:
        if isinstance(result, Exception):
            pbar.write(f"❌ バッチエラー: {result}")
            continue
        if result[0]:
            items_count += 1
            price_count += result[1]
            chart_count += result[2]
            grading_count += result[3]

    return items_count, price_count, chart_count, grading_count


async def main():
    """メイン処理"""
    print("=" * 60)
    print("🎴 Pokemon Card Scraping Batch")
    print(f"⏰ 開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    start_time = time.time()

    # データベース接続
    db = Database()
    await db.connect()

    try:
        async with PokecaAPIClient() as client:
            # WordPress REST APIから全カードを取得
            print("\n📥 WordPress APIからカード一覧を取得中...")
            wp_posts = await client.get_all_posts()
            print(f"✅ 取得完了: {len(wp_posts)} 件のカード")

            if not wp_posts:
                print("⚠️ カードが見つかりませんでした")
                return

            # 進捗バー付きで処理
            print("\n🔄 カードデータを処理中...")
            total_items = 0
            total_prices = 0
            total_charts = 0
            total_gradings = 0

            with tqdm(total=len(wp_posts), desc="処理中", unit="cards") as pbar:
                # バッチサイズごとに処理
                batch_size = settings.batch_size
                for i in range(0, len(wp_posts), batch_size):
                    batch = wp_posts[i : i + batch_size]
                    items, prices, charts, gradings = await process_cards_batch(
                        client, db, batch, pbar
                    )
                    total_items += items
                    total_prices += prices
                    total_charts += charts
                    total_gradings += gradings
                    pbar.update(len(batch))

                    # レート制限対策
                    await asyncio.sleep(settings.request_delay)

            # 統計情報を表示
            elapsed = time.time() - start_time
            stats = await db.get_stats()

            print("\n" + "=" * 60)
            print("📊 処理結果")
            print("=" * 60)
            print(f"処理カード数: {total_items}")
            print(f"価格情報: {total_prices}")
            print(f"チャートデータ: {total_charts}")
            print(f"グレーディング情報: {total_gradings}")
            print(f"\n📈 データベース統計:")
            for table, count in stats.items():
                print(f"  {table}: {count:,} 件")
            print(f"\n⏱️ 処理時間: {elapsed:.2f} 秒")
            print(f"📈 処理速度: {len(wp_posts) / elapsed:.2f} cards/sec")
            
            # データ取得率を計算
            if total_items > 0:
                print(f"\n📊 データ取得率:")
                print(f"  価格情報: {total_prices}/{total_items} ({total_prices/total_items*100:.1f}%)")
                print(f"  チャートデータ: {total_charts}/{total_items} ({total_charts/total_items*100:.1f}%)")
                print(f"  グレーディング情報: {total_gradings}/{total_items} ({total_gradings/total_items*100:.1f}%)")

    finally:
        await db.close()

    print("\n✅ バッチ処理完了!")
    print(f"⏰ 終了時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ 処理が中断されました")
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"\n❌ 致命的エラー: {e}")
        print(f"\n詳細:")
        traceback.print_exc()
        sys.exit(1)

