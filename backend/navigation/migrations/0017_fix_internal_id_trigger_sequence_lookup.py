from django.db import migrations


# 0015 renamed the tables (dynamic_top_level_tab -> center_tabs_table, ...)
# but the sequences kept their old names, while the trigger function built
# the sequence name from TG_TABLE_NAME. On a fresh database every INSERT into
# the navigation tables therefore failed with:
#   relation "center_tabs_table_internal_id_seq" does not exist
# pg_get_serial_sequence() follows the column ownership instead of a name.
FORWARD_SQL = """
CREATE OR REPLACE FUNCTION navigation_generate_internal_id()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.internal_id IS NULL OR NEW.internal_id = 0 THEN
        NEW.internal_id := nextval(
            pg_get_serial_sequence(
                format('%I.%I', TG_TABLE_SCHEMA, TG_TABLE_NAME),
                'internal_id'
            )
        );
    END IF;

    RETURN NEW;
END;
$$;
"""

REVERSE_SQL = """
CREATE OR REPLACE FUNCTION navigation_generate_internal_id()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    sequence_name TEXT;
BEGIN
    IF NEW.internal_id IS NULL OR NEW.internal_id = 0 THEN
        sequence_name := TG_TABLE_NAME || '_internal_id_seq';
        EXECUTE format('SELECT nextval(%L)', sequence_name)
        INTO NEW.internal_id;
    END IF;

    RETURN NEW;
END;
$$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("navigation", "0016_alter_navigationuseraccess_table"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
