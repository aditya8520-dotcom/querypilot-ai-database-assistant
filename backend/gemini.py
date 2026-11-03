import os
import re

from dotenv import load_dotenv

try:
    from google import genai
except Exception:
    genai = None


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

GEMINI_MODEL = "gemini-3.8-flash"


# ============================================================
# GEMINI CLIENT
# ============================================================

def get_client():

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing from backend/.env"
        )

    if genai is None:
        raise RuntimeError(
            "google-genai is not installed."
        )

    return genai.Client(
        api_key=api_key
    )


# ============================================================
# BUILD DATABASE SCHEMA
# ============================================================

def build_schema_text(schema):

    if not schema:
        return "No database schema available."

    lines = []

    for table_name, columns in schema.items():

        lines.append(
            f"TABLE: {table_name}"
        )

        for column in columns:

            name = column.get(
                "name",
                "UNKNOWN"
            )

            data_type = column.get(
                "type",
                "UNKNOWN"
            )

            nullable = column.get(
                "nullable"
            )

            key = column.get(
                "key"
            )

            details = [
                f"TYPE={data_type}"
            ]

            if nullable == "NO":

                details.append(
                    "NOT NULL"
                )

            if key == "PRI":

                details.append(
                    "PRIMARY KEY"
                )

            if key == "UNI":

                details.append(
                    "UNIQUE"
                )

            lines.append(
                f"  COLUMN: {name} "
                f"({', '.join(details)})"
            )

        lines.append("")

    return "\n".join(lines)


# ============================================================
# CLEAN QUESTION
# ============================================================

def normalize_question(question):

    if question is None:
        return ""

    question = str(question).strip()

    # Remove excessive whitespace

    question = re.sub(
        r"\s+",
        " ",
        question
    )

    return question


# ============================================================
# CLEAN GEMINI RESPONSE
# ============================================================

def clean_sql(text):

    if not text:
        return ""

    sql = str(text).strip()

    # --------------------------------------------------------
    # Remove Markdown code fences
    # --------------------------------------------------------

    sql = re.sub(
        r"```sql\s*",
        "",
        sql,
        flags=re.IGNORECASE
    )

    sql = re.sub(
        r"```mysql\s*",
        "",
        sql,
        flags=re.IGNORECASE
    )

    sql = sql.replace(
        "```",
        ""
    )

    sql = sql.strip()

    # --------------------------------------------------------
    # Find SELECT or WITH
    # --------------------------------------------------------

    match = re.search(
        r"\b(SELECT|WITH)\b",
        sql,
        flags=re.IGNORECASE
    )

    if match:

        sql = sql[
            match.start():
        ]

    sql = sql.strip()

    # --------------------------------------------------------
    # Remove trailing semicolon
    # --------------------------------------------------------

    sql = sql.rstrip(";").strip()

    return sql


# ============================================================
# VALIDATE GENERATED SQL
# ============================================================

def validate_generated_sql(sql):

    if not sql:

        raise ValueError(
            "Gemini returned empty SQL."
        )

    # --------------------------------------------------------
    # Must start with SELECT or WITH
    # --------------------------------------------------------

    if not re.match(
        r"^(SELECT|WITH)\b",
        sql,
        flags=re.IGNORECASE
    ):

        raise ValueError(
            "Generated query is not a SELECT query."
        )

    # --------------------------------------------------------
    # Only one SQL statement
    # --------------------------------------------------------

    if ";" in sql:

        raise ValueError(
            "Multiple SQL statements are not allowed."
        )

    # --------------------------------------------------------
    # Read-only SQL
    # --------------------------------------------------------

    forbidden = [

        r"\bINSERT\b",
        r"\bUPDATE\b",
        r"\bDELETE\b",
        r"\bDROP\b",
        r"\bALTER\b",
        r"\bCREATE\b",
        r"\bTRUNCATE\b",
        r"\bRENAME\b",
        r"\bGRANT\b",
        r"\bREVOKE\b",
        r"\bCALL\b",
        r"\bEXEC\b",
        r"\bEXECUTE\b"
    ]

    for pattern in forbidden:

        if re.search(
            pattern,
            sql,
            flags=re.IGNORECASE
        ):

            raise ValueError(
                "Only read-only SQL queries are allowed."
            )

    return True


# ============================================================
# GENERATE SQL
# ============================================================

def generate_sql(question, schema):

    question = normalize_question(
        question
    )

    if not question:

        raise ValueError(
            "Question cannot be empty."
        )

    if not schema:

        raise ValueError(
            "Database schema is empty."
        )

    # --------------------------------------------------------
    # Build actual schema
    # --------------------------------------------------------

    schema_text = build_schema_text(
        schema
    )

    # ========================================================
    # PROMPT
    # ========================================================

    prompt = f"""
You are an expert MySQL natural-language-to-SQL engine.

Your task is to understand the user's question semantically
and convert it into ONE correct MySQL SELECT query.

The user may express the same intent in many different ways.

Do NOT rely on exact keywords.

Do NOT expect the user to use database column names.

Understand synonyms, conversational language, informal wording,
spoken language, grammatical variations, and different sentence
structures.

The database schema provided below is the ONLY source of truth.

============================================================
ACTUAL DATABASE SCHEMA
============================================================

{schema_text}

============================================================
USER QUESTION
============================================================

{question}

============================================================
CORE OBJECTIVE
============================================================

First understand what information the user is asking for.

Then determine which table or tables contain that information.

Then determine which columns are relevant.

Then construct the SQL query that answers the user's intent.

The user's wording does NOT have to match the database schema.

For example, if the schema contains:

    salary

the user might say:

    pay
    income
    earnings
    compensation
    money they make
    how much they earn

Understand the meaning and map it to the actual schema.

Likewise, if the schema contains:

    city

the user might say:

    location
    place
    where they live
    where they are located

Only use the actual column that exists in the schema.

============================================================
SCHEMA RULES
============================================================

1. Use ONLY tables that exist in the schema.

2. Use ONLY columns that exist in the schema.

3. Never invent tables.

4. Never invent columns.

5. Never assume a column exists because it would normally
   exist in a database.

6. Use the actual column names from the schema.

7. Respect table relationships when multiple tables are
   required and the schema provides enough information
   to join them.

8. Do not create joins based on guesses.

9. If a question can be answered using one table, prefer
   the simpler query.

============================================================
NATURAL LANGUAGE UNDERSTANDING
============================================================

Understand different ways of expressing the same intent.

Examples of semantic equivalence:

"highest salary"
"largest salary"
"maximum salary"
"most money"
"highest paid"
"who earns the most"
"who makes the most"
"who gets paid the most"

These all express the concept of finding the maximum
value of the appropriate salary-like column.

Similarly:

"lowest"
"smallest"
"minimum"
"least"
"who earns the least"

express the concept of finding the minimum.

Do NOT implement this with Python keyword matching.

The AI must understand the meaning of the complete sentence.

============================================================
FILTERS
============================================================

Understand natural-language filters.

Examples:

"people in Hyderabad"

may correspond to:

city = 'Hyderabad'

"employees from the IT department"

may correspond to:

department = 'IT'

"products cheaper than 500"

may correspond to:

price < 500

"students older than 20"

may correspond to:

age > 20

Only use the appropriate actual schema columns.

============================================================
COMPARISONS
============================================================

Interpret natural language comparisons correctly.

"above X"
"over X"
"more than X"
"greater than X"

=> >

"below X"
"under X"
"less than X"
"lower than X"

=> <

"at least X"
"minimum X"

=> >=

"at most X"
"maximum X"

=> <=

"equal to X"
"exactly X"

=> =

============================================================
SORTING
============================================================

Understand natural sorting requests.

Examples:

"highest first"
"largest first"
"most expensive first"
"descending order"

=> ORDER BY ... DESC

"lowest first"
"smallest first"
"cheapest first"
"ascending order"

=> ORDER BY ... ASC

============================================================
TOP / BOTTOM RESULTS
============================================================

If the user requests a specific number of records,
use LIMIT.

Examples:

"top 5"
"best 5"
"first 5"
"five highest"
"five lowest"

must result in an appropriate ORDER BY and LIMIT.

Do not use LIMIT when the user asks for an aggregate such
as maximum or minimum unless the requested result actually
requires a specific record.

============================================================
AGGREGATIONS
============================================================

Understand requests for:

COUNT
SUM
AVG
MIN
MAX

Examples:

"how many"
"number of"
"total count"

=> COUNT

"total amount"
"sum of"

=> SUM

"average"
"mean"

=> AVG

"highest"
"maximum"

=> MAX when the user asks for the value itself.

"lowest"
"minimum"

=> MIN when the user asks for the value itself.

If the user asks for the complete record associated with
the maximum or minimum value, return the appropriate record
instead of only returning the numeric maximum/minimum.

============================================================
GROUPING
============================================================

If the user asks for a result for each category,
use GROUP BY.

Examples:

"employees in each department"

"sales by city"

"average salary for each department"

"number of products in each category"

Determine the appropriate grouping column from the schema.

============================================================
DISTINCT
============================================================

If the user asks for unique, different, or distinct values,
use DISTINCT.

Examples:

"what cities are represented?"

"list unique departments"

"which locations are available?"

============================================================
TEXT SEARCH
============================================================

Understand partial-name and partial-text requests.

Examples:

"names starting with A"

=> LIKE 'A%'

"names ending with n"

=> LIKE '%n'

"names containing raj"

=> LIKE '%raj%'

Use LIKE when the user's request implies partial matching.

============================================================
NULL VALUES
============================================================

If the user asks for missing, empty, unavailable, or null
values and the schema supports NULL:

use:

IS NULL

or:

IS NOT NULL

Do not compare NULL using = or !=.

============================================================
NUMBERS
============================================================

Understand numbers written in different forms.

Examples:

"three" = 3
"ten" = 10
"twenty five" = 25
"sixty thousand" = 60000
"60,000" = 60000
"60 000" = 60000

Natural speech may contain number words.

Interpret them according to the user's intended meaning.

============================================================
DATES AND TIME
============================================================

If the schema contains date/time columns, understand
natural date expressions when possible.

Examples:

"today"
"yesterday"
"this month"
"last month"
"this year"
"recent records"

Use appropriate MySQL date/time functions when the schema
supports the requested operation.

Never invent a date column.

============================================================
IDENTIFIERS
============================================================

If a user refers to a record by an identifier such as:

"employee 3"
"record 3"
"ID 3"
"number 3"
"employee number three"

and the schema contains an appropriate primary-key column,
interpret the number as the identifier when the context
clearly indicates a record ID.

Do NOT automatically interpret a record number as a name.

If the user explicitly provides a person's name, use the
appropriate name column only if that column exists.

============================================================
FULL RECORD VS SINGLE VALUE
============================================================

Pay attention to what the user actually wants.

If the user asks:

"What is the salary of Rahul?"

return the salary column.

If the user asks:

"Show me Rahul's details."

return the relevant record.

If the user asks:

"Who earns the most?"

return the record/person associated with the maximum value
when the schema supports identifying that record.

If the user asks:

"What is the highest salary?"

return the maximum salary value.

Do not confuse an aggregate-value question with a
record-identification question.

============================================================
CONVERSATIONAL QUESTIONS
============================================================

Understand informal questions.

Examples:

"Who makes the most money?"

"Tell me about the highest paid employee."

"Can you show people from Hyderabad?"

"I want to see the IT guys."

"Give me the cheapest product."

"How many are there?"

"Which one costs the most?"

"What is the average?"

"Show me everything about Rahul."

These are examples of language style only.

Do not hardcode these questions.

Understand the user's actual intent using the schema.

============================================================
READ-ONLY REQUIREMENT
============================================================

The generated SQL must be read-only.

Allowed:

SELECT

WITH ... SELECT

Never generate:

INSERT
UPDATE
DELETE
DROP
ALTER
CREATE
TRUNCATE
RENAME
GRANT
REVOKE
CALL
EXEC
EXECUTE

Never generate multiple SQL statements.

============================================================
SQL QUALITY
============================================================

Generate clean, valid MySQL syntax.

Use aliases when they make aggregate results easier
to understand.

Prefer explicit column selection when the user asks
for specific information.

Use SELECT * when the user explicitly asks for all
information or a complete record.

Do not add unnecessary conditions.

Do not add unnecessary joins.

Do not invent business rules.

Do not assume values that the user did not provide.

Preserve the exact meaning of the user's request.

============================================================
FINAL VALIDATION
============================================================

Before returning the query, internally verify:

1. Does every table exist?

2. Does every column exist?

3. Does the query actually answer the user's question?

4. Are filters correct?

5. Is aggregation correct?

6. Is GROUP BY correct?

7. Is ORDER BY correct?

8. Is LIMIT correct?

9. Are joins supported by the schema?

10. Is the query read-only?

11. Is there exactly one SQL statement?

============================================================
OUTPUT FORMAT
============================================================

Return ONLY the SQL query.

Do NOT return:

- explanations
- comments
- Markdown
- code fences
- "SQL:"
- reasoning
- bullet points
- natural-language text

============================================================
SQL
============================================================
"""

    # ========================================================
    # CALL GEMINI WITH AUTOMATIC MODEL FALLBACK
    # ========================================================

    client = get_client()

    models_to_try = [
        GEMINI_MODEL,
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-2.5-flash"
    ]

    response_text = None
    last_error = None

    for model_name in models_to_try:
        try:
            print(f"Trying Gemini model: {model_name}")

            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )

            response_text = getattr(
                response,
                "text",
                None
            )

            if response_text:
                print(f"Gemini model succeeded: {model_name}")
                break

            last_error = ValueError(
                f"{model_name} returned no text."
            )

        except Exception as error:
            last_error = error
            error_text = str(error).upper()

            print(
                f"Gemini model failed: {model_name} -> {error}"
            )

            temporary_error = (
                "503" in error_text
                or "UNAVAILABLE" in error_text
                or "HIGH DEMAND" in error_text
                or "OVERLOADED" in error_text
                or "SERVICE UNAVAILABLE" in error_text
            )

            if not temporary_error:
                raise

    if not response_text:
        raise RuntimeError(
            f"All Gemini models failed. Last error: {last_error}"
        )

    # ========================================================
    # CLEAN SQL
    # ========================================================

    sql = clean_sql(
        response_text
    )

    # ========================================================
    # VALIDATE SQL
    # ========================================================

    validate_generated_sql(
        sql
    )

    # ========================================================
    # LOG
    # ========================================================

    print("\n========================================")
    print("GEMINI SQL GENERATION")
    print("========================================")

    print("Question:")
    print(question)

    print("\nSQL:")
    print(sql)

    print("========================================\n")

    return sql