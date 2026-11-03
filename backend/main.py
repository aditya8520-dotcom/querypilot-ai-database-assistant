from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import re

from database import get_connection, get_database_schema
from gemini import generate_sql
from validator import validate_sql


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="AI Voice Database Assistant",
    description="Voice-first natural language database assistant",
    version="3.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# SESSIONS
# ============================================================

database_sessions = {}
conversation_sessions = {}


# ============================================================
# REQUEST MODELS
# ============================================================

class DatabaseConnectionRequest(BaseModel):
    host: str
    port: int = 3306
    database: str
    username: str
    password: str


class QueryRequest(BaseModel):
    question: str
    session_id: str | None = None


class GenerateSQLRequest(BaseModel):
    question: str
    session_id: str | None = None


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():

    return {
        "status": "success",
        "message": "AI Voice Database Assistant is running!"
    }


# ============================================================
# CONNECT DATABASE
# ============================================================

@app.post("/connect-database")
def connect_database(request: DatabaseConnectionRequest):

    connection = None

    try:

        print("\n========================================")
        print("DATABASE CONNECTION")
        print("========================================")

        print("Host:", request.host)
        print("Database:", request.database)

        # ----------------------------------------------------
        # CONNECT
        # ----------------------------------------------------

        connection = get_connection(
            host=request.host,
            port=request.port,
            user=request.username,
            password=request.password,
            database=request.database
        )

        # ----------------------------------------------------
        # READ ACTUAL SCHEMA
        # ----------------------------------------------------

        schema = get_database_schema(connection)

        connection.close()
        connection = None

        # ----------------------------------------------------
        # CREATE SESSION
        # ----------------------------------------------------

        session_id = str(uuid.uuid4())

        database_sessions[session_id] = {
            "host": request.host,
            "port": request.port,
            "user": request.username,
            "password": request.password,
            "database": request.database,
            "schema": schema
        }

        conversation_sessions[session_id] = []

        tables = list(schema.keys())

        print("Connected successfully")
        print("Session:", session_id)
        print("Tables:", tables)

        return {
            "status": "success",
            "message": "Database connected successfully!",
            "session_id": session_id,
            "database": request.database,
            "tables": tables,
            "schema": schema
        }

    except Exception as error:

        print("DATABASE ERROR:", error)

        return {
            "status": "error",
            "message": (
                "Could not connect to the database. "
                "Check the connection details."
            )
        }

    finally:

        if connection:

            try:
                connection.close()

            except Exception:
                pass
# ============================================================
# DISCONNECT DATABASE
# ============================================================

@app.post("/disconnect-database")
def disconnect_database(session_id: str):

    if not session_id:
        return {
            "status": "error",
            "message": "Session ID is required."
        }

    # Remove database session
    database_sessions.pop(session_id, None)

    # Remove conversation history
    conversation_sessions.pop(session_id, None)

    print("\n========================================")
    print("DATABASE DISCONNECTED")
    print("========================================")
    print("Session:", session_id)

    return {
        "status": "success",
        "message": "Database disconnected successfully."
    }


# ============================================================
# GET DATABASE SESSION
# ============================================================

def get_database_session(session_id):

    if not session_id:
        return None

    return database_sessions.get(session_id)


# ============================================================
# GET CONVERSATION
# ============================================================

def get_conversation(session_id):

    if session_id not in conversation_sessions:

        conversation_sessions[session_id] = []

    return conversation_sessions[session_id]


# ============================================================
# CLEAN SQL
# ============================================================

def clean_sql(sql):

    if not sql:
        return ""

    sql = str(sql).strip()

    # Remove markdown SQL fences

    sql = re.sub(
        r"^```sql\s*",
        "",
        sql,
        flags=re.IGNORECASE
    )

    sql = re.sub(
        r"^```\s*",
        "",
        sql
    )

    sql = re.sub(
        r"\s*```$",
        "",
        sql
    )

    sql = sql.strip()

    # Remove trailing semicolon

    sql = sql.rstrip(";").strip()

    return sql


# ============================================================
# CHECK SELECT QUERY
# ============================================================

def is_select_query(sql):

    if not sql:
        return False

    normalized = sql.strip().lower()

    # --------------------------------------------------------
    # Must start with SELECT or WITH
    # --------------------------------------------------------

    if not (
        normalized.startswith("select ")
        or normalized.startswith("select\n")
        or normalized.startswith("with ")
    ):
        return False

    # --------------------------------------------------------
    # Dangerous SQL keywords
    # --------------------------------------------------------

    dangerous = [
        "insert ",
        "update ",
        "delete ",
        "drop ",
        "alter ",
        "create ",
        "truncate ",
        "rename ",
        "grant ",
        "revoke ",
        "call ",
        "execute "
    ]

    for keyword in dangerous:

        if keyword in normalized:
            return False

    # --------------------------------------------------------
    # Only one SQL statement
    # --------------------------------------------------------

    if ";" in normalized:
        return False

    return True


# ============================================================
# EXECUTE SQL
# ============================================================

def execute_sql(database_config, sql):

    connection = None
    cursor = None

    try:

        connection = get_connection(
            host=database_config["host"],
            port=database_config["port"],
            user=database_config["user"],
            password=database_config["password"],
            database=database_config["database"]
        )

        cursor = connection.cursor(
            dictionary=True
        )

        print("\n========================================")
        print("EXECUTING SQL")
        print("========================================")

        print(sql)

        cursor.execute(sql)

        rows = cursor.fetchall()

        # ----------------------------------------------------
        # GET COLUMN NAMES
        # ----------------------------------------------------

        if cursor.description:

            columns = [
                description[0]
                for description in cursor.description
            ]

        else:

            columns = []

        return {
            "rows": rows,
            "columns": columns,
            "row_count": len(rows)
        }

    finally:

        if cursor:

            cursor.close()

        if connection:

            connection.close()


# ============================================================
# GENERIC ANSWER
# ============================================================

def create_answer(question, result):

    rows = result.get("rows", [])
    columns = result.get("columns", [])

    # --------------------------------------------------------
    # NO RESULTS
    # --------------------------------------------------------

    if not rows:

        return (
            "I couldn't find any records matching "
            "your question."
        )

    # --------------------------------------------------------
    # ONE VALUE
    # --------------------------------------------------------

    if len(rows) == 1 and len(columns) == 1:

        column = columns[0]
        value = rows[0].get(column)

        if value is None:

            return "The result is empty."

        return (
            f"The result for your question is "
            f"{value}."
        )

    # --------------------------------------------------------
    # ONE RECORD
    # --------------------------------------------------------

    if len(rows) == 1:

        parts = []

        for column in columns:

            value = rows[0].get(column)

            if value is not None:

                parts.append(
                    f"{column}: {value}"
                )

        if parts:

            return (
                "I found one matching record:\n\n"
                + "\n".join(parts)
            )

    # --------------------------------------------------------
    # MULTIPLE RECORDS
    # --------------------------------------------------------

    return (
        f"I found {len(rows)} matching "
        f"records."
    )


# ============================================================
# DETECT CHART
# ============================================================

def detect_chart(rows, columns):

    if not rows or len(rows) < 2:

        return {
            "type": "table"
        }

    if len(columns) < 2:

        return {
            "type": "table"
        }

    # --------------------------------------------------------
    # Find numeric columns
    # --------------------------------------------------------

    numeric_columns = []

    for column in columns:

        for row in rows:

            value = row.get(column)

            if isinstance(value, (int, float)):

                numeric_columns.append(column)

                break

    # --------------------------------------------------------
    # Two columns:
    # one category + one numeric
    # --------------------------------------------------------

    if (
        len(columns) == 2
        and len(numeric_columns) == 1
    ):

        numeric_column = numeric_columns[0]

        category_column = (
            columns[0]
            if columns[0] != numeric_column
            else columns[1]
        )

        return {
            "type": "bar",
            "x": category_column,
            "y": numeric_column
        }

    # --------------------------------------------------------
    # Multiple columns with numeric value
    # --------------------------------------------------------

    if len(numeric_columns) >= 1:

        return {
            "type": "bar",
            "x": columns[0],
            "y": numeric_columns[0]
        }

    # --------------------------------------------------------
    # Default
    # --------------------------------------------------------

    return {
        "type": "table"
    }


# ============================================================
# GENERATE SQL ONLY
# ============================================================

@app.post("/generate-sql")
def generate_sql_only(request: GenerateSQLRequest):

    question = request.question.strip()

    # --------------------------------------------------------
    # EMPTY QUESTION
    # --------------------------------------------------------

    if not question:

        return {
            "status": "error",
            "message": "Please enter a question."
        }

    # --------------------------------------------------------
    # GET DATABASE SESSION
    # --------------------------------------------------------

    database_config = get_database_session(
        request.session_id
    )

    if not database_config:

        return {
            "status": "error",
            "message": "Please connect your database first."
        }

    schema = database_config["schema"]

    # --------------------------------------------------------
    # GENERATE SQL
    # --------------------------------------------------------

    try:

        print("\n========================================")
        print("GENERATE SQL ONLY")
        print("========================================")

        print("QUESTION:")
        print(question)

        sql = generate_sql(
            question,
            schema
        )

        sql = clean_sql(sql)

        print("\nGENERATED SQL:")
        print(sql)

    except Exception as error:

        print(
            "SQL GENERATION ERROR:",
            error
        )

        return {
            "status": "error",
            "generated_sql": None,
            "message": (
                "I could not generate SQL "
                "for that question."
            )
        }

    # --------------------------------------------------------
    # SAFETY CHECK
    # --------------------------------------------------------

    if not is_select_query(sql):

        return {
            "status": "rejected",
            "generated_sql": sql,
            "message": (
                "For safety, only read-only "
                "SELECT queries are allowed."
            )
        }

    # --------------------------------------------------------
    # VALIDATE AGAINST ACTUAL SCHEMA
    # --------------------------------------------------------

    try:

        is_valid, validation_message = validate_sql(
            sql,
            schema
        )

        if not is_valid:

            return {
                "status": "rejected",
                "generated_sql": sql,
                "message": validation_message
            }

    except Exception as error:

        print(
            "VALIDATION ERROR:",
            error
        )

        return {
            "status": "error",
            "generated_sql": sql,
            "message": "SQL validation failed."
        }

    # --------------------------------------------------------
    # DO NOT EXECUTE
    # --------------------------------------------------------

    return {
        "status": "success",
        "question": question,
        "generated_sql": sql,
        "database": database_config["database"],
        "session_id": request.session_id
    }


# ============================================================
# ASK DATABASE
# ============================================================

@app.post("/query")
def query_database(request: QueryRequest):

    question = request.question.strip()

    # --------------------------------------------------------
    # EMPTY QUESTION
    # --------------------------------------------------------

    if not question:

        return {
            "status": "error",
            "message": "Please ask a question."
        }

    # --------------------------------------------------------
    # GET DATABASE SESSION
    # --------------------------------------------------------

    database_config = get_database_session(
        request.session_id
    )

    if not database_config:

        return {
            "status": "error",
            "message": "Please connect your database first."
        }

    # --------------------------------------------------------
    # GET ACTUAL DATABASE SCHEMA
    # --------------------------------------------------------

    schema = database_config["schema"]

    # --------------------------------------------------------
    # GET CONVERSATION
    # --------------------------------------------------------

    conversation = get_conversation(
        request.session_id
    )

    # --------------------------------------------------------
    # GENERATE SQL
    # --------------------------------------------------------

    try:

        print("\n========================================")
        print("USER QUESTION")
        print("========================================")

        print(question)

        print("\nAVAILABLE TABLES:")
        print(list(schema.keys()))

        sql = generate_sql(
            question,
            schema
        )

        sql = clean_sql(sql)

        print("\n========================================")
        print("GENERATED SQL")
        print("========================================")

        print(sql)

    except Exception as error:

        print(
            "SQL GENERATION ERROR:",
            error
        )

        return {
            "status": "error",
            "generated_sql": None,
            "message": (
                "I could not generate SQL "
                "for that question."
            )
        }

    # ========================================================
    # SAFETY CHECK
    # ========================================================

    if not is_select_query(sql):

        return {
            "status": "rejected",
            "generated_sql": sql,
            "message": (
                "For safety, only read-only "
                "SELECT queries are allowed."
            )
        }

    # ========================================================
    # SQL VALIDATION
    # ========================================================

    try:

        is_valid, validation_message = validate_sql(
            sql,
            schema
        )

        if not is_valid:

            return {
                "status": "rejected",
                "generated_sql": sql,
                "message": validation_message
            }

    except Exception as error:

        print(
            "VALIDATION ERROR:",
            error
        )

        return {
            "status": "error",
            "generated_sql": sql,
            "message": "SQL validation failed."
        }

    # ========================================================
    # EXECUTE SQL
    # ========================================================

    try:

        result = execute_sql(
            database_config,
            sql
        )

    except Exception as error:

        print(
            "EXECUTION ERROR:",
            error
        )

        return {
            "status": "database_error",
            "generated_sql": sql,
            "message": f"Database error: {error}"
        }

    # ========================================================
    # GENERIC AI ANSWER
    # ========================================================

    answer = create_answer(
        question,
        result
    )

    # ========================================================
    # CHART DETECTION
    # ========================================================

    chart = detect_chart(
        result["rows"],
        result["columns"]
    )

    # ========================================================
    # SAVE CONVERSATION
    # ========================================================

    conversation.append({

        "question": question,

        "sql": sql,

        "columns": result["columns"],

        "row_count": result["row_count"]

    })

    # Keep only last 10 conversations

    if len(conversation) > 10:

        conversation.pop(0)

    # ========================================================
    # PRINT RESULT
    # ========================================================

    print("\n========================================")
    print("QUERY RESULT")
    print("========================================")

    print("Rows:", result["row_count"])
    print("Columns:", result["columns"])

    # ========================================================
    # RETURN RESULT
    # ========================================================

    return {

        "status": "success",

        "question": question,

        "generated_sql": sql,

        "database":
            database_config["database"],

        "session_id":
            request.session_id,

        "columns":
            result["columns"],

        "rows":
            result["rows"],

        "row_count":
            result["row_count"],

        "answer":
            answer,

        "chart":
            chart,

        "conversation":
            conversation
    }


# ============================================================
# GET SCHEMA
# ============================================================

@app.get("/schema/{session_id}")
def get_schema(session_id: str):

    database_config = get_database_session(
        session_id
    )

    if not database_config:

        return {
            "status": "error",
            "message": "Database session not found."
        }

    return {

        "status": "success",

        "database":
            database_config["database"],

        "tables":
            list(
                database_config["schema"].keys()
            ),

        "schema":
            database_config["schema"]
    }


# ============================================================
# GET HISTORY
# ============================================================

@app.get("/history/{session_id}")
def get_history(session_id: str):

    return {

        "status": "success",

        "history":
            conversation_sessions.get(
                session_id,
                []
            )
    }


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )