import mysql.connector


# ============================================================
# CONNECT TO A DATABASE
# ============================================================

def get_connection(
    host="localhost",
    port=3306,
    user="root",
    password="",
    database=None
):
    config = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
    }

    if database:
        config["database"] = database

    return mysql.connector.connect(**config)


# ============================================================
# GET DATABASE SCHEMA
# ============================================================

def get_database_schema(connection):
    if connection is None:
        raise ValueError("A valid database connection is required.")

    cursor = connection.cursor()
    schema = {}

    try:
        cursor.execute("SHOW TABLES")
        rows = cursor.fetchall()

        for row in rows:
            if isinstance(row, dict):
                table_name = next(iter(row.values()))
            else:
                table_name = row[0]

            cursor.execute(f"DESCRIBE `{table_name}`")
            columns = cursor.fetchall()

            schema[table_name] = []

            for column in columns:
                schema[table_name].append({
                    "name": column[0],
                    "type": column[1],
                    "nullable": column[2],
                    "key": column[3],
                })

        return schema

    finally:
        cursor.close()