from database import get_database_schema
from fallback_sql import fallback_generate_sql


schema = get_database_schema()


questions = [
    "Show properties in Hyderabad below 20000",
    "Show properties in Bangalore above 30000",
    "Show 2 bedroom properties in Hyderabad",
    "Show available properties in Chennai"
]


for question in questions:

    print("\nQuestion:")
    print(question)

    sql = fallback_generate_sql(question, schema)

    print("\nGenerated SQL:")
    print(sql)

    print("-" * 60)