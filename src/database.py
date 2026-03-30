"""データベース操作 - Supabaseクライアント使用"""

import asyncio
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Callable, TypeVar

import httpx
from supabase import create_client, Client

from .config import settings
from .models import CardItem, ChartData, GradingInfo, PriceInfo

T = TypeVar("T")


def _is_retryable_supabase_error(exc: BaseException) -> bool:
    """httpx / ソケットの一過性エラー（並列過多・EAGAIN 等）なら True"""
    if isinstance(
        exc,
        (
            httpx.ReadError,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
            httpx.WriteError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.PoolTimeout,
        ),
    ):
        # Resource temporarily unavailable は ReadError 等として現れることが多い
        return True
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, OSError):
        errno = getattr(exc, "errno", None)
        if errno in (11, 35):  # EAGAIN, macOS EAGAIN
            return True
    return False


class Database:
    """Supabaseデータベース操作クラス"""

    def __init__(self):
        self.client: Optional[Client] = None
        self._write_sem = asyncio.Semaphore(settings.db_write_concurrency)

    async def _run_supabase(self, fn: Callable[[], T]) -> T:
        """同時書き込み数を制限し、一過性ネットワークエラーは指数バックオフで再試行"""
        max_attempts = max(1, settings.db_max_retries)
        async with self._write_sem:
            last_exc: Optional[BaseException] = None
            for attempt in range(max_attempts):
                try:
                    return await asyncio.to_thread(fn)
                except BaseException as e:
                    last_exc = e
                    if not _is_retryable_supabase_error(e) or attempt >= max_attempts - 1:
                        raise
                    wait = settings.retry_delay * (2**attempt)
                    await asyncio.sleep(wait)
            assert last_exc is not None
            raise last_exc

    async def connect(self):
        """Supabaseクライアントを初期化"""
        try:
            print(f"📡 Supabase接続中... ({settings.supabase_url})")

            # Supabaseクライアントを作成（同期APIなので、スレッドで実行）
            self.client = await asyncio.to_thread(
                create_client,
                settings.supabase_url,
                settings.supabase_key,
            )
            print("✅ Supabase接続完了")
        except Exception as e:
            print(f"❌ Supabase接続エラー: {e}")
            print(f"\n確認事項:")
            print(f"1. SUPABASE_URLが正しく設定されていますか？")
            print(f"2. SUPABASE_KEY（anon key）が正しく設定されていますか？")
            print(f"3. Supabaseダッシュボードの Settings > API から正しい値を取得していますか？")
            raise

    async def close(self):
        """接続を閉じる（Supabaseクライアントは特に閉じる必要がない）"""
        print("Supabase接続終了")

    async def upsert_item(self, item: CardItem) -> int:
        """アイテムをupsert（挿入または更新）してIDを返す"""
        assert self.client is not None

        def _search():
            return self.client.table("items2").select("id").eq("name", item.name).execute()

        existing_result = await self._run_supabase(_search)

        item_data = {
            "name": item.name,
            "series": item.series,
            "tags": item.tags,
            "transactions": item.transactions,
            "views": item.views,
            "image_url": item.image_url,
            "pv": item.pv,
            "updated_at": datetime.now().isoformat(),
        }

        if existing_result.data and len(existing_result.data) > 0:
            existing_id = existing_result.data[0]["id"]

            def _update():
                return self.client.table("items2").update(item_data).eq("id", existing_id).execute()

            await self._run_supabase(_update)
            return existing_id

        def _insert():
            return self.client.table("items2").insert(item_data).execute()

        result = await self._run_supabase(_insert)
        if result.data and len(result.data) > 0:
            return result.data[0]["id"]
        raise Exception("アイテムの挿入に失敗しました")

    async def upsert_items_batch(self, items: List[CardItem]) -> Dict[str, int]:
        """アイテムをバッチでupsertし、name -> db_id のマッピングを返す"""
        name_to_id = {}
        for item in items:
            db_id = await self.upsert_item(item)
            name_to_id[item.name] = db_id
        return name_to_id

    async def upsert_price_info(self, price_info: PriceInfo, db_item_id: int):
        """価格情報をupsert"""
        assert self.client is not None
        price_data = {
            "item_id": db_item_id,
            "deal_count": price_info.deal_count,
            "price_recent": price_info.price_recent,
            "price_min": price_info.price_min,
            "price_max": price_info.price_max,
            "price_avg": price_info.price_avg,
            "price_change_rate7": price_info.price_change_rate7,
            "price_change_rate30": price_info.price_change_rate30,
            "price_change7": price_info.price_change7,
            "price_change30": price_info.price_change30,
        }

        def _upsert_price():
            result = self.client.table("price_infos2").upsert(
                price_data, on_conflict="item_id"
            ).execute()
            if hasattr(result, "error") and result.error:
                raise Exception(f"価格情報のupsertエラー: {result.error}")
            return result

        await self._run_supabase(_upsert_price)

    async def upsert_price_infos_batch(self, price_infos: List[Tuple[PriceInfo, int]]):
        """価格情報をバッチでupsert"""
        if not price_infos:
            return
        assert self.client is not None

        price_data_list = [
            {
                "item_id": db_item_id,
                "deal_count": pi.deal_count,
                "price_recent": pi.price_recent,
                "price_min": pi.price_min,
                "price_max": pi.price_max,
                "price_avg": pi.price_avg,
                "price_change_rate7": pi.price_change_rate7,
                "price_change_rate30": pi.price_change_rate30,
                "price_change7": pi.price_change7,
                "price_change30": pi.price_change30,
            }
            for pi, db_item_id in price_infos
        ]

        def _upsert_prices():
            return self.client.table("price_infos2").upsert(
                price_data_list, on_conflict="item_id"
            ).execute()

        await self._run_supabase(_upsert_prices)

    async def upsert_chart_data(self, chart: ChartData, db_item_id: int):
        """チャートデータを1行upsert（大量投入時は upsert_charts_for_item を推奨）"""
        await self.upsert_charts_for_item([chart], db_item_id)

    async def upsert_charts_for_item(
        self, charts: List[ChartData], db_item_id: int
    ) -> int:
        """1アイテム分のチャートをチャンク単位でバッチupsert。保存した行数を返す"""
        if not charts:
            return 0
        chunk = max(1, settings.supabase_chart_batch_rows)
        total = 0
        for i in range(0, len(charts), chunk):
            part = charts[i : i + chunk]
            pairs = [(c, db_item_id) for c in part]
            await self.upsert_charts_batch(pairs)
            total += len(part)
        return total

    async def upsert_charts_batch(self, charts: List[Tuple[ChartData, int]]):
        """チャートデータをバッチでupsert"""
        if not charts:
            return
        assert self.client is not None

        chart_data_list = [
            {
                "item_id": db_item_id,
                "date": chart.date.isoformat()
                if hasattr(chart.date, "isoformat")
                else str(chart.date),
                "price1": chart.price1,
                "price2": chart.price2,
                "price3": chart.price3,
                "volume": chart.volume,
            }
            for chart, db_item_id in charts
        ]

        def _upsert_charts():
            result = self.client.table("charts2").upsert(
                chart_data_list, on_conflict="item_id,date"
            ).execute()
            if hasattr(result, "error") and result.error:
                raise Exception(f"チャートデータのupsertエラー: {result.error}")
            return result

        await self._run_supabase(_upsert_charts)

    async def upsert_grading(self, grading: GradingInfo, db_item_id: int):
        """グレーディング情報をupsert"""
        assert self.client is not None
        grading_data = {
            "item_id": db_item_id,
            "checked_at": grading.checked_at.isoformat() if grading.checked_at else None,
            "grd_status_auth": grading.grd_status_auth,
            "grd_status1": grading.grd_status1,
            "grd_status2": grading.grd_status2,
            "grd_status3": grading.grd_status3,
            "grd_status4": grading.grd_status4,
            "grd_status5": grading.grd_status5,
            "grd_status6": grading.grd_status6,
            "grd_status7": grading.grd_status7,
            "grd_status8": grading.grd_status8,
            "grd_status9": grading.grd_status9,
            "grd_status10": grading.grd_status10,
            "grd_status_all": grading.grd_status_all,
            "grd_url": grading.grd_url,
        }

        def _upsert_grading():
            result = self.client.table("gradings2").upsert(
                grading_data, on_conflict="item_id"
            ).execute()
            if hasattr(result, "error") and result.error:
                raise Exception(f"グレーディング情報のupsertエラー: {result.error}")
            return result

        await self._run_supabase(_upsert_grading)

    async def get_stats(self) -> Dict:
        """テーブル統計を取得"""
        assert self.client is not None
        stats = {}
        for table in ["items2", "price_infos2", "charts2", "gradings2"]:

            def _count(tbl=table):
                return self.client.table(tbl).select("id", count="exact").execute()

            result = await self._run_supabase(_count)
            stats[table] = (
                result.count
                if hasattr(result, "count")
                else len(result.data) if result.data else 0
            )
        return stats
