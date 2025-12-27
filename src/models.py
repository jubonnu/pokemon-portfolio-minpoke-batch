"""データモデル定義"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List


@dataclass
class CardItem:
    """カードアイテム"""

    id: Optional[int] = None  # DB上のID
    wp_post_id: int = 0  # WordPress post ID
    slug: str = ""
    name: str = ""
    series: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    transactions: int = 0
    views: int = 0
    image_url: Optional[str] = None
    pv: int = 0


@dataclass
class PriceInfo:
    """価格情報"""

    item_id: int
    deal_count: int = 0
    price_recent: int = 0
    price_min: int = 0
    price_max: int = 0
    price_avg: int = 0
    price_change_rate7: float = 0.0
    price_change_rate30: float = 0.0
    price_change7: int = 0
    price_change30: int = 0


@dataclass
class ChartData:
    """チャートデータ"""

    item_id: int
    date: date
    price1: int = 0
    price2: int = 0
    price3: int = 0
    volume: int = 0


@dataclass
class GradingInfo:
    """グレーディング情報"""

    item_id: int
    checked_at: Optional[datetime] = None
    grd_status_auth: int = 0
    grd_status1: int = 0
    grd_status2: int = 0
    grd_status3: int = 0
    grd_status4: int = 0
    grd_status5: int = 0
    grd_status6: int = 0
    grd_status7: int = 0
    grd_status8: int = 0
    grd_status9: int = 0
    grd_status10: int = 0
    grd_status_all: int = 0
    grd_url: Optional[str] = None


@dataclass
class WordPressPost:
    """WordPress投稿データ"""

    id: int  # WordPress post ID
    slug: str
    title: str
    link: str
    featured_media: int
    categories: List[int] = field(default_factory=list)

