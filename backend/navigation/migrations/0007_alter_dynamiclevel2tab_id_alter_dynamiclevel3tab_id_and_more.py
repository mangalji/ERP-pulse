# Generated manually for safe BIGINT -> UUID migration.
# This migration preserves existing navigation relationships.

import uuid

from django.db import migrations, models


TARGET_TABLES = {
    "navigation_transaction_menu",
    "navigation_transaction_menu_item",
    "dynamic_top_level_tab",
    "dynamic_level2_tab",
    "dynamic_level3_tab",
    "navigation_user_access",
}


def _get_table_fks(cursor, table_name, column_names):
    cursor.execute(
        """
        SELECT DISTINCT c.conname
        FROM pg_constraint c
        JOIN pg_class t
          ON t.oid = c.conrelid
        JOIN pg_namespace n
          ON n.oid = t.relnamespace
        JOIN pg_attribute a
          ON a.attrelid = c.conrelid
         AND a.attnum = ANY(c.conkey)
        WHERE c.contype = 'f'
          AND n.nspname = current_schema()
          AND t.relname = %s
          AND a.attname = ANY(%s);
        """,
        [table_name, list(column_names)],
    )
    return [row[0] for row in cursor.fetchall()]


def _drop_constraint(cursor, schema_editor, table_name, constraint_name):
    cursor.execute(
        f"ALTER TABLE {schema_editor.quote_name(table_name)} "
        f"DROP CONSTRAINT {schema_editor.quote_name(constraint_name)}"
    )


def _get_pk_constraint(cursor, table_name):
    cursor.execute(
        """
        SELECT c.conname
        FROM pg_constraint c
        JOIN pg_class t
          ON t.oid = c.conrelid
        JOIN pg_namespace n
          ON n.oid = t.relnamespace
        WHERE c.contype = 'p'
          AND n.nspname = current_schema()
          AND t.relname = %s;
        """,
        [table_name],
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _check_for_external_fks(cursor):
    cursor.execute(
        """
        SELECT
            child.relname AS child_table,
            c.conname AS constraint_name,
            parent.relname AS parent_table
        FROM pg_constraint c
        JOIN pg_class child
          ON child.oid = c.conrelid
        JOIN pg_namespace child_ns
          ON child_ns.oid = child.relnamespace
        JOIN pg_class parent
          ON parent.oid = c.confrelid
        JOIN pg_namespace parent_ns
          ON parent_ns.oid = parent.relnamespace
        WHERE c.contype = 'f'
          AND child_ns.nspname = current_schema()
          AND parent_ns.nspname = current_schema()
          AND parent.relname = ANY(%s)
          AND NOT (
              child.relname = ANY(%s)
          );
        """,
        [list(TARGET_TABLES), list(TARGET_TABLES)],
    )

    rows = cursor.fetchall()

    if rows:
        details = ", ".join(
            f"{child}.{constraint} -> {parent}"
            for child, constraint, parent in rows
        )
        raise RuntimeError(
            "Navigation UUID migration stopped because external foreign keys "
            f"reference navigation tables: {details}"
        )


def _build_id_map(cursor, table_name):
    cursor.execute(
        f"SELECT id FROM {table_name} ORDER BY id"
    )
    rows = cursor.fetchall()

    mapping = {}

    for (old_id,) in rows:
        mapping[old_id] = uuid.uuid4()

    return mapping


def _populate_uuid_ids(cursor, table_name, mapping):
    values = [
        (new_id, old_id)
        for old_id, new_id in mapping.items()
    ]

    if not values:
        return

    cursor.executemany(
        f"""
        UPDATE {table_name}
        SET id_uuid = %s
        WHERE id = %s
        """,
        values,
    )


def _populate_fk_column(cursor, table_name, old_column, new_column, mapping):
    cursor.execute(
        f"""
        SELECT {old_column}
        FROM {table_name}
        WHERE {old_column} IS NOT NULL
        """
    )

    old_values = [row[0] for row in cursor.fetchall()]

    missing = [value for value in old_values if value not in mapping]

    if missing:
        raise RuntimeError(
            f"Missing UUID mapping for {table_name}.{old_column}: {missing}"
        )

    for old_value in old_values:
        cursor.execute(
            f"""
            UPDATE {table_name}
            SET {new_column} = %s
            WHERE {old_column} = %s
            """,
            [mapping[old_value], old_value],
        )

def _forwards(apps, schema_editor):
    connection = schema_editor.connection

    if connection.vendor != "postgresql":
        raise RuntimeError(
            "This navigation UUID migration requires PostgreSQL."
        )

    with connection.cursor() as cursor:
        # =============================================================
        # IMPORTANT:
        # This is a recovery/continuation migration.
        #
        # The original migration already ran partially:
        # - UUID shadow columns already exist.
        # - UUID values are already populated.
        # - Some old BIGINT columns are already dropped.
        # - Old PK/FK constraints have already been removed.
        #
        # Therefore DO NOT recreate UUID columns or UUID mappings here.
        # =============================================================

        # -------------------------------------------------------------
        # 1. Remove the dependent view before replacing
        #    dynamic_top_level_tab.id
        # -------------------------------------------------------------
        cursor.execute(
            """
            DROP VIEW IF EXISTS active_tabs;
            """
        )

        # -------------------------------------------------------------
        # 2. Finish dropping remaining old BIGINT columns
        # -------------------------------------------------------------

        # navigation_transaction_menu
        # id is already gone; id_uuid is the final ID column.

        # navigation_transaction_menu_item
        # id/menu_id/parent_item_id are already gone;
        # id_uuid/menu_uuid/parent_item_uuid remain.

        # dynamic_top_level_tab
        cursor.execute(
            """
            ALTER TABLE dynamic_top_level_tab
            DROP COLUMN IF EXISTS id;
            """
        )

        # dynamic_level2_tab
        cursor.execute(
            """
            ALTER TABLE dynamic_level2_tab
            DROP COLUMN IF EXISTS id,
            DROP COLUMN IF EXISTS parent_tab_id;
            """
        )

        # dynamic_level3_tab
        cursor.execute(
            """
            ALTER TABLE dynamic_level3_tab
            DROP COLUMN IF EXISTS id,
            DROP COLUMN IF EXISTS parent_tab_id;
            """
        )

        # navigation_user_access
        cursor.execute(
            """
            ALTER TABLE navigation_user_access
            DROP COLUMN IF EXISTS id,
            DROP COLUMN IF EXISTS top_level_tab_id,
            DROP COLUMN IF EXISTS level2_tab_id,
            DROP COLUMN IF EXISTS level3_tab_id;
            """
        )

        # -------------------------------------------------------------
        # 3. Rename UUID shadow columns to final Django column names
        # -------------------------------------------------------------

        # navigation_transaction_menu
        cursor.execute(
            """
            ALTER TABLE navigation_transaction_menu
            RENAME COLUMN id_uuid TO id;
            """
        )

        # navigation_transaction_menu_item
        cursor.execute(
            """
            ALTER TABLE navigation_transaction_menu_item
            RENAME COLUMN id_uuid TO id;

            ALTER TABLE navigation_transaction_menu_item
            RENAME COLUMN menu_uuid TO menu_id;

            ALTER TABLE navigation_transaction_menu_item
            RENAME COLUMN parent_item_uuid TO parent_item_id;
            """
        )

        # dynamic_top_level_tab
        cursor.execute(
            """
            ALTER TABLE dynamic_top_level_tab
            RENAME COLUMN id_uuid TO id;
            """
        )

        # dynamic_level2_tab
        cursor.execute(
            """
            ALTER TABLE dynamic_level2_tab
            RENAME COLUMN id_uuid TO id;

            ALTER TABLE dynamic_level2_tab
            RENAME COLUMN parent_tab_uuid TO parent_tab_id;
            """
        )

        # dynamic_level3_tab
        cursor.execute(
            """
            ALTER TABLE dynamic_level3_tab
            RENAME COLUMN id_uuid TO id;

            ALTER TABLE dynamic_level3_tab
            RENAME COLUMN parent_tab_uuid TO parent_tab_id;
            """
        )

        # navigation_user_access
        cursor.execute(
            """
            ALTER TABLE navigation_user_access
            RENAME COLUMN id_uuid TO id;

            ALTER TABLE navigation_user_access
            RENAME COLUMN top_level_tab_uuid TO top_level_tab_id;

            ALTER TABLE navigation_user_access
            RENAME COLUMN level2_tab_uuid TO level2_tab_id;

            ALTER TABLE navigation_user_access
            RENAME COLUMN level3_tab_uuid TO level3_tab_id;
            """
        )

        # -------------------------------------------------------------
        # 4. Ensure UUID columns are NOT NULL
        # -------------------------------------------------------------
        required_uuid_columns = [
            ("navigation_transaction_menu", "id"),
            ("navigation_transaction_menu_item", "id"),
            ("navigation_transaction_menu_item", "menu_id"),
            ("dynamic_top_level_tab", "id"),
            ("dynamic_level2_tab", "id"),
            ("dynamic_level2_tab", "parent_tab_id"),
            ("dynamic_level3_tab", "id"),
            ("dynamic_level3_tab", "parent_tab_id"),
            ("navigation_user_access", "id"),
        ]

        for table_name, column_name in required_uuid_columns:
            cursor.execute(
                f"""
                ALTER TABLE {table_name}
                ALTER COLUMN {column_name}
                SET NOT NULL;
                """
            )

        # -------------------------------------------------------------
        # 5. Recreate primary keys
        # -------------------------------------------------------------
        target_tables = [
            "navigation_transaction_menu",
            "navigation_transaction_menu_item",
            "dynamic_top_level_tab",
            "dynamic_level2_tab",
            "dynamic_level3_tab",
            "navigation_user_access",
        ]

        for table_name in target_tables:
            cursor.execute(
                f"""
                ALTER TABLE {table_name}
                ADD PRIMARY KEY (id);
                """
            )

        # -------------------------------------------------------------
        # 6. Recreate foreign keys
        # -------------------------------------------------------------

        cursor.execute(
            """
            ALTER TABLE navigation_transaction_menu_item
            ADD CONSTRAINT navigation_transaction_menu_item_menu_fk
            FOREIGN KEY (menu_id)
            REFERENCES navigation_transaction_menu(id)
            ON DELETE CASCADE;
            """
        )

        cursor.execute(
            """
            ALTER TABLE navigation_transaction_menu_item
            ADD CONSTRAINT navigation_transaction_menu_item_parent_fk
            FOREIGN KEY (parent_item_id)
            REFERENCES navigation_transaction_menu_item(id)
            ON DELETE CASCADE;
            """
        )

        cursor.execute(
            """
            ALTER TABLE dynamic_level2_tab
            ADD CONSTRAINT dynamic_level2_tab_parent_fk
            FOREIGN KEY (parent_tab_id)
            REFERENCES dynamic_top_level_tab(id)
            ON DELETE CASCADE;
            """
        )

        cursor.execute(
            """
            ALTER TABLE dynamic_level3_tab
            ADD CONSTRAINT dynamic_level3_tab_parent_fk
            FOREIGN KEY (parent_tab_id)
            REFERENCES dynamic_level2_tab(id)
            ON DELETE CASCADE;
            """
        )

        cursor.execute(
            """
            ALTER TABLE navigation_user_access
            ADD CONSTRAINT navigation_user_access_top_fk
            FOREIGN KEY (top_level_tab_id)
            REFERENCES dynamic_top_level_tab(id)
            ON DELETE CASCADE;
            """
        )

        cursor.execute(
            """
            ALTER TABLE navigation_user_access
            ADD CONSTRAINT navigation_user_access_l2_fk
            FOREIGN KEY (level2_tab_id)
            REFERENCES dynamic_level2_tab(id)
            ON DELETE CASCADE;
            """
        )

        cursor.execute(
            """
            ALTER TABLE navigation_user_access
            ADD CONSTRAINT navigation_user_access_l3_fk
            FOREIGN KEY (level3_tab_id)
            REFERENCES dynamic_level3_tab(id)
            ON DELETE CASCADE;
            """
        )

        # -------------------------------------------------------------
        # 7. Recreate indexes
        # -------------------------------------------------------------

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS nav_tx_item_tree_idx
            ON navigation_transaction_menu_item
            (menu_id, parent_item_id, is_active, sort_order);
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS nav_tx_item_active_order_idx
            ON navigation_transaction_menu_item
            (is_active, sort_order);
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS dyn_l2_parent_order_idx
            ON dynamic_level2_tab
            (parent_tab_id, is_active, sort_order);
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS dyn_l3_parent_order_idx
            ON dynamic_level3_tab
            (parent_tab_id, is_active, sort_order);
            """
        )

        # -------------------------------------------------------------
        # 8. Recreate NavigationUserAccess constraint
        # -------------------------------------------------------------

        cursor.execute(
            """
            ALTER TABLE navigation_user_access
            ADD CONSTRAINT nav_user_access_exactly_one_level
            CHECK (
                (
                    top_level_tab_id IS NOT NULL
                    AND level2_tab_id IS NULL
                    AND level3_tab_id IS NULL
                )
                OR
                (
                    top_level_tab_id IS NULL
                    AND level2_tab_id IS NOT NULL
                    AND level3_tab_id IS NULL
                )
                OR
                (
                    top_level_tab_id IS NULL
                    AND level2_tab_id IS NULL
                    AND level3_tab_id IS NOT NULL
                )
            );
            """
        )

        # -------------------------------------------------------------
        # 9. Recreate unique user-navigation indexes
        # -------------------------------------------------------------

        cursor.execute(
            """
            CREATE UNIQUE INDEX nav_user_access_user_top_unique
            ON navigation_user_access (user_id, top_level_tab_id)
            WHERE top_level_tab_id IS NOT NULL;
            """
        )

        cursor.execute(
            """
            CREATE UNIQUE INDEX nav_user_access_user_l2_unique
            ON navigation_user_access (user_id, level2_tab_id)
            WHERE level2_tab_id IS NOT NULL;
            """
        )

        cursor.execute(
            """
            CREATE UNIQUE INDEX nav_user_access_user_l3_unique
            ON navigation_user_access (user_id, level3_tab_id)
            WHERE level3_tab_id IS NOT NULL;
            """
        )

        # -------------------------------------------------------------
        # 10. Restore UUID defaults
        # -------------------------------------------------------------

        cursor.execute(
            """
            ALTER TABLE navigation_transaction_menu
            ALTER COLUMN id SET DEFAULT gen_random_uuid();
            """
        )

        cursor.execute(
            """
            ALTER TABLE navigation_transaction_menu_item
            ALTER COLUMN id SET DEFAULT gen_random_uuid();
            """
        )

        cursor.execute(
            """
            ALTER TABLE dynamic_top_level_tab
            ALTER COLUMN id SET DEFAULT gen_random_uuid();
            """
        )

        cursor.execute(
            """
            ALTER TABLE dynamic_level2_tab
            ALTER COLUMN id SET DEFAULT gen_random_uuid();
            """
        )

        cursor.execute(
            """
            ALTER TABLE dynamic_level3_tab
            ALTER COLUMN id SET DEFAULT gen_random_uuid();
            """
        )

        cursor.execute(
            """
            ALTER TABLE navigation_user_access
            ALTER COLUMN id SET DEFAULT gen_random_uuid();
            """
        )

        # -------------------------------------------------------------
        # 11. Recreate the active_tabs view
        # -------------------------------------------------------------
        cursor.execute(
            """
            CREATE VIEW active_tabs AS
            SELECT
                id,
                name,
                key,
                route,
                query_params,
                feature_code,
                icon,
                sort_order,
                is_active,
                created_at,
                updated_at
            FROM dynamic_top_level_tab
            WHERE is_active = true;
            """
        )

def _backwards(apps, schema_editor):
    raise RuntimeError(
        "Navigation UUID migration is irreversible because the original "
        "BIGINT -> UUID mappings are intentionally not retained."
    )


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("navigation", "0006_dynamiclevel3tab_and_more"),
    ]

    operations = [
        migrations.RunPython(
            _forwards,
            _backwards,
        ),

        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="dynamiclevel2tab",
                    name="id",
                    field=models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                migrations.AlterField(
                    model_name="dynamiclevel3tab",
                    name="id",
                    field=models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                migrations.AlterField(
                    model_name="dynamictopleveltab",
                    name="id",
                    field=models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                migrations.AlterField(
                    model_name="navigationuseraccess",
                    name="id",
                    field=models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                migrations.AlterField(
                    model_name="transactionmenu",
                    name="id",
                    field=models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                migrations.AlterField(
                    model_name="transactionmenuitem",
                    name="id",
                    field=models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
            ],
        ),
    ]