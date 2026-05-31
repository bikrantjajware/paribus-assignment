from __future__ import annotations

import logging
import uuid

from flask import current_app
from flask import Blueprint, jsonify, request
from werkzeug.datastructures import FileStorage

from app.schemas import BulkUploadResponse, HospitalRow, HospitalStatus
from app.utils import parse_csv_upload
from app.hospital_utils import create_hospital

logger = logging.getLogger(__name__)

hospitals_bp = Blueprint("hospitals", __name__, url_prefix="/hospitals")

_ALLOWED_CONTENT_TYPES = {"text/csv", "application/csv"}


@hospitals_bp.route("/bulk", methods=["POST"])
def bulk_upload():
    """
    Request: accepts a Multipart form data with CSV file with Columns name, address, phone (phone is optional)
    Response: Processing status with batch ID and progress information
    """
    if "file" not in request.files:
        return jsonify({"error": "No file part in request.  Send the CSV as 'file' field."}), 400

    uploaded_file: FileStorage = request.files["file"]

    if uploaded_file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    content_type = (uploaded_file.content_type or "").split(";")[0].strip().lower()
    filename_lower = (uploaded_file.filename or "").lower()

    if content_type not in _ALLOWED_CONTENT_TYPES and not filename_lower.endswith(".csv"):
        return (
            jsonify({"error": f"Unsupported file type '{content_type}'.  Please upload a CSV file."}),
            415,
        )
    try:
        valid_rows, row_errors = parse_csv_upload(uploaded_file, HospitalRow)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except UnicodeDecodeError:
        return (
            jsonify({"error": "Could not decode the file.  Ensure it is saved as UTF-8."}),
            400,
        )
    total = len(valid_rows) + len(row_errors)
    print(total)
    print(valid_rows)
    logger.info(
        "bulk_upload: processed %d rows – %d valid, %d invalid",
        total,
        len(valid_rows),
        len(row_errors),
    )
    batch_id = str(uuid.uuid4())
    status = HospitalStatus.CREATED.value
    created_hospitals = []
    for hospital in valid_rows:
        try:
            created_hospital = create_hospital(hospital, batch_id, status)
            created_hospitals.append({
                'row': created_hospital.row,
                'hospital_id': created_hospital.id,
                'name': created_hospital.name,
                'status': created_hospital.status,
                'batch_id': batch_id,
            })
        except Exception as e:
            logger.exception(f'failed to create store for hospital {hospital}' + str(e))
            return jsonify({"error": "something went wrong while creating store"}), 500

    response = BulkUploadResponse(
        batch_id=batch_id,
        total_hospitals=total,
        processed_hospitals=len(valid_rows),
        failed_hospitals=len(row_errors),
        processing_time_seconds=0,
        batch_activated=False,
        hospitals=created_hospitals,
    )

    return jsonify(response.model_dump()), 200
