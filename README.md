# Pokemon Card Scraping Batch

pokeca-chart.com からポケモンカード情報をスクレイピングし、PostgreSQLデータベースに保存するバッチ処理ツールです。

## 機能

- 📥 WordPress REST APIからカード一覧を自動取得
- 💰 価格情報（現在価格、最高/最低/平均、変動率、取引数）を取得
- 📈 日次チャートデータを取得
- 🏷️ カード名からシリーズ情報を自動抽出
- 🏪 ショップ在庫からPSAグレーディング情報を取得
- 🗄️ PostgreSQLへの高速バッチ保存
- 🔄 並列処理による高速スクレイピング
- 📊 進捗バーと統計情報の表示

## 必要条件

- Python 3.11以上
- PostgreSQL 14以上

## セットアップ

### 1. リポジトリをクローン

```bash
git clone <repository-url>
cd pokemon-portfolio-minpoke-batch
```

### 2. 仮想環境を作成

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. 依存関係をインストール

```bash
pip install -r requirements.txt
```

### 4. 環境変数を設定

```bash
cp env.example .env
```

`.env` ファイルを編集し、データベース接続情報を設定：

```
DATABASE_URL=postgresql://user:password@localhost:5432/pokemon_db
```

### 5. データベーステーブルを作成

PostgreSQLに接続して以下のSQLを実行：

```sql
-- items2テーブル
CREATE TABLE public.items2 (
  id bigserial NOT NULL,
  name text NOT NULL,
  series text NULL,
  tags text[] NULL,
  transactions integer NULL DEFAULT 0,
  views integer NULL DEFAULT 0,
  image_url text NULL,
  pv integer NULL DEFAULT 0,
  created_at timestamp with time zone NULL DEFAULT now(),
  updated_at timestamp with time zone NULL DEFAULT now(),
  CONSTRAINT items2_pkey PRIMARY KEY (id)
);

CREATE INDEX idx_items2_updated_at ON public.items2 USING btree (updated_at);

-- price_infos2テーブル
CREATE TABLE public.price_infos2 (
  id bigserial NOT NULL,
  item_id bigint NOT NULL,
  deal_count integer NULL DEFAULT 0,
  price_recent integer NULL DEFAULT 0,
  price_min integer NULL DEFAULT 0,
  price_max integer NULL DEFAULT 0,
  price_avg integer NULL DEFAULT 0,
  price_change_rate7 double precision NULL DEFAULT 0,
  price_change_rate30 double precision NULL DEFAULT 0,
  price_change7 integer NULL DEFAULT 0,
  price_change30 integer NULL DEFAULT 0,
  created_at timestamp with time zone NULL DEFAULT now(),
  CONSTRAINT price_infos2_pkey PRIMARY KEY (id),
  CONSTRAINT price_infos2_item_id_key UNIQUE (item_id),
  CONSTRAINT price_infos2_item_id_fkey FOREIGN KEY (item_id) REFERENCES items2 (id) ON DELETE CASCADE
);

CREATE INDEX idx_price_infos2_item_id ON public.price_infos2 USING btree (item_id);

-- charts2テーブル
CREATE TABLE public.charts2 (
  id bigserial NOT NULL,
  item_id bigint NOT NULL,
  date date NOT NULL,
  price1 integer NULL DEFAULT 0,
  price2 integer NULL DEFAULT 0,
  price3 integer NULL DEFAULT 0,
  volume integer NULL DEFAULT 0,
  created_at timestamp with time zone NULL DEFAULT now(),
  CONSTRAINT charts2_pkey PRIMARY KEY (id),
  CONSTRAINT charts2_item_id_date_key UNIQUE (item_id, date),
  CONSTRAINT charts2_item_id_fkey FOREIGN KEY (item_id) REFERENCES items2 (id) ON DELETE CASCADE
);

CREATE INDEX idx_charts2_item_id ON public.charts2 USING btree (item_id);
CREATE INDEX idx_charts2_date ON public.charts2 USING btree (date);

-- gradings2テーブル
CREATE TABLE public.gradings2 (
  id bigserial NOT NULL,
  item_id bigint NOT NULL,
  checked_at timestamp with time zone NULL,
  grd_status_auth integer NULL DEFAULT 0,
  grd_status1 integer NULL DEFAULT 0,
  grd_status2 integer NULL DEFAULT 0,
  grd_status3 integer NULL DEFAULT 0,
  grd_status4 integer NULL DEFAULT 0,
  grd_status5 integer NULL DEFAULT 0,
  grd_status6 integer NULL DEFAULT 0,
  grd_status7 integer NULL DEFAULT 0,
  grd_status8 integer NULL DEFAULT 0,
  grd_status9 integer NULL DEFAULT 0,
  grd_status10 integer NULL DEFAULT 0,
  grd_status_all integer NULL DEFAULT 0,
  grd_url text NULL,
  created_at timestamp with time zone NULL DEFAULT now(),
  CONSTRAINT gradings2_pkey PRIMARY KEY (id),
  CONSTRAINT gradings2_item_id_key UNIQUE (item_id),
  CONSTRAINT gradings2_item_id_fkey FOREIGN KEY (item_id) REFERENCES items2 (id) ON DELETE CASCADE
);

CREATE INDEX idx_gradings2_item_id ON public.gradings2 USING btree (item_id);
```

## 使用方法

### バッチ処理を実行

```bash
python main.py
```

### 出力例

```
============================================================
🎴 Pokemon Card Scraping Batch
⏰ 開始時刻: 2025-12-28 15:30:00
============================================================

📥 WordPress APIからカード一覧を取得中...
取得済み: 100 件 (ページ 1)
取得済み: 200 件 (ページ 2)
...
✅ 取得完了: 5000 件のカード

🔄 カードデータを処理中...
処理中: 100%|████████████████████| 5000/5000 [05:30<00:00, 15.15cards/s]

============================================================
📊 処理結果
============================================================
処理カード数: 4950
価格情報: 4950
チャートデータ: 34650
グレーディング情報: 4950

📈 データベース統計:
  items2: 4,950 件
  price_infos2: 4,950 件
  charts2: 34,650 件
  gradings2: 4,950 件

⏱️ 処理時間: 330.00 秒
📈 処理速度: 15.15 cards/sec

✅ バッチ処理完了!
⏰ 終了時刻: 2025-12-28 15:35:30
```

## 設定オプション

| 環境変数 | デフォルト | 説明 |
|---------|-----------|------|
| `DATABASE_URL` | - | PostgreSQL接続URL（必須） |
| `CONCURRENT_REQUESTS` | 10 | 同時リクエスト数 |
| `REQUEST_DELAY` | 0.1 | リクエスト間の遅延（秒） |
| `BATCH_SIZE` | 100 | DBバッチ処理サイズ |
| `WP_PER_PAGE` | 100 | WordPress APIの1ページあたり件数 |
| `MAX_RETRIES` | 3 | 最大リトライ回数 |
| `REQUEST_TIMEOUT` | 30 | リクエストタイムアウト（秒） |

## プロジェクト構造

```
pokemon-portfolio-minpoke-batch/
├── main.py              # メインエントリーポイント
├── requirements.txt     # 依存関係
├── env.example          # 環境変数サンプル
├── README.md            # このファイル
└── src/
    ├── __init__.py
    ├── config.py        # 設定
    ├── models.py        # データモデル
    ├── api_client.py    # APIクライアント
    └── database.py      # データベース操作
```

## 取得データの詳細

### items2テーブル
- ✅ name: カード名
- ✅ series: シリーズ（カード名から自動抽出）
- ✅ tags: タグ（WordPressカテゴリ）
- ✅ transactions: 取引数（cnt_0 + cnt_1 + cnt_2）
- ✅ image_url: 画像URL
- ❌ views: API無し
- ❌ pv: API無し（セッターのみ）

### price_infos2テーブル
- ✅ 全カラム取得可能（100%）

### charts2テーブル
- ✅ 全カラム取得可能（100%）
- price1: 美品の平均価格
- price2: キズありの平均価格
- price3: PSA10の平均価格

### gradings2テーブル
- ✅ grd_status9: PSA9在庫数（item_status=45）
- ✅ grd_status10: PSA10在庫数（item_status=2）
- ✅ grd_status_all: 全在庫合計
- ❌ grd_status1-8: API無し

## 注意事項

- スクレイピング時はサーバーへの負荷を考慮し、`REQUEST_DELAY` を適切に設定してください
- 大量のデータを取得する場合は `CONCURRENT_REQUESTS` を下げることをお勧めします
- 定期実行する場合は cron や systemd timer の使用を検討してください

## ライセンス

MIT License

