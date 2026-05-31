from __future__ import annotations

import csv
import io
import logging
from typing import List, Tuple, Type, TypeVar

from pydantic import BaseModel, ValidationError
from werkzeug.datastructures import FileStorage

from app.schemas import RowError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def parse_csv_upload(
    file: FileStorage,
    schema: Type[T],
    *,
    encoding: str = "utf-8-sig",
) -> Tuple[List[T], List[RowError]]:
    """
    Args:
        file:     Werkzeug FileStorage from ``request.files``.
        schema:   A Pydantic BaseModel subclass whose fields map to CSV columns.
        encoding: Character encoding to use when decoding the file bytes.

    Returns:
        A 2-tuple ``(valid_rows, row_errors)`` where
        * ``valid_rows``  is a list of validated *schema* instances.
        * ``row_errors``  is a list of :class:`~app.schemas.RowError` objects
          describing every row that did not pass validation.
    Raises:
        ValueError: If the uploaded file is empty or contains no data rows.
    """
    raw_bytes: bytes = file.read()

    if not raw_bytes.strip():
        raise ValueError("The uploaded CSV file is empty.")

    text = raw_bytes.decode(encoding)
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise ValueError("Could not read CSV headers.  Ensure the file has a header row.")

    reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]

    valid_rows: List[T] = []
    row_errors: List[RowError] = []

    for row_index, raw_row in enumerate(reader, start=1):
        # Replace empty strings with None so optional fields work correctly.
        print(raw_row.items())
        cleaned = {k: (v if v != "" else None) for k, v in raw_row.items()}
        try:
            cleaned['row'] = row_index
            validated = schema.model_validate(cleaned)
            valid_rows.append(validated)
        except ValidationError as exc:
            messages = [
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                for err in exc.errors()
            ]
            row_errors.append(RowError(row=row_index, errors=messages))
            logger.debug("Row %d failed validation: %s", row_index, messages)

    if not valid_rows and not row_errors:
        raise ValueError("The CSV file contains a header but no data rows.")

    return valid_rows, row_errors
