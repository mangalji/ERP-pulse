import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import connection


def main():
    with connection.cursor() as cursor:
        tables = connection.introspection.table_names()

        for table in tables:
            print("\n" + "=" * 80)
            print(f"TABLE: {table}")
            print("=" * 80)

            description = connection.introspection.get_table_description(
                cursor,
                table,
            )

            for column in description:
                print(
                    f"{column.name:35} "
                    f"type={column.type_code!s:20} "
                    f"null={column.null_ok}"
                )

            constraints = connection.introspection.get_constraints(
                cursor,
                table,
            )

            print("\nForeign Keys / Constraints:")
            for name, info in constraints.items():
                if info.get("foreign_key"):
                    print(
                        f"  {name}: "
                        f"{info['columns']} -> {info['foreign_key']}"
                    )


if __name__ == "__main__":
    main()