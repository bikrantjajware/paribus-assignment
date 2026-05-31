from __future__ import annotations

from app.db import DBHospital
from app.extensions import hospital_client


def create_hospital(hospital: HospitalRow, batch_id: str, status: HospitalStatus) -> int:
    print(f'hospital_client {hospital_client}')
    created_hospital = hospital_client.create_hospital(hospital=hospital, batch_id=batch_id)
    print(f'created hospital response {created_hospital}')
    db_hospital = DBHospital(
                        id=created_hospital["id"],
                        name=created_hospital["name"],
                        address=created_hospital["address"],
                        batch_id=created_hospital["creation_batch_id"],
                        status=status,
                        created_at=created_hospital["created_at"],
                        row=hospital.row,
                        active=created_hospital["active"],
                        phone=created_hospital["phone"])
    db_hospital.save()
    return db_hospital