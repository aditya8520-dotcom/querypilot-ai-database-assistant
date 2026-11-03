import re


NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}


def fallback_generate_sql(question, schema):
    """
    Local read-only SQL fallback generator.

    This is used only when Gemini cannot generate SQL.

    Supports:
    - SELECT
    - WHERE
    - equality filters
    - numeric comparisons
    - COUNT
    - highest / lowest
    - ORDER BY
    - LIMIT
    - employee number / ID lookups
    - employee name lookups
    - city filters
    - department filters
    - bedrooms / bathrooms
    - available / active / enabled
    """

    if not schema:
        raise ValueError("Database schema is empty.")

    question = normalize_question(question)
    q = question.lower().strip()

    table_names = list(schema.keys())

    if not table_names:
        raise ValueError("No tables found in database schema.")

    # ---------------------------------------------------------
    # 1. SELECT TABLE
    # ---------------------------------------------------------

    selected_table = find_table(q, table_names)

    columns = schema[selected_table]

    column_names = [
        column["name"]
        for column in columns
    ]

    if not column_names:
        raise ValueError(
            f"No columns found for table '{selected_table}'."
        )

    column_map = {
        column.lower(): column
        for column in column_names
    }

    # ---------------------------------------------------------
    # 2. COLUMN TYPES
    # ---------------------------------------------------------

    numeric_columns = []

    for column in columns:
        column_name = column["name"]
        column_type = str(
            column.get("type", "")
        ).lower()

        if any(
            data_type in column_type
            for data_type in [
                "int",
                "decimal",
                "float",
                "double",
                "numeric",
                "real"
            ]
        ):
            numeric_columns.append(column_name)

    # ---------------------------------------------------------
    # 3. CONDITIONS
    # ---------------------------------------------------------

    conditions = []

    def add_condition(condition):
        if condition not in conditions:
            conditions.append(condition)

    # ---------------------------------------------------------
    # 4. ID / EMPLOYEE NUMBER LOOKUP
    # ---------------------------------------------------------

    id_column = find_column(
        column_names,
        [
            "id",
            "employee_id",
            "property_id",
            "user_id",
            "customer_id"
        ]
    )

    if id_column:

        id_match = re.search(
            r"\b(?:number|no\.?|id|employee number|employee no\.?|"
            r"property number|property no\.?)\s*"
            r"(?:is|equals?|number)?\s*"
            r"(\d+)\b",
            q
        )

        if not id_match:

            id_match = re.search(
                r"\b(?:employee|property|user|customer)"
                r"\s+(?:number|no\.?|id)\s*(\d+)\b",
                q
            )

        if id_match:

            record_id = id_match.group(1)

            add_condition(
                f"`{id_column}` = {record_id}"
            )

    # ---------------------------------------------------------
    # 5. PERSON / NAME LOOKUP
    # ---------------------------------------------------------

    name_column = find_column(
        column_names,
        [
            "name",
            "employee_name",
            "full_name",
            "person_name"
        ]
    )

    if name_column:

        person_name = extract_person_name(
            question,
            q
        )

        if person_name:

            person_name = clean_text_value(
                person_name
            )

            add_condition(
                f"`{name_column}` = "
                f"'{escape_sql_value(person_name)}'"
            )

    # ---------------------------------------------------------
    # 6. CITY / LOCATION
    # ---------------------------------------------------------

    city_column = find_column(
        column_names,
        [
            "city",
            "location",
            "town"
        ]
    )

    if city_column:

        city = extract_city(q)

        if city:

            add_condition(
                f"`{city_column}` = "
                f"'{escape_sql_value(city.title())}'"
            )

    # ---------------------------------------------------------
    # 7. DEPARTMENT
    # ---------------------------------------------------------

    department_column = find_column(
        column_names,
        [
            "department",
            "dept",
            "team"
        ]
    )

    if department_column:

        department = extract_department(
            q
        )

        if department:

            add_condition(
                f"`{department_column}` = "
                f"'{escape_sql_value(department.upper())}'"
            )

    # ---------------------------------------------------------
    # 8. BEDROOMS / BHK
    # ---------------------------------------------------------

    bedroom_column = find_column(
        column_names,
        [
            "bedrooms",
            "bedroom",
            "bhk"
        ]
    )

    if bedroom_column:

        bedroom_match = re.search(
            r"\b(\d+)\s*(?:bhk|bedrooms?|bedroom)\b",
            q
        )

        if bedroom_match:

            bedrooms = bedroom_match.group(1)

            add_condition(
                f"`{bedroom_column}` = {bedrooms}"
            )

    # ---------------------------------------------------------
    # 9. BATHROOMS
    # ---------------------------------------------------------

    bathroom_column = find_column(
        column_names,
        [
            "bathrooms",
            "bathroom"
        ]
    )

    if bathroom_column:

        bathroom_match = re.search(
            r"\b(\d+)\s*(?:bathrooms?|bathroom)\b",
            q
        )

        if bathroom_match:

            bathrooms = bathroom_match.group(1)

            add_condition(
                f"`{bathroom_column}` = {bathrooms}"
            )

    # ---------------------------------------------------------
    # 10. GENERIC COLUMN EQUALITY
    # ---------------------------------------------------------

    for column in column_names:

        lower_column = column.lower()

        # Already handled
        if lower_column in {
            "id",
            "employee_id",
            "property_id",
            "user_id",
            "customer_id",
            "name",
            "employee_name",
            "full_name",
            "person_name",
            "city",
            "location",
            "town",
            "department",
            "dept",
            "team",
            "bedrooms",
            "bedroom",
            "bhk",
            "bathrooms",
            "bathroom"
        }:
            continue

        # Example:
        # property_type is apartment
        # salary equals 50000

        match = re.search(
            rf"\b{re.escape(lower_column)}\b"
            r"\s+(?:is|equals?|equal to)\s+"
            r"([a-zA-Z0-9_. -]+)",
            q
        )

        if match:

            value = match.group(1).strip()

            value = re.split(
                r"\s+(?:and|with|where|having)\s+",
                value,
                maxsplit=1
            )[0].strip()

            if value:

                if is_numeric_column(
                    column,
                    numeric_columns
                ):

                    number = extract_number(
                        value
                    )

                    if number is not None:

                        add_condition(
                            f"`{column}` = {number}"
                        )

                else:

                    add_condition(
                        f"`{column}` = "
                        f"'{escape_sql_value(value.title())}'"
                    )

    # ---------------------------------------------------------
    # 11. NUMERIC COMPARISONS
    # ---------------------------------------------------------

    for column in numeric_columns:

        lower_column = column.lower()

        if not column_mentioned(
            lower_column,
            q
        ):
            continue

        # >=
        match = re.search(
            rf"\b{re.escape(lower_column)}\b"
            r".{0,50}?"
            r"(?:at least|greater than or equal to|"
            r"more than or equal to|minimum of)\s*"
            r"(?:₹|rs\.?|inr|\$)?\s*"
            r"([\d][\d,\s]*)",
            q
        )

        if match:

            amount = clean_number(
                match.group(1)
            )

            if amount is not None:

                add_condition(
                    f"`{column}` >= {amount}"
                )

        # <=
        match = re.search(
            rf"\b{re.escape(lower_column)}\b"
            r".{0,50}?"
            r"(?:at most|less than or equal to|"
            r"no more than|maximum of)\s*"
            r"(?:₹|rs\.?|inr|\$)?\s*"
            r"([\d][\d,\s]*)",
            q
        )

        if match:

            amount = clean_number(
                match.group(1)
            )

            if amount is not None:

                add_condition(
                    f"`{column}` <= {amount}"
                )

        # <
        match = re.search(
            rf"\b{re.escape(lower_column)}\b"
            r".{0,50}?"
            r"(?:below|under|less than)\s*"
            r"(?:₹|rs\.?|inr|\$)?\s*"
            r"([\d][\d,\s]*)",
            q
        )

        if match:

            amount = clean_number(
                match.group(1)
            )

            if amount is not None:

                add_condition(
                    f"`{column}` < {amount}"
                )

        # >
        match = re.search(
            rf"\b{re.escape(lower_column)}\b"
            r".{0,50}?"
            r"(?:above|over|more than|greater than)\s*"
            r"(?:₹|rs\.?|inr|\$)?\s*"
            r"([\d][\d,\s]*)",
            q
        )

        if match:

            amount = clean_number(
                match.group(1)
            )

            if amount is not None:

                add_condition(
                    f"`{column}` > {amount}"
                )

        # Exact numeric value
        match = re.search(
            rf"\b{re.escape(lower_column)}\b"
            r"\s*(?:is|equals?|of)\s*"
            r"(?:₹|rs\.?|inr|\$)?\s*"
            r"([\d][\d,\s]*)",
            q
        )

        if match:

            amount = clean_number(
                match.group(1)
            )

            if amount is not None:

                add_condition(
                    f"`{column}` = {amount}"
                )

    # ---------------------------------------------------------
    # 12. BOOLEAN COLUMNS
    # ---------------------------------------------------------

    boolean_columns = [
        column
        for column in column_names
        if column.lower() in [
            "available",
            "active",
            "enabled",
            "verified"
        ]
    ]

    for column in boolean_columns:

        lower_column = column.lower()

        if any(
            phrase in q
            for phrase in [
                f"{lower_column}",
                f"currently {lower_column}",
                f"that are {lower_column}"
            ]
        ):

            # Don't blindly apply TRUE if user explicitly
            # asks for false/unavailable/inactive.
            if any(
                phrase in q
                for phrase in [
                    f"not {lower_column}",
                    f"un{lower_column}",
                    "unavailable",
                    "inactive",
                    "disabled",
                    "not active",
                    "not verified"
                ]
            ):

                add_condition(
                    f"`{column}` = FALSE"
                )

            else:

                add_condition(
                    f"`{column}` = TRUE"
                )

    # ---------------------------------------------------------
    # 13. COUNT
    # ---------------------------------------------------------

    is_count_query = any(
        phrase in q
        for phrase in [
            "how many",
            "number of",
            "count",
            "total number"
        ]
    )

    group_by_column = find_group_by_column(
        q,
        column_names
    )

    if is_count_query:

        if group_by_column:

            sql = (
                f"SELECT `{group_by_column}`, "
                f"COUNT(*) AS total "
                f"FROM `{selected_table}`"
            )

        else:

            sql = (
                f"SELECT COUNT(*) AS total "
                f"FROM `{selected_table}`"
            )

        if conditions:

            sql += (
                " WHERE "
                + " AND ".join(conditions)
            )

        if group_by_column:

            sql += (
                f" GROUP BY `{group_by_column}`"
            )

        sql += ";"

        return sql

    # ---------------------------------------------------------
    # 14. SELECT SPECIFIC COLUMNS
    # ---------------------------------------------------------

    explicit_columns = find_requested_columns(
        q,
        column_names
    )

    # If the user asks for salary, department, etc.,
    # return that column instead of SELECT *.

    if explicit_columns:

        select_columns = ", ".join(
            f"`{column}`"
            for column in explicit_columns
        )

    else:

        select_columns = "*"

    sql = (
        f"SELECT {select_columns} "
        f"FROM `{selected_table}`"
    )

    # ---------------------------------------------------------
    # 15. WHERE
    # ---------------------------------------------------------

    if conditions:

        sql += (
            " WHERE "
            + " AND ".join(conditions)
        )

    # ---------------------------------------------------------
    # 16. ORDER BY
    # ---------------------------------------------------------

    order_column = find_order_column(
        q,
        column_names,
        numeric_columns
    )

    order_direction = find_order_direction(
        q
    )

    if order_column:

        sql += (
            f" ORDER BY `{order_column}` "
            f"{order_direction}"
        )

    # ---------------------------------------------------------
    # 17. LIMIT
    # ---------------------------------------------------------

    limit = find_limit(q)

    # Highest / lowest normally means one result
    if limit is None and is_single_extreme_query(q):

        limit = 1

    if limit is not None:

        sql += f" LIMIT {limit}"

    # ---------------------------------------------------------
    # 18. GROUP BY
    # ---------------------------------------------------------

    if group_by_column:

        sql += (
            f" GROUP BY `{group_by_column}`"
        )

    # ---------------------------------------------------------
    # IMPORTANT:
    # GROUP BY must come before ORDER BY.
    #
    # For fallback simplicity, rebuild grouped queries
    # correctly here.
    # ---------------------------------------------------------

    if group_by_column:

        sql = (
            f"SELECT `{group_by_column}`, "
            f"COUNT(*) AS total "
            f"FROM `{selected_table}`"
        )

        if conditions:

            sql += (
                " WHERE "
                + " AND ".join(conditions)
            )

        sql += (
            f" GROUP BY `{group_by_column}`"
        )

        if order_column:

            sql += (
                f" ORDER BY `{order_column}` "
                f"{order_direction}"
            )

        if limit is not None:

            sql += f" LIMIT {limit}"

    sql += ";"

    return sql


# =============================================================
# HELPERS
# =============================================================


def normalize_question(question):

    question = str(question or "").strip()

    # Speech recognition sometimes converts:
    # I.T -> IT
    # I. T. -> IT

    question = re.sub(
        r"\bi\s*\.\s*t\s*\.?\b",
        "IT",
        question,
        flags=re.IGNORECASE
    )

    # Convert common spoken number formats.
    #
    # "60 000" -> "60000"
    # "60,000" -> "60000"

    question = re.sub(
        r"(?<=\d)[,\s]+(?=\d{3}\b)",
        "",
        question
    )

    # Convert number words where useful.
    question = replace_number_words(
        question
    )

    return question.strip()


def replace_number_words(text):

    for word, number in sorted(
        NUMBER_WORDS.items(),
        key=lambda item: -len(item[0])
    ):

        text = re.sub(
            rf"\b{re.escape(word)}\b",
            str(number),
            text,
            flags=re.IGNORECASE
        )

    return text


def find_table(question, table_names):

    # Exact table mention first.

    for table in table_names:

        if re.search(
            rf"\b{re.escape(table.lower())}\b",
            question
        ):

            return table

    # Semantic aliases for common schemas.

    aliases = {
        "employee": [
            "employees",
            "employee",
            "staff",
            "workers",
            "people"
        ],
        "property": [
            "properties",
            "property",
            "houses",
            "house",
            "apartments",
            "apartment"
        ],
        "customer": [
            "customers",
            "customer",
            "clients",
            "client"
        ],
        "product": [
            "products",
            "product",
            "items",
            "item"
        ],
        "order": [
            "orders",
            "order",
            "purchases",
            "purchase"
        ]
    }

    for table in table_names:

        table_lower = table.lower()

        for category, words in aliases.items():

            if category in table_lower:

                if any(
                    word in question
                    for word in words
                ):

                    return table

    # Default to first table.

    return table_names[0]


def find_column(column_names, candidates):

    lower_map = {
        column.lower(): column
        for column in column_names
    }

    for candidate in candidates:

        if candidate.lower() in lower_map:

            return lower_map[
                candidate.lower()
            ]

    return None


def extract_person_name(question, q):

    # "What is Rahul's salary?"
    match = re.search(
        r"\b(?:what|who|show|give|tell|find|get)"
        r".{0,30}?"
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
        r"(?:['’]s)?\s+"
        r"(?:salary|pay|earnings?|wage|department|role|details|info)\b",
        question,
        flags=re.IGNORECASE
    )

    if match:

        name = match.group(1).strip()

        if name.lower() not in {
            "what",
            "who",
            "show",
            "give",
            "tell",
            "find",
            "get",
            "the"
        }:

            return name

    # "Salary of Rahul"
    match = re.search(
        r"\b(?:salary|pay|earnings?|wage|department|role|details|info)"
        r"\s+(?:of|for|about)\s+"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        question,
        flags=re.IGNORECASE
    )

    if match:

        return match.group(1).strip()

    # "Rahul salary"
    match = re.search(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
        r"\s+(?:salary|pay|earnings?|wage|department)\b",
        question,
        flags=re.IGNORECASE
    )

    if match:

        return match.group(1).strip()

    return None


def extract_city(q):

    # "employees in Hyderabad"
    # "employees from Mumbai"
    # "properties near Pune"

    match = re.search(
        r"\b(?:in|from|at|near)\s+"
        r"([a-zA-Z][a-zA-Z ]*)",
        q
    )

    if not match:

        return None

    value = match.group(1).strip()

    # Stop at another condition.

    value = re.split(
        r"\b(?:with|having|and|who|where|"
        r"salary|employees?|properties?|"
        r"earning|earn|above|below|under|over|"
        r"more|less|greater)\b",
        value,
        maxsplit=1
    )[0].strip()

    if not value:

        return None

    # Prevent department from being interpreted as city.

    if value.lower() in {
        "it",
        "hr",
        "finance",
        "sales",
        "marketing",
        "admin",
        "management"
    }:

        return None

    return value


def extract_department(q):

    # "IT employees"
    match = re.search(
        r"\b(it|hr|finance|sales|marketing|admin|"
        r"management|operations|engineering|support)"
        r"\s+employees?\b",
        q
    )

    if match:

        return match.group(1)

    # "employees in IT"
    match = re.search(
        r"\bemployees?\s+"
        r"(?:in|from|of)\s+"
        r"(it|hr|finance|sales|marketing|admin|"
        r"management|operations|engineering|support)\b",
        q
    )

    if match:

        return match.group(1)

    # "IT department"
    match = re.search(
        r"\b(it|hr|finance|sales|marketing|admin|"
        r"management|operations|engineering|support)"
        r"\s+department\b",
        q
    )

    if match:

        return match.group(1)

    # "department is IT"
    match = re.search(
        r"\bdepartment\s+"
        r"(?:is|equals?)\s+"
        r"(it|hr|finance|sales|marketing|admin|"
        r"management|operations|engineering|support)\b",
        q
    )

    if match:

        return match.group(1)

    return None


def find_requested_columns(q, column_names):

    requested = []

    for column in column_names:

        lower = column.lower()

        aliases = {
            "salary": [
                "salary",
                "pay",
                "earnings",
                "wage"
            ],
            "name": [
                "name",
                "employee name",
                "employee's name"
            ],
            "department": [
                "department",
                "dept"
            ],
            "city": [
                "city",
                "location"
            ],
            "rent": [
                "rent",
                "monthly rent"
            ],
            "price": [
                "price",
                "cost"
            ]
        }

        words = aliases.get(
            lower,
            [lower]
        )

        if any(
            re.search(
                rf"\b{re.escape(word)}\b",
                q
            )
            for word in words
        ):

            requested.append(column)

    # If user asks "what is salary",
    # return salary only.

    return requested


def find_group_by_column(q, column_names):

    for column in column_names:

        lower = column.lower()

        patterns = [
            f"each {lower}",
            f"every {lower}",
            f"per {lower}",
            f"by {lower}",
            f"{lower} wise",
            f"grouped by {lower}",
            f"group by {lower}"
        ]

        if any(
            pattern in q
            for pattern in patterns
        ):

            return column

    return None


def find_order_column(
    q,
    column_names,
    numeric_columns
):

    # Explicit "sort by salary"

    for column in column_names:

        lower = column.lower()

        if (
            f"sort by {lower}" in q
            or f"sorted by {lower}" in q
            or f"order by {lower}" in q
        ):

            return column

    # Highest / lowest usually applies
    # to salary, rent, price, amount, etc.

    if any(
        phrase in q
        for phrase in [
            "highest",
            "maximum",
            "max",
            "most expensive",
            "highest paid",
            "largest",
            "lowest",
            "minimum",
            "min",
            "cheapest",
            "lowest paid",
            "smallest"
        ]
    ):

        preferred = [
            "salary",
            "rent",
            "price",
            "amount",
            "total",
            "score",
            "quantity"
        ]

        for name in preferred:

            column = find_column(
                numeric_columns,
                [name]
            )

            if column:

                return column

        if numeric_columns:

            return numeric_columns[0]

    return None


def find_order_direction(q):

    if any(
        phrase in q
        for phrase in [
            "lowest",
            "minimum",
            "min",
            "cheapest",
            "lowest paid",
            "smallest",
            "ascending",
            "lowest to highest",
            "smallest to largest"
        ]
    ):

        return "ASC"

    return "DESC"


def find_limit(q):

    # "top 5"
    match = re.search(
        r"\btop\s+(\d+)\b",
        q
    )

    if match:

        return int(match.group(1))

    # "first 5"
    match = re.search(
        r"\bfirst\s+(\d+)\b",
        q
    )

    if match:

        return int(match.group(1))

    # "show 5"
    match = re.search(
        r"\bshow\s+(\d+)\b",
        q
    )

    if match:

        return int(match.group(1))

    # "top three"
    match = re.search(
        r"\btop\s+"
        r"(one|two|three|four|five|six|seven|eight|nine|ten)\b",
        q
    )

    if match:

        return NUMBER_WORDS[
            match.group(1)
        ]

    # "first three"
    match = re.search(
        r"\bfirst\s+"
        r"(one|two|three|four|five|six|seven|eight|nine|ten)\b",
        q
    )

    if match:

        return NUMBER_WORDS[
            match.group(1)
        ]

    return None


def is_single_extreme_query(q):

    return any(
        phrase in q
        for phrase in [
            "highest",
            "maximum",
            "max",
            "most expensive",
            "highest paid",
            "lowest",
            "minimum",
            "min",
            "cheapest",
            "lowest paid"
        ]
    )


def column_mentioned(column, q):

    # Exact word match prevents:
    # "id" matching inside "paid"

    return bool(
        re.search(
            rf"\b{re.escape(column)}\b",
            q
        )
    )


def is_numeric_column(
    column,
    numeric_columns
):

    return column in numeric_columns


def extract_number(value):

    cleaned = re.sub(
        r"[^\d.]",
        "",
        value
    )

    if not cleaned:

        return None

    try:

        number = float(cleaned)

        if number.is_integer():

            return int(number)

        return number

    except ValueError:

        return None


def clean_number(value):

    value = value.strip()

    # Remove commas and spaces inside numbers.
    value = re.sub(
        r"(?<=\d)[,\s]+(?=\d)",
        "",
        value
    )

    return extract_number(
        value
    )


def clean_text_value(value):

    value = value.strip()

    value = re.sub(
        r"^['\"]|['\"]$",
        "",
        value
    )

    return value


def escape_sql_value(value):

    return str(value).replace(
        "'",
        "''"
    )