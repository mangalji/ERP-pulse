from django.db import migrations


FORWARD_SQL = """
-- ============================================================
-- 1. Create reusable trigger function
-- ============================================================

CREATE OR REPLACE FUNCTION navigation_generate_internal_id()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    sequence_name TEXT;
BEGIN
    IF NEW.internal_id IS NULL OR NEW.internal_id = 0 THEN
        sequence_name := TG_TABLE_NAME || '_internal_id_seq';

        EXECUTE format(
            'SELECT nextval(%L)',
            sequence_name
        )
        INTO NEW.internal_id;
    END IF;

    RETURN NEW;
END;
$$;


-- ============================================================
-- 2. TOP LEVEL TAB
-- ============================================================

ALTER TABLE dynamic_top_level_tab
    ADD COLUMN IF NOT EXISTS internal_id BIGINT;

CREATE SEQUENCE IF NOT EXISTS dynamic_top_level_tab_internal_id_seq
    AS BIGINT
    MINVALUE 1
    START WITH 1;

WITH numbered AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            ORDER BY sort_order, created_at, id
        ) AS new_internal_id
    FROM dynamic_top_level_tab
    WHERE internal_id IS NULL OR internal_id = 0
)
UPDATE dynamic_top_level_tab t
SET internal_id = numbered.new_internal_id
FROM numbered
WHERE t.id = numbered.id;

SELECT setval(
    'dynamic_top_level_tab_internal_id_seq',
    COALESCE(
        (SELECT MAX(internal_id) FROM dynamic_top_level_tab),
        0
    ),
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM dynamic_top_level_tab
            WHERE internal_id IS NOT NULL
              AND internal_id > 0
        )
        THEN true
        ELSE false
    END
);

ALTER SEQUENCE dynamic_top_level_tab_internal_id_seq
    OWNED BY dynamic_top_level_tab.internal_id;

ALTER TABLE dynamic_top_level_tab
    ALTER COLUMN internal_id SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS
    dynamic_top_level_tab_internal_id_key
ON dynamic_top_level_tab (internal_id);

DROP TRIGGER IF EXISTS
    navigation_dynamic_top_level_tab_internal_id
ON dynamic_top_level_tab;

CREATE TRIGGER navigation_dynamic_top_level_tab_internal_id
BEFORE INSERT ON dynamic_top_level_tab
FOR EACH ROW
EXECUTE FUNCTION navigation_generate_internal_id();


-- ============================================================
-- 3. LEVEL 2 TAB
-- ============================================================

ALTER TABLE dynamic_level2_tab
    ADD COLUMN IF NOT EXISTS internal_id BIGINT;

CREATE SEQUENCE IF NOT EXISTS dynamic_level2_tab_internal_id_seq
    AS BIGINT
    MINVALUE 1
    START WITH 1;

WITH numbered AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            ORDER BY sort_order, created_at, id
        ) AS new_internal_id
    FROM dynamic_level2_tab
    WHERE internal_id IS NULL OR internal_id = 0
)
UPDATE dynamic_level2_tab t
SET internal_id = numbered.new_internal_id
FROM numbered
WHERE t.id = numbered.id;

SELECT setval(
    'dynamic_level2_tab_internal_id_seq',
    COALESCE(
        (SELECT MAX(internal_id) FROM dynamic_level2_tab),
        0
    ),
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM dynamic_level2_tab
            WHERE internal_id IS NOT NULL
              AND internal_id > 0
        )
        THEN true
        ELSE false
    END
);

ALTER SEQUENCE dynamic_level2_tab_internal_id_seq
    OWNED BY dynamic_level2_tab.internal_id;

ALTER TABLE dynamic_level2_tab
    ALTER COLUMN internal_id SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS
    dynamic_level2_tab_internal_id_key
ON dynamic_level2_tab (internal_id);

DROP TRIGGER IF EXISTS
    navigation_dynamic_level2_tab_internal_id
ON dynamic_level2_tab;

CREATE TRIGGER navigation_dynamic_level2_tab_internal_id
BEFORE INSERT ON dynamic_level2_tab
FOR EACH ROW
EXECUTE FUNCTION navigation_generate_internal_id();


-- ============================================================
-- 4. LEVEL 3 TAB
-- ============================================================

ALTER TABLE dynamic_level3_tab
    ADD COLUMN IF NOT EXISTS internal_id BIGINT;

CREATE SEQUENCE IF NOT EXISTS dynamic_level3_tab_internal_id_seq
    AS BIGINT
    MINVALUE 1
    START WITH 1;

WITH numbered AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            ORDER BY sort_order, created_at, id
        ) AS new_internal_id
    FROM dynamic_level3_tab
    WHERE internal_id IS NULL OR internal_id = 0
)
UPDATE dynamic_level3_tab t
SET internal_id = numbered.new_internal_id
FROM numbered
WHERE t.id = numbered.id;

SELECT setval(
    'dynamic_level3_tab_internal_id_seq',
    COALESCE(
        (SELECT MAX(internal_id) FROM dynamic_level3_tab),
        0
    ),
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM dynamic_level3_tab
            WHERE internal_id IS NOT NULL
              AND internal_id > 0
        )
        THEN true
        ELSE false
    END
);

ALTER SEQUENCE dynamic_level3_tab_internal_id_seq
    OWNED BY dynamic_level3_tab.internal_id;

ALTER TABLE dynamic_level3_tab
    ALTER COLUMN internal_id SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS
    dynamic_level3_tab_internal_id_key
ON dynamic_level3_tab (internal_id);

DROP TRIGGER IF EXISTS
    navigation_dynamic_level3_tab_internal_id
ON dynamic_level3_tab;

CREATE TRIGGER navigation_dynamic_level3_tab_internal_id
BEFORE INSERT ON dynamic_level3_tab
FOR EACH ROW
EXECUTE FUNCTION navigation_generate_internal_id();
"""


REVERSE_SQL = """
DROP TRIGGER IF EXISTS
    navigation_dynamic_top_level_tab_internal_id
ON dynamic_top_level_tab;

DROP TRIGGER IF EXISTS
    navigation_dynamic_level2_tab_internal_id
ON dynamic_level2_tab;

DROP TRIGGER IF EXISTS
    navigation_dynamic_level3_tab_internal_id
ON dynamic_level3_tab;

DROP FUNCTION IF EXISTS navigation_generate_internal_id();

DROP SEQUENCE IF EXISTS dynamic_top_level_tab_internal_id_seq;
DROP SEQUENCE IF EXISTS dynamic_level2_tab_internal_id_seq;
DROP SEQUENCE IF EXISTS dynamic_level3_tab_internal_id_seq;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("navigation", "0010_dynamiclevel2tab_query_params_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql=FORWARD_SQL,
            reverse_sql=REVERSE_SQL,
        ),
    ]