import pytest

from validator import validate_sql
from gemini import normalize_question
from fallback_sql import fallback_generate_sql


SCHEMA = {
    "employees": [
        {"name": "id", "type": "int", "nullable": "NO", "key": "PRI"},
        {"name": "name", "type": "varchar(255)", "nullable": "YES", "key": ""},
        {"name": "department", "type": "varchar(255)", "nullable": "YES", "key": ""},
        {"name": "salary", "type": "decimal(10,2)", "nullable": "YES", "key": ""},
        {"name": "city", "type": "varchar(255)", "nullable": "YES", "key": ""},
    ]
}


def test_validate_sql_accepts_safe_select():
    valid, msg = validate_sql(
        "SELECT salary FROM employees WHERE id = 3;",
        SCHEMA,
    )
    assert valid is True
    assert msg is None


def test_validate_sql_rejects_insert():
    valid, msg = validate_sql("INSERT INTO employees (name) VALUES ('A');", SCHEMA)
    assert valid is False
    assert "Only SELECT" in msg or "Forbidden" in msg


def test_validate_sql_rejects_unknown_table():
    valid, msg = validate_sql("SELECT * FROM missing_table;", SCHEMA)
    assert valid is False
    assert "Table" in msg


def test_validate_sql_rejects_unknown_column():
    valid, msg = validate_sql("SELECT fake_column FROM employees;", SCHEMA)
    assert valid is False
    assert "column" in msg.lower()


def test_normalize_question_handles_voice_values():
    normalized = normalize_question("I.T Department and 60 000 salary")
    assert "IT" in normalized
    assert "60000" in normalized


def test_fallback_group_by_for_department_question():
    sql = fallback_generate_sql("How many employees are there in each department?", SCHEMA)
    assert "GROUP BY" in sql.upper()
    assert "department" in sql.lower()
    assert "WHERE department = 'each department'" not in sql.lower()


def test_fallback_limits_for_top_three():
    sql = fallback_generate_sql("Show the top three highest paid employees.", SCHEMA)
    assert "LIMIT 3" in sql.upper()
    assert "ORDER BY" in sql.upper()


def test_fallback_handles_name_and_salary_question():
    sql = fallback_generate_sql("What is Rahul's salary?", SCHEMA)
    assert "WHERE" in sql.upper()
    assert "salary" in sql.lower()
