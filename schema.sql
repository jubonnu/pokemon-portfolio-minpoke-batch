-- update_updated_at_column関数を作成
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- items2テーブル
CREATE TABLE IF NOT EXISTS public.items2 (
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
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_items2_updated_at ON public.items2 USING btree (updated_at) TABLESPACE pg_default;

-- トリガーが既に存在する場合は削除してから再作成
DROP TRIGGER IF EXISTS update_items2_updated_at ON public.items2;
CREATE TRIGGER update_items2_updated_at BEFORE
UPDATE ON items2 FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- price_infos2テーブル
CREATE TABLE IF NOT EXISTS public.price_infos2 (
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
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_price_infos2_item_id ON public.price_infos2 USING btree (item_id) TABLESPACE pg_default;

-- charts2テーブル
CREATE TABLE IF NOT EXISTS public.charts2 (
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
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_charts2_item_id ON public.charts2 USING btree (item_id) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_charts2_date ON public.charts2 USING btree (date) TABLESPACE pg_default;

-- gradings2テーブル
CREATE TABLE IF NOT EXISTS public.gradings2 (
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
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_gradings2_item_id ON public.gradings2 USING btree (item_id) TABLESPACE pg_default;

