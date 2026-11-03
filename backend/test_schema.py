from database import get_connection, get_database_schema


try:
    connection = get_connection(
        host="localhost",
        port=3306,
        user="root",
        password="root",
        database="voice_sql"
    )
    schema = get_database_schema(connection)

    print("\nDATABASE SCHEMA\n")
    print("====================")

    for table_name, columns in schema.items():
        print(f"\nTable: {table_name}")
        for column in columns:
            print(f"  {column['name']} ({column['type']}) Key: {column['key']}")

    connection.close()

except Exception as exc:
    print(f"Schema check skipped: {exc}")