# Generated manually for BIGINT -> UUID migration.
#
# Converts existing navigation primary keys and foreign keys from
# BIGINT to UUID while preserving all existing data and relationships.
#
# PostgreSQL only.
# Irreversible by design.

import uuid

from django.db import migrations, models


TARGET_TABLES = (
    "navigation_transaction_menu",
    "navigation_transaction_menu_item",
    "dynamic_top_level_tab",
    "dynamic_level2_tab",
    "dynamic_level3_tab",
    "navigation_user_access",
)


def _pk_constraint(cursor, table_name):
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


def _fk_constraints(cursor, table_name):
    cursor.execute(
        """
        SELECT DISTINCT c.conname
        FROM pg_constraint c
        JOIN pg_class t
          ON t.oid = c.conrelid
        JOIN pg_namespace n
          ON n.oid = t.relnamespace
        WHERE c.contype = 'f'
          AND n.nspname = current_schema()
          AND t.relname = %s;
        """,
        [table_name],
    )
    return [row[0] for row in cursor.fetchall()]


def _drop_constraint(cursor, schema_editor, table_name, constraint_name):
    cursor.execute(
        f"""
        ALTER TABLE {schema_editor.quote_name(table_name)}
        DROP CONSTRAINT {schema_editor.quote_name(constraint_name)}
        """
    )


def _build_mapping(cursor, table_name):
    cursor.execute(
        f"""
        SELECT id
        FROM {table_name}
        ORDER BY id
        """
    )

    return {
        old_id: uuid.uuid4()
        for (old_id,) in cursor.fetchall()
    }


def _populate_ids(cursor, table_name, mapping):
    if not mapping:
        return

    rows = [
        (new_id, old_id)
        for old_id, new_id in mapping.items()
    ]

    cursor.executemany(
        f"""
        UPDATE {table_name}
        SET id_uuid = %s
        WHERE id = %s
        """,
        rows,
    )


def _populate_fk(
    cursor,
    table_name,
    old_column,
    new_column,
    mapping,
):
    cursor.execute(
        f"""
        SELECT {old_column}
        FROM {table_name}
        WHERE {old_column} IS NOT NULL
        """
    )

    values = [row[0] for row in cursor.fetchall()]

    missing = [
        value
        for value in values
        if value not in mapping
    ]

    if missing:
        raise RuntimeError(
            f"Missing UUID mapping for "
            f"{table_name}.{old_column}: {missing}"
        )

    cursor.executemany(
        f"""
        UPDATE {table_name}
        SET {new_column} = %s
        WHERE {old_column} = %s
        """,
        [
            (mapping[value], value)
            for value in set(values)
        ],
    )


def _forwards(apps, schema_editor):
    connection = schema_editor.connection

    if connection.vendor != "postgresql":
        raise RuntimeError(
            "Navigation UUID migration requires PostgreSQL."
        )

    with connection.cursor() as cursor:

        # ---------------------------------------------------------
        # 1. Create temporary UUID columns
        # ---------------------------------------------------------

        cursor.execute(
            """
            ALTER TABLE navigation_transaction_menu
            ADD COLUMN id_uuid uuid;
            """
        )

        cursor.execute(
            """
            ALTER TABLE navigation_transaction_menu_item
            ADD COLUMN id_uuid uuid,
            ADD COLUMN menu_uuid uuid,
            ADD COLUMN parent_item_uuid uuid;
            """
        )

        cursor.execute(
            """
            ALTER TABLE dynamic_top_level_tab
            ADD COLUMN id_uuid uuid;
            """
        )

        cursor.execute(
            """
            ALTER TABLE dynamic_level2_tab
            ADD COLUMN id_uuid uuid,
            ADD COLUMN parent_tab_uuid uuid;
            """
        )

        cursor.execute(
            """
            ALTER TABLE dynamic_level3_tab
            ADD COLUMN id_uuid uuid,
            ADD COLUMN parent_tab_uuid uuid;
            """
        )

        cursor.execute(
            """
            ALTER TABLE navigation_user_access
            ADD COLUMN id_uuid uuid,
            ADD COLUMN top_level_tab_uuid uuid,
            ADD COLUMN level2_tab_uuid uuid,
            ADD COLUMN level3_tab_uuid uuid;
            """
        )

        # ---------------------------------------------------------
        # 2. Build stable BIGINT -> UUID mappings
        # ---------------------------------------------------------

        transaction_menu_map = _build_mapping(
            cursor,
            "navigation_transaction_menu",
        )

        transaction_menu_item_map = _build_mapping(
            cursor,
            "navigation_transaction_menu_item",
        )

        top_level_map = _build_mapping(
            cursor,
            "dynamic_top_level_tab",
        )

        level2_map = _build_mapping(
            cursor,
            "dynamic_level2_tab",
        )

        level3_map = _build_mapping(
            cursor,
            "dynamic_level3_tab",
        )

        user_access_map = _build_mapping(
            cursor,
            "navigation_user_access",
        )

        # ---------------------------------------------------------
        # 3. Populate UUID primary-key columns
        # ---------------------------------------------------------

        _populate_ids(
            cursor,
            "navigation_transaction_menu",
            transaction_menu_map,
        )

        _populate_ids(
            cursor,
            "navigation_transaction_menu_item",
            transaction_menu_item_map,
        )

        _populate_ids(
            cursor,
            "dynamic_top_level_tab",
            top_level_map,
        )

        _populate_ids(
            cursor,
            "dynamic_level2_tab",
            level2_map,
        )

        _populate_ids(
            cursor,
            "dynamic_level3_tab",
            level3_map,
        )

        _populate_ids(
            cursor,
            "navigation_user_access",
            user_access_map,
        )

        # ---------------------------------------------------------
        # 4. Populate UUID foreign-key columns
        # ---------------------------------------------------------

        _populate_fk(
            cursor,
            "navigation_transaction_menu_item",
            "menu_id",
            "menu_uuid",
            transaction_menu_map,
        )

        _populate_fk(
            cursor,
            "navigation_transaction_menu_item",
            "parent_item_id",
            "parent_item_uuid",
            transaction_menu_item_map,
        )

        _populate_fk(
            cursor,
            "dynamic_level2_tab",
            "parent_tab_id",
            "parent_tab_uuid",
            top_level_map,
        )

        _populate_fk(
            cursor,
            "dynamic_level3_tab",
            "parent_tab_id",
            "parent_tab_uuid",
            level2_map,
        )

        _populate_fk(
            cursor,
            "navigation_user_access",
            "top_level_tab_id",
            "top_level_tab_uuid",
            top_level_map,
        )

        _populate_fk(
            cursor,
            "navigation_user_access",
            "level2_tab_id",
            "level2_tab_uuid",
            level2_map,
        )

        _populate_fk(
            cursor,
            "navigation_user_access",
            "level3_tab_id",
            "level3_tab_uuid",
            level3_map,
        )

        # ---------------------------------------------------------
        # 5. Validate every UUID mapping before destructive changes
        # ---------------------------------------------------------

        validation_columns = (
            (
                "navigation_transaction_menu",
                "id_uuid",
            ),
            (
                "navigation_transaction_menu_item",
                "id_uuid",
            ),
            (
                "navigation_transaction_menu_item",
                "menu_uuid",
            ),
            (
                "dynamic_top_level_tab",
                "id_uuid",
            ),
            (
                "dynamic_level2_tab",
                "id_uuid",
            ),
            (
                "dynamic_level2_tab",
                "parent_tab_uuid",
            ),
            (
                "dynamic_level3_tab",
                "id_uuid",
            ),
            (
                "dynamic_level3_tab",
                "parent_tab_uuid",
            ),
            (
                "navigation_user_access",
                "id_uuid",
            ),
        )

        for table_name, column_name in validation_columns:
            cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM {table_name}
                WHERE {column_name} IS NULL
                """
            )

            count = cursor.fetchone()[0]

            if count:
                raise RuntimeError(
                    f"UUID migration validation failed: "
                    f"{table_name}.{column_name} "
                    f"contains {count} NULL values."
                )

        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE;")

        # ---------------------------------------------------------
        # 6. Drop existing foreign-key constraints FIRST
        # ---------------------------------------------------------

        for table_name in TARGET_TABLES:
            for constraint_name in _fk_constraints(
                cursor,
                table_name,
            ):
                _drop_constraint(
                    cursor,
                    schema_editor,
                    table_name,
                    constraint_name,
                )

        # ---------------------------------------------------------
        # 7. Drop existing primary-key constraints
        # ---------------------------------------------------------

        for table_name in TARGET_TABLES:
            constraint_name = _pk_constraint(
                cursor,
                table_name,
            )

            if constraint_name:
                _drop_constraint(
                    cursor,
                    schema_editor,
                    table_name,
                    constraint_name,
                )

        # ---------------------------------------------------------
        # 8. Drop old BIGINT columns
        # ---------------------------------------------------------

        cursor.execute(
            """
            ALTER TABLE navigation_transaction_menu
            DROP COLUMN id;
            """
        )

        cursor.execute(
            """
            ALTER TABLE navigation_transaction_menu_item
            DROP COLUMN id,
            DROP COLUMN menu_id,
            DROP COLUMN parent_item_id;
            """
        )

        cursor.execute(
            """
            ALTER TABLE dynamic_top_level_tab
            DROP COLUMN id;
            """
        )

        cursor.execute(
            """
            ALTER TABLE dynamic_level2_tab
            DROP COLUMN id,
            DROP COLUMN parent_tab_id;
            """
        )

        cursor.execute(
            """
            ALTER TABLE dynamic_level3_tab
            DROP COLUMN id,
            DROP COLUMN parent_tab_id;
            """
        )

        cursor.execute(
            """
            ALTER TABLE navigation_user_access
            DROP COLUMN id,
            DROP COLUMN top_level_tab_id,
            DROP COLUMN level2_tab_id,
            DROP COLUMN level3_tab_id;
            """
        )

        # ---------------------------------------------------------
        # 9. Rename UUID columns to Django's final column names
        # ---------------------------------------------------------

        cursor.execute(
            """
            ALTER TABLE navigation_transaction_menu
            RENAME COLUMN id_uuid TO id;
            """
        )

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

        cursor.execute(
            """
            ALTER TABLE dynamic_top_level_tab
            RENAME COLUMN id_uuid TO id;
            """
        )

        cursor.execute(
            """
            ALTER TABLE dynamic_level2_tab
            RENAME COLUMN id_uuid TO id;

            ALTER TABLE dynamic_level2_tab
            RENAME COLUMN parent_tab_uuid TO parent_tab_id;
            """
        )

        cursor.execute(
            """
            ALTER TABLE dynamic_level3_tab
            RENAME COLUMN id_uuid TO id;

            ALTER TABLE dynamic_level3_tab
            RENAME COLUMN parent_tab_uuid TO parent_tab_id;
            """
        )

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

        # ---------------------------------------------------------
        # 10. Set required columns NOT NULL
        # ---------------------------------------------------------

        required_columns = (
            ("navigation_transaction_menu", "id"),
            ("navigation_transaction_menu_item", "id"),
            ("navigation_transaction_menu_item", "menu_id"),
            ("dynamic_top_level_tab", "id"),
            ("dynamic_level2_tab", "id"),
            ("dynamic_level2_tab", "parent_tab_id"),
            ("dynamic_level3_tab", "id"),
            ("dynamic_level3_tab", "parent_tab_id"),
            ("navigation_user_access", "id"),
        )

        for table_name, column_name in required_columns:
            cursor.execute(
                f"""
                ALTER TABLE {table_name}
                ALTER COLUMN {column_name}
                SET NOT NULL;
                """
            )

        # ---------------------------------------------------------
        # 11. Recreate primary keys
        # ---------------------------------------------------------

        for table_name in TARGET_TABLES:
            cursor.execute(
                f"""
                ALTER TABLE {table_name}
                ADD PRIMARY KEY (id);
                """
            )

        # ---------------------------------------------------------
        # 12. Recreate foreign keys
        # ---------------------------------------------------------

        cursor.execute(
            """
            ALTER TABLE navigation_transaction_menu_item
            ADD CONSTRAINT
            navigation_transaction_menu_item_menu_fk
            FOREIGN KEY (menu_id)
            REFERENCES navigation_transaction_menu(id)
            ON DELETE CASCADE
            DEFERRABLE INITIALLY DEFERRED;
            """
        )

        cursor.execute(
            """
            ALTER TABLE navigation_transaction_menu_item
            ADD CONSTRAINT
            navigation_transaction_menu_item_parent_fk
            FOREIGN KEY (parent_item_id)
            REFERENCES navigation_transaction_menu_item(id)
            ON DELETE CASCADE
            DEFERRABLE INITIALLY DEFERRED;
            """
        )

        cursor.execute(
            """
            ALTER TABLE dynamic_level2_tab
            ADD CONSTRAINT
            dynamic_level2_tab_parent_fk
            FOREIGN KEY (parent_tab_id)
            REFERENCES dynamic_top_level_tab(id)
            ON DELETE CASCADE
            DEFERRABLE INITIALLY DEFERRED;
            """
        )

        cursor.execute(
            """
            ALTER TABLE dynamic_level3_tab
            ADD CONSTRAINT
            dynamic_level3_tab_parent_fk
            FOREIGN KEY (parent_tab_id)
            REFERENCES dynamic_level2_tab(id)
            ON DELETE CASCADE
            DEFERRABLE INITIALLY DEFERRED;
            """
        )

        cursor.execute(
            """
            ALTER TABLE navigation_user_access
            ADD CONSTRAINT
            navigation_user_access_top_fk
            FOREIGN KEY (top_level_tab_id)
            REFERENCES dynamic_top_level_tab(id)
            ON DELETE CASCADE
            DEFERRABLE INITIALLY DEFERRED;
            """
        )

        cursor.execute(
            """
            ALTER TABLE navigation_user_access
            ADD CONSTRAINT
            navigation_user_access_l2_fk
            FOREIGN KEY (level2_tab_id)
            REFERENCES dynamic_level2_tab(id)
            ON DELETE CASCADE
            DEFERRABLE INITIALLY DEFERRED;
            """
        )

        cursor.execute(
            """
            ALTER TABLE navigation_user_access
            ADD CONSTRAINT
            navigation_user_access_l3_fk
            FOREIGN KEY (level3_tab_id)
            REFERENCES dynamic_level3_tab(id)
            ON DELETE CASCADE
            DEFERRABLE INITIALLY DEFERRED;
            """
        )

        # ---------------------------------------------------------
        # 13. Recreate indexes
        # ---------------------------------------------------------

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

        # ---------------------------------------------------------
        # 14. Recreate NavigationUserAccess check constraint
        # ---------------------------------------------------------

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

        # ---------------------------------------------------------
        # 15. Recreate partial unique indexes
        # ---------------------------------------------------------

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


def _backwards(apps, schema_editor):
    raise RuntimeError(
        "This migration is irreversible because the generated "
        "BIGINT -> UUID mappings are not retained."
    )


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        (
            "navigation",
            "0006_dynamiclevel3tab_and_more",
        ),
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