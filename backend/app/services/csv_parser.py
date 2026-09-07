import csv
import io
import re
from typing import Any, Dict, List, Tuple
from app.models.csv_table import ColumnDefinition


RESERVED_SQL_KEYWORDS = {
    "select", "from", "where", "group", "order", "by", "having", "limit",
    "offset", "table", "user", "column", "primary", "foreign", "key",
    "insert", "update", "delete", "create", "drop", "alter", "index",
    "join", "left", "right", "full", "inner", "outer", "on", "as",
    "and", "or", "not", "null", "is", "in", "like", "between", "case", "when"
}


def sanitize_column_name(raw_name: str, existing_names: set) -> str:
    """
    Sanitize a raw CSV header string into a valid, safe PostgreSQL identifier:
    - Lowercase alphanumeric and underscores only.
    - Strips special symbols like $, %, (, ), etc.
    - Prepends 'col_' if starting with a digit or reserved SQL keyword.
    - Handles duplicates by appending a numeric suffix.
    """
    cleaned = raw_name.strip().lower()
    # Replace non-alphanumeric characters with underscores
    cleaned = re.sub(r"[^a-z0-9_]+", "_", cleaned)
    # Strip leading/trailing underscores
    cleaned = cleaned.strip("_")

    if not cleaned:
        cleaned = "col"

    if cleaned[0].isdigit() or cleaned in RESERVED_SQL_KEYWORDS:
        cleaned = f"col_{cleaned}"

    # Ensure uniqueness
    candidate = cleaned
    counter = 2
    while candidate in existing_names:
        candidate = f"{cleaned}_{counter}"
        counter += 1

    existing_names.add(candidate)
    return candidate


def infer_sql_type(sample_values: List[str]) -> str:
    """
    Infer PostgreSQL data type from non-empty sample values.
    Returns: 'INTEGER', 'NUMERIC', 'BOOLEAN', or 'TEXT'.
    """
    NULL_MARKERS = {"-", "n/a", "na", "null", "none", "nan", "nil", ""}
    non_null_samples = [v.strip() for v in sample_values if v and v.strip().lower() not in NULL_MARKERS]
    if not non_null_samples:
        return "TEXT"

    # Check BOOLEAN
    bool_values = {"true", "false", "yes", "no", "1", "0", "t", "f"}
    if all(v.lower() in bool_values for v in non_null_samples):
        return "BOOLEAN"

    # Check INTEGER
    is_int = True
    for v in non_null_samples:
        cleaned_v = v.replace(",", "").strip()
        if not re.match(r"^-?\d+$", cleaned_v):
            is_int = False
            break
    if is_int:
        return "INTEGER"

    # Check NUMERIC (float/currency/percentage)
    is_numeric = True
    for v in non_null_samples:
        cleaned_v = v.replace(",", "").replace("$", "").replace("%", "").strip()
        if cleaned_v.startswith("(") and cleaned_v.endswith(")"):
            cleaned_v = f"-{cleaned_v[1:-1]}"
        try:
            float(cleaned_v)
        except ValueError:
            is_numeric = False
            break
    if is_numeric:
        return "NUMERIC"

    return "TEXT"


def cast_value_for_sql(val: Any, sql_type: str) -> Any:
    """Cast a raw string value to the appropriate Python type matching SQL data type."""
    if val is None:
        return None
    s = str(val).strip()
    if s == "" or s.lower() in ("-", "null", "none", "nan", "n/a", "na", "nil"):
        return None

    if sql_type == "INTEGER":
        try:
            return int(s.replace(",", "").strip())
        except Exception:
            return None

    if sql_type == "NUMERIC":
        try:
            cleaned = s.replace(",", "").replace("$", "").replace("%", "").strip()
            if cleaned.startswith("(") and cleaned.endswith(")"):
                cleaned = f"-{cleaned[1:-1]}"
            return float(cleaned)
        except Exception:
            return None

    if sql_type == "BOOLEAN":
        return s.lower() in ("true", "yes", "1", "t")

    return s


def parse_csv_bytes(csv_bytes: bytes) -> Tuple[List[ColumnDefinition], List[Dict[str, Any]], List[str]]:
    """
    Parse CSV bytes with encoding detection:
    1. Extracts headers and creates sanitized ColumnDefinitions with inferred SQL types.
    2. Returns parsed raw row dictionaries with original column keys.
    3. Serializes each row into a natural-language sentence for Path A semantic embedding.
    """
    # Detect encoding
    text_content = ""
    for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            text_content = csv_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if not text_content:
        raise ValueError("Unable to decode CSV file with supported encodings.")

    # Read CSV
    f = io.StringIO(text_content)
    reader = csv.reader(f)
    try:
        raw_headers = next(reader)
    except StopIteration:
        raise ValueError("CSV file is completely empty.")

    # Handle duplicate/blank headers
    existing_sanitized = set()
    col_defs: List[ColumnDefinition] = []
    header_mapping: List[Tuple[str, str]] = []  # (original, sanitized)

    for idx, raw_h in enumerate(raw_headers):
        raw_name = raw_h.strip() if raw_h.strip() else f"column_{idx + 1}"
        sanitized = sanitize_column_name(raw_name, existing_sanitized)
        header_mapping.append((raw_name, sanitized))

    # Read all rows
    raw_rows: List[List[str]] = []
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue  # skip empty lines
        # Pad row if shorter than headers
        if len(row) < len(raw_headers):
            row = row + [""] * (len(raw_headers) - len(row))
        raw_rows.append(row[: len(raw_headers)])

    if not raw_rows:
        raise ValueError("CSV contains headers but no data rows.")

    # Infer SQL types per column
    for col_idx, (orig_name, sanitized_name) in enumerate(header_mapping):
        col_samples = [row[col_idx] for row in raw_rows[:100]]  # sample up to 100 rows
        inferred_type = infer_sql_type(col_samples)
        col_defs.append(
            ColumnDefinition(
                name=sanitized_name,
                original_name=orig_name,
                data_type=inferred_type,
            )
        )

    # 1. Build row dictionaries with sanitized keys and cast values
    parsed_rows: List[Dict[str, Any]] = []
    # 2. Build natural language sentence representations (Path A)
    serialized_sentences: List[str] = []

    for row_idx, row in enumerate(raw_rows):
        row_dict: Dict[str, Any] = {}
        sentence_parts: List[str] = []

        for col_idx, col_def in enumerate(col_defs):
            raw_val = row[col_idx]
            cast_val = cast_value_for_sql(raw_val, col_def.data_type)
            row_dict[col_def.name] = cast_val

            if raw_val and raw_val.strip():
                sentence_parts.append(f"{col_def.original_name} is {raw_val.strip()}")

        parsed_rows.append(row_dict)

        # Row natural language serialization
        sentence = f"Row {row_idx + 1}: " + "; ".join(sentence_parts) + "."
        serialized_sentences.append(sentence)

    return col_defs, parsed_rows, serialized_sentences
