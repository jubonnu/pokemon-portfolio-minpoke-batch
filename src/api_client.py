"""APIクライアント"""

import asyncio
import json
import re
from datetime import datetime
from typing import Optional, Union, Dict, List, Tuple

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import settings
from .models import CardItem, ChartData, GradingInfo, PriceInfo, WordPressPost


# item_statusとカード状態のマッピング
ITEM_STATUS_MAP = {
    2: "psa10",      # PSA10
    3: "play",       # プレイ用
    36: "mint",      # 美品 (A)
    37: "scratched", # キズあり (B)
    39: "sealed",    # 未開封?
    42: "unknown1",
    45: "psa9",      # PSA9?
    60: "psa_high",  # 高グレードPSA
    61: "psa_auth",  # PSA認証済み
}


class PokecaAPIClient:
    """Pokeca Chart APIクライアント"""

    def __init__(self):
        self.base_url = settings.base_url
        self.wp_api_url = settings.wp_api_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(settings.concurrent_requests)
        # カテゴリIDと名前のキャッシュ
        self._category_cache: Dict[int, str] = {}

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(aiohttp.ClientResponseError),
    )
    async def _get(self, url: str, params: Optional[dict] = None) -> Union[dict, list, str]:
        """HTTP GETリクエスト"""
        async with self.semaphore:
            # リクエスト間の遅延
            await asyncio.sleep(settings.request_delay)
            
            try:
                async with self.session.get(url, params=params) as response:
                    # 503エラーの場合は特別な処理
                    if response.status == 503:
                        await asyncio.sleep(5)  # 503エラーの場合は5秒待機
                    
                    response.raise_for_status()
                    content_type = response.headers.get("Content-Type", "")
                    
                    # Content-Typeがapplication/jsonの場合はJSONとしてパース
                    if "application/json" in content_type:
                        return await response.json()
                    
                    # そうでない場合はテキストとして取得
                    text = await response.text()
                    
                    # "Connection failed:"などのエラーメッセージをチェック
                    if text.strip() == "Connection failed:" or text.strip().startswith("Connection failed"):
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=503,
                            message="Connection failed"
                        )
                    
                    # テキストがJSON形式の文字列かどうかをチェック
                    text_stripped = text.strip()
                    if (text_stripped.startswith("{") and text_stripped.endswith("}")) or \
                       (text_stripped.startswith("[") and text_stripped.endswith("]")):
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            # JSONパースに失敗した場合はテキストのまま返す
                            return text
                    
                    return text
            except aiohttp.ClientResponseError as e:
                # 503エラーの場合は詳細を出力しない（ログが多すぎるため）
                if e.status != 503:
                    print(f"❌ HTTP リクエストエラー (url={url}, params={params}): {type(e).__name__}: {e}")
                raise
            except aiohttp.ClientError as e:
                print(f"❌ HTTP リクエストエラー (url={url}, params={params}): {type(e).__name__}: {e}")
                raise
            except Exception as e:
                print(f"❌ 予期しないエラー (url={url}, params={params}): {type(e).__name__}: {e}")
                raise

    async def get_all_posts(self) -> List[WordPressPost]:
        """WordPress REST APIから全投稿を取得"""
        all_posts = []
        page = 1

        while True:
            url = f"{self.wp_api_url}/posts"
            params = {
                "per_page": settings.wp_per_page,
                "page": page,
                "_fields": "id,slug,title,link,featured_media,categories",
            }

            try:
                posts = await self._get(url, params)
                if not posts:
                    break

                for post in posts:
                    wp_post = WordPressPost(
                        id=post["id"],
                        slug=post["slug"],
                        title=post["title"]["rendered"],
                        link=post["link"],
                        featured_media=post.get("featured_media", 0),
                        categories=post.get("categories", []),
                    )
                    all_posts.append(wp_post)

                print(f"取得済み: {len(all_posts)} 件 (ページ {page})")

                if len(posts) < settings.wp_per_page:
                    break

                page += 1
                await asyncio.sleep(settings.request_delay)

            except aiohttp.ClientResponseError as e:
                if e.status == 400:
                    # ページが存在しない
                    break
                raise

        return all_posts

    async def get_item_id(self, card_url: str) -> Optional[int]:
        """カードURLからitem_idを取得"""
        url = f"{self.base_url}/ch/php/get-item-id.php"
        params = {"this_url": card_url}

        try:
            result = await self._get(url, params)
            if isinstance(result, str) and result.strip().isdigit():
                return int(result.strip())
            return None
        except Exception:
            return None

    async def get_item_image_url(self, item_id: int) -> Optional[str]:
        """item_idから画像URLを取得（get-image-url.php）"""
        url = f"{self.base_url}/ch/php/get-image-url.php"
        params = {"item_id": item_id}

        try:
            data = await self._get(url, params)
            if data and isinstance(data, list) and len(data) > 0:
                # img_url_full > img_url_large > img_url_medium の順で取得
                item = data[0]
                return (
                    item.get("img_url_full")
                    or item.get("img_url_large")
                    or item.get("img_url_medium")
                    or item.get("img_url_thumbnail")
                )
            return None
        except Exception:
            return None

    async def get_item_btn_link(self, item_id: int) -> Optional[dict]:
        """カード名と検索ワードを取得（get-item-btn-link.php）"""
        url = f"{self.base_url}/ch/php/get-item-btn-link.php"
        params = {"item_id": item_id}

        try:
            data = await self._get(url, params)
            if data and isinstance(data, dict):
                return {
                    "name": data.get("name", ""),
                    "search_word": data.get("search_word", ""),
                }
            return None
        except Exception:
            return None

    async def get_item_table(self, item_id: int) -> Optional[dict]:
        """価格テーブル情報を取得（get-item-table.php）- transactionsを含む"""
        url = f"{self.base_url}/ch/php/get-item-table.php"
        params = {"item_id": item_id}

        try:
            data = await self._get(url, params)
            if data and isinstance(data, dict):
                return data
            print(f"⚠️ get_item_table: データが取得できませんでした (item_id={item_id}): {type(data)} - {data}")
            return None
        except Exception as e:
            print(f"❌ get_item_table エラー (item_id={item_id}): {type(e).__name__}: {e}")
            return None

    async def get_price_info(self, item_id: int) -> Tuple[Optional[PriceInfo], int]:
        """
        価格情報を取得
        Returns: (PriceInfo, transactions)
        """
        data = await self.get_item_table(item_id)
        if not data:
            return None, 0

        try:
            # transactionsは cnt_0 + cnt_1 + cnt_2 の合計
            transactions = (
                self._parse_int(data.get("cnt_0"))
                + self._parse_int(data.get("cnt_1"))
                + self._parse_int(data.get("cnt_2"))
            )

            price_info = PriceInfo(
                item_id=item_id,
                deal_count=self._parse_int(data.get("cnt_0")),
                price_recent=self._parse_price(data.get("recent_price_0")),
                price_min=self._parse_price(data.get("min_0")),
                price_max=self._parse_price(data.get("max_0")),
                price_avg=self._parse_price(data.get("avg_0")),
                price_change_rate7=self._parse_rate(data.get("soar7_rate_0")),
                price_change_rate30=self._parse_rate(data.get("soar30_rate_0")),
                price_change7=self._parse_price(data.get("soar7_price_0")),
                price_change30=self._parse_price(data.get("soar30_price_0")),
            )
            return price_info, transactions
        except Exception as e:
            print(f"価格情報取得エラー (item_id={item_id}): {e}")
            return None, 0

    async def get_chart_data(self, item_id: int) -> List[ChartData]:
        """チャートデータを取得"""
        url = f"{self.base_url}/ch/php/get-chart-data.php"
        params = {"item_id": item_id}

        try:
            data = await self._get(url, params)
            if not data or not isinstance(data, list):
                print(f"⚠️ get_chart_data: データが取得できませんでした (item_id={item_id}): {type(data)} - {data}")
                return []

            charts = []
            for row in data:
                try:
                    chart = ChartData(
                        item_id=item_id,
                        date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
                        price1=row.get("price_01") or 0,
                        price2=row.get("price_02") or 0,
                        price3=row.get("price_03") or 0,
                        volume=row.get("volume") or 0,
                    )
                    charts.append(chart)
                except (KeyError, ValueError) as e:
                    print(f"⚠️ get_chart_data: チャートデータのパースエラー (item_id={item_id}): {e}")
                    continue

            return charts
        except Exception as e:
            print(f"❌ get_chart_data エラー (item_id={item_id}): {type(e).__name__}: {e}")
            return []

    async def get_category_name(self, category_id: int) -> Optional[str]:
        """WordPress カテゴリIDからカテゴリ名を取得（キャッシュ付き）"""
        if category_id in self._category_cache:
            return self._category_cache[category_id]

        url = f"{self.wp_api_url}/categories/{category_id}"
        params = {"_fields": "name"}

        try:
            data = await self._get(url, params)
            if data and isinstance(data, dict):
                name = data.get("name", "")
                self._category_cache[category_id] = name
                return name
            return None
        except Exception:
            return None

    async def get_category_names(self, category_ids: List[int]) -> List[str]:
        """複数のカテゴリIDからカテゴリ名リストを取得"""
        if not category_ids:
            return []

        tasks = [self.get_category_name(cat_id) for cat_id in category_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        names = []
        for result in results:
            if isinstance(result, str) and result:
                names.append(result)
        return names

    async def get_image_url(self, media_id: int) -> Optional[str]:
        """WordPress Media IDから画像URLを取得"""
        if not media_id:
            return None

        url = f"{self.wp_api_url}/media/{media_id}"
        params = {"_fields": "source_url"}

        try:
            data = await self._get(url, params)
            return data.get("source_url")
        except Exception:
            return None

    async def get_shop_stock_data(self, item_id: int) -> List[dict]:
        """ショップ在庫データを取得"""
        url = f"{self.base_url}/ch/php/get.php"
        params = {"function": "get_shop_stock_data", "item_id": item_id}

        try:
            data = await self._get(url, params)
            if data and isinstance(data, list):
                return data
            print(f"⚠️ get_shop_stock_data: データが取得できませんでした (item_id={item_id}): {type(data)} - {data}")
            return []
        except Exception as e:
            print(f"❌ get_shop_stock_data エラー (item_id={item_id}): {type(e).__name__}: {e}")
            return []

    async def get_grading_info(self, item_id: int) -> Optional[GradingInfo]:
        """
        ショップ在庫データからグレーディング情報を抽出
        item_status=2 がPSA10に対応
        """
        stock_data = await self.get_shop_stock_data(item_id)
        if not stock_data:
            return None

        # item_statusごとの在庫数を集計
        status_stock: Dict[int, int] = {}
        for item in stock_data:
            status = item.get("item_status")
            stock = item.get("stock", 0) or 0
            if status is not None:
                status_stock[status] = status_stock.get(status, 0) + stock

        # 全在庫数
        total_stock = sum(status_stock.values())

        # GradingInfoを作成
        # 現時点で判明しているマッピング:
        # item_status=2 → PSA10
        # item_status=45 → PSA9 (推定)
        grading = GradingInfo(
            item_id=item_id,
            checked_at=datetime.now(),
            grd_status_auth=0,  # 認証済み数（不明）
            grd_status1=0,
            grd_status2=0,
            grd_status3=0,
            grd_status4=0,
            grd_status5=0,
            grd_status6=0,
            grd_status7=0,
            grd_status8=0,
            grd_status9=status_stock.get(45, 0),  # item_status=45 → PSA9?
            grd_status10=status_stock.get(2, 0),  # item_status=2 → PSA10
            grd_status_all=total_stock,
        )

        return grading

    @staticmethod
    def extract_series(name: str) -> Optional[str]:
        """
        カード名からシリーズを抽出
        例: "メガリザードンYex [MC 766/742]" → "MC"
        例: "ブラッキーex [sv8a 217/187]" → "sv8a"
        """
        # パターン: [XXX 数字/数字] または [XXX]
        match = re.search(r"\[([A-Za-z0-9]+)[\s\-]", name)
        if match:
            return match.group(1)

        # パターン: [XXX] （スペースなし）
        match = re.search(r"\[([A-Za-z0-9]+)\]", name)
        if match:
            return match.group(1)

        return None

    @staticmethod
    def _parse_price(value: Optional[str]) -> int:
        """価格文字列をintに変換 (例: "199,999円" -> 199999)"""
        if not value:
            return 0
        # 数字以外を除去（マイナス記号は保持）
        cleaned = re.sub(r"[^\d\-]", "", value)
        try:
            return int(cleaned) if cleaned and cleaned != "-" else 0
        except ValueError:
            return 0

    @staticmethod
    def _parse_rate(value: Optional[str]) -> float:
        """変動率文字列をfloatに変換 (例: "-22.48%" -> -22.48)"""
        if not value:
            return 0.0
        # 数字、マイナス、ピリオド以外を除去
        cleaned = re.sub(r"[^\d\-.]", "", value)
        try:
            return float(cleaned) if cleaned and cleaned not in ["-", "."] else 0.0
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_int(value) -> int:
        """値をintに変換"""
        if value is None:
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0


async def fetch_card_details(
    client: PokecaAPIClient, wp_post: WordPressPost
) -> Tuple[Optional[CardItem], Optional[PriceInfo], List[ChartData], Optional[GradingInfo]]:
    """カードの詳細情報を一括取得"""
    # item_idを取得
    item_id = await client.get_item_id(wp_post.link)
    if not item_id:
        print(f"item_id取得失敗: {wp_post.slug}")
        return None, None, [], None

    # 並列で各種情報を取得
    (
        image_url,
        item_btn_link,
        price_result,
        chart_data,
        tags,
        grading_info,
    ) = await asyncio.gather(
        client.get_item_image_url(item_id),
        client.get_item_btn_link(item_id),
        client.get_price_info(item_id),
        client.get_chart_data(item_id),
        client.get_category_names(wp_post.categories),
        client.get_grading_info(item_id),
    )

    # price_resultはタプル (PriceInfo, transactions)
    price_info, transactions = price_result

    # カード名を決定（get-item-btn-link.phpから取得、なければWordPressから）
    name = wp_post.title
    if item_btn_link and item_btn_link.get("name"):
        name = item_btn_link["name"]

    # シリーズを抽出
    series = client.extract_series(name)

    # 画像URLが取得できなかった場合はWordPress Media APIにフォールバック
    if not image_url:
        image_url = await client.get_image_url(wp_post.featured_media)

    # カードアイテムを作成
    card = CardItem(
        wp_post_id=wp_post.id,
        slug=wp_post.slug,
        name=name,
        series=series,
        tags=tags,
        transactions=transactions,
        image_url=image_url,
    )

    # item_idをカードに設定
    card.id = item_id

    return card, price_info, chart_data, grading_info

