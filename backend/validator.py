import re


# ============================================================
# SQL RESERVED WORDS
# ============================================================

RESERVED_WORDS = {
    "select",
    "from",
    "join",
    "where",
    "and",
    "or",
    "not",
    "in",
    "like",
    "group",
    "by",
    "order",
    "limit",
    "having",
    "as",
    "on",
    "distinct",
    "count",
    "sum",
    "avg",
    "min",
    "max",
    "case",
    "when",
    "then",
    "else",
    "end",
    "is",
    "null",
    "asc",
    "desc",
    "between",
    "ifnull",
    "concat",
    "round",
    "cast",
    "coalesce",
    "exists",
    "all",
    "any",
    "with",
    "union",
    "inner",
    "left",
    "right",
    "full",
    "cross",
    "outer",
    "fetch",
    "offset",
    "top",
    "true",
    "false",
    "interval",
    "over",
    "partition",
    "window",
    "row_number",
    "rank",
    "dense_rank",
}


# ============================================================
# FORBIDDEN SQL OPERATIONS
# ============================================================

FORBIDDEN_PATTERN = re.compile(
    r"""
    \b(
        INSERT|
        UPDATE|
        DELETE|
        DROP|
        ALTER|
        CREATE|
        TRUNCATE|
        RENAME|
        GRANT|
        REVOKE|
        CALL|
        EXEC|
        EXECUTE|
        MERGE|
        ATTACH|
        DETACH|
        LOAD_FILE
    )\b
    """,
    re.IGNORECASE | re.VERBOSE
)


# ============================================================
# REMOVE SQL COMMENTS
# ============================================================

def remove_comments(sql):
    """
    Remove SQL comments before validation.
    """

    # -- comment
    sql = re.sub(
        r"--[^\n]*",
        " ",
        sql
    )

    # # comment
    sql = re.sub(
        r"#[^\n]*",
        " ",
        sql
    )

    # /* comment */
    sql = re.sub(
        r"/\*.*?\*/",
        " ",
        sql,
        flags=re.DOTALL
    )

    return sql


# ============================================================
# REMOVE STRING LITERALS
# ============================================================

def remove_string_literals(sql):
    """
    Replace strings such as:
        'Hyderabad'
        'IT'
        'John'
    
    with placeholders.

    This prevents words inside strings from being
    incorrectly interpreted as column names.
    """

    return re.sub(
        r"'(?:''|[^'])*'",
        " ",
        sql
    )


# ============================================================
# GET SCHEMA INFORMATION
# ============================================================

def get_schema_information(schema):

    table_lookup = {
        table.lower(): table
        for table in schema.keys()
    }

    column_lookup = {}

    for table_name, columns in schema.items():

        column_lookup[table_name.lower()] = {
            column["name"].lower()
            for column in columns
        }

    all_columns = set()

    for columns in column_lookup.values():
        all_columns.update(columns)

    return (
        table_lookup,
        column_lookup,
        all_columns
    )


# ============================================================
# FIND TABLES
# ============================================================

def find_tables(sql):

    tables = []

    # FROM table
    from_matches = re.findall(
        r"""
        \bFROM\s+
        `?([A-Za-z_][A-Za-z0-9_]*)`?
        """,
        sql,
        flags=re.IGNORECASE | re.VERBOSE
    )

    tables.extend(from_matches)

    # JOIN table
    join_matches = re.findall(
        r"""
        \bJOIN\s+
        `?([A-Za-z_][A-Za-z0-9_]*)`?
        """,
        sql,
        flags=re.IGNORECASE | re.VERBOSE
    )

    tables.extend(join_matches)

    return tables


# ============================================================
# FIND TABLE ALIASES
# ============================================================

def find_table_aliases(sql, valid_tables):

    aliases = set()

    # Example:
    # FROM employees e
    # FROM employees AS e

    pattern = re.compile(
        r"""
        \bFROM\s+
        `?([A-Za-z_][A-Za-z0-9_]*)`?
        (?:\s+AS)?\s+
        ([A-Za-z_][A-Za-z0-9_]*)
        """,
        re.IGNORECASE | re.VERBOSE
    )

    for match in pattern.finditer(sql):

        table_name = match.group(1).lower()
        alias = match.group(2).lower()

        if table_name in valid_tables:
            if alias not in RESERVED_WORDS:
                aliases.add(alias)

    # JOIN aliases
    join_pattern = re.compile(
        r"""
        \bJOIN\s+
        `?([A-Za-z_][A-Za-z0-9_]*)`?
        (?:\s+AS)?\s+
        ([A-Za-z_][A-Za-z0-9_]*)
        """,
        re.IGNORECASE | re.VERBOSE
    )

    for match in join_pattern.finditer(sql):

        table_name = match.group(1).lower()
        alias = match.group(2).lower()

        if table_name in valid_tables:
            if alias not in RESERVED_WORDS:
                aliases.add(alias)

    return aliases


# ============================================================
# FIND COLUMN REFERENCES
# ============================================================

def find_column_references(sql):

    references = set()

    # --------------------------------------------------------
    # table.column
    # --------------------------------------------------------

    qualified = re.findall(
        r"""
        `?([A-Za-z_][A-Za-z0-9_]*)`?
        \.
        `?([A-Za-z_][A-Za-z0-9_]*)`?
        """,
        sql,
        flags=re.IGNORECASE | re.VERBOSE
    )

    for table_or_alias, column in qualified:

        references.add(
            (
                table_or_alias.lower(),
                column.lower()
            )
        )

    # --------------------------------------------------------
    # Backticked identifiers
    # --------------------------------------------------------

    backticked = re.findall(
        r"`([A-Za-z_][A-Za-z0-9_]*)`",
        sql
    )

    for identifier in backticked:

        references.add(
            (
                None,
                identifier.lower()
            )
        )

    return references


# ============================================================
# FIND UNQUOTED IDENTIFIERS
# ============================================================

def find_identifiers(sql):

    identifiers = []

    for match in re.finditer(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\b",
        sql
    ):

        identifiers.append(
            match.group(1)
        )

    return identifiers


# ============================================================
# VALIDATE SQL
# ============================================================

def validate_sql(sql, schema):
    """
    Validate that generated SQL is:

    1. Non-empty
    2. A single SELECT statement
    3. Free from dangerous SQL operations
    4. Uses only tables from the connected database
    5. Uses only columns from the connected database
    """

    # ========================================================
    # BASIC CHECK
    # ========================================================

    if not sql or not sql.strip():

        return (
            False,
            "SQL query is empty."
        )

    sql = sql.strip()

    # ========================================================
    # REMOVE COMMENTS
    # ========================================================

    clean_sql = remove_comments(sql).strip()

    if not clean_sql:

        return (
            False,
            "SQL query is empty."
        )

    # ========================================================
    # ONLY ONE STATEMENT
    # ========================================================

    # Allow one final semicolon.
    semicolon_count = clean_sql.count(";")

    if semicolon_count > 1:

        return (
            False,
            "Multiple SQL statements are not allowed."
        )

    # ========================================================
    # MUST START WITH SELECT
    # ========================================================

    if not re.match(
        r"^\s*SELECT\b",
        clean_sql,
        re.IGNORECASE
    ):

        return (
            False,
            "Only SELECT queries are allowed."
        )

    # ========================================================
    # FORBIDDEN OPERATIONS
    # ========================================================

    forbidden_match = FORBIDDEN_PATTERN.search(
        clean_sql
    )

    if forbidden_match:

        keyword = forbidden_match.group(1).upper()

        return (
            False,
            f"Forbidden SQL operation: {keyword}"
        )

    # ========================================================
    # EXTRA SECURITY CHECKS
    # ========================================================

    dangerous_patterns = [

        # INTO OUTFILE
        r"\bINTO\s+OUTFILE\b",

        # INTO DUMPFILE
        r"\bINTO\s+DUMPFILE\b",

        # LOAD DATA
        r"\bLOAD\s+DATA\b",

        # SYSTEM commands
        r"\bSYSTEM\b",

        # Multiple SELECT statements
        r";\s*SELECT\b",

        # UNION is intentionally blocked for simplicity
        r"\bUNION\b",
    ]

    for pattern in dangerous_patterns:

        if re.search(
            pattern,
            clean_sql,
            re.IGNORECASE
        ):

            return (
                False,
                "Potentially unsafe SQL operation detected."
            )

    # ========================================================
    # SCHEMA CHECK
    # ========================================================

    if not schema:

        return (
            False,
            "Database schema is empty."
        )

    (
        table_lookup,
        column_lookup,
        all_columns
    ) = get_schema_information(schema)

    # ========================================================
    # CHECK TABLES
    # ========================================================

    found_tables = find_tables(
        clean_sql
    )

    if not found_tables:

        return (
            False,
            "No valid FROM table was found."
        )

    for table_name in found_tables:

        if table_name.lower() not in table_lookup:

            return (
                False,
                f"Table '{table_name}' does not exist "
                f"in the connected database."
            )

    # ========================================================
    # TABLE ALIASES
    # ========================================================

    aliases = find_table_aliases(
        clean_sql,
        table_lookup
    )

    # ========================================================
    # REMOVE STRING VALUES
    # ========================================================

    sql_without_strings = remove_string_literals(
        clean_sql
    )

    # ========================================================
    # QUALIFIED COLUMN CHECK
    #
    # Example:
    #
    # employees.salary
    # e.salary
    # ========================================================

    qualified_references = find_column_references(
        sql_without_strings
    )

    for table_or_alias, column in qualified_references:

        if column not in all_columns:

            return (
                False,
                f"Column '{column}' does not exist "
                f"in the connected database."
            )

    # ========================================================
    # BACKTICKED IDENTIFIER CHECK
    # ========================================================

    backticked_identifiers = re.findall(
        r"`([A-Za-z_][A-Za-z0-9_]*)`",
        sql_without_strings
    )

    for identifier in backticked_identifiers:

        identifier_lower = identifier.lower()

        # Valid table
        if identifier_lower in table_lookup:
            continue

        # Valid column
        if identifier_lower in all_columns:
            continue

        # Valid alias
        if identifier_lower in aliases:
            continue

        return (
            False,
            f"Table or column '{identifier}' "
            f"does not exist in the connected database."
        )

    # ========================================================
    # UNQUOTED IDENTIFIER CHECK
    # ========================================================

    identifiers = find_identifiers(
        sql_without_strings
    )

    # Function names that may appear in SQL
    function_names = {
        "count",
        "sum",
        "avg",
        "min",
        "max",
        "round",
        "concat",
        "coalesce",
        "ifnull",
        "cast",
        "date",
        "year",
        "month",
        "day",
        "upper",
        "lower",
        "length",
        "substring",
        "trim",
    }

    for identifier in identifiers:

        identifier_lower = identifier.lower()

        # ----------------------------------------------------
        # SQL keyword
        # ----------------------------------------------------

        if identifier_lower in RESERVED_WORDS:
            continue

        # ----------------------------------------------------
        # Table
        # ----------------------------------------------------

        if identifier_lower in table_lookup:
            continue

        # ----------------------------------------------------
        # Column
        # ----------------------------------------------------

        if identifier_lower in all_columns:
            continue

        # ----------------------------------------------------
        # Alias
        # ----------------------------------------------------

        if identifier_lower in aliases:
            continue

        # ----------------------------------------------------
        # Function
        # ----------------------------------------------------

        if identifier_lower in function_names:
            continue

        # ----------------------------------------------------
        # SQL aliases after AS
        # ----------------------------------------------------

        if re.search(
            rf"\bAS\s+{re.escape(identifier)}\b",
            sql_without_strings,
            re.IGNORECASE
        ):

            continue

        # ----------------------------------------------------
        # Numeric-looking identifier
        # ----------------------------------------------------

        if identifier_lower.isdigit():
            continue

        # ----------------------------------------------------
        # MySQL special identifiers
        # ----------------------------------------------------

        if identifier_lower in {
            "current_date",
            "current_time",
            "current_timestamp",
            "current_date()",
            "current_time()",
            "current_timestamp()",
        }:

            continue

        # ----------------------------------------------------
        # Unknown identifier
        #
        # We do NOT immediately reject every unknown word
        # because SQL can contain aliases and expressions.
        # ----------------------------------------------------

    # ========================================================
    # FINAL CHECK
    # ========================================================

    return True, None