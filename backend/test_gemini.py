from gemini import generate_sql


schema = {
    "employees": [
        {
            "name": "id",
            "type": "int",
            "nullable": "NO",
            "key": "PRI"
        },
        {
            "name": "name",
            "type": "varchar(100)",
            "nullable": "YES",
            "key": ""
        },
        {
            "name": "department",
            "type": "varchar(50)",
            "nullable": "YES",
            "key": ""
        },
        {
            "name": "salary",
            "type": "decimal(10,2)",
            "nullable": "YES",
            "key": ""
        },
        {
            "name": "city",
            "type": "varchar(50)",
            "nullable": "YES",
            "key": ""
        }
    ]
}


questions = [
    "Show all employees",
    "Show employees in Hyderabad",
    "Show employees with salary above 60000",
    "Who has the highest salary?",
    "Show all employees in the IT department"
]


for question in questions:
    print("\n========================================")
    print("QUESTION:")
    print(question)

    try:
        sql = generate_sql(question, schema)

        print("\nGENERATED SQL:")
        print(sql)

    except Exception as error:
        print("\nERROR:")
        print(error)