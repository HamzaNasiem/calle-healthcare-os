from datetime import UTC, datetime

from sqlalchemy import event
from sqlalchemy.orm import Session

from src.core.logger import log
from src.models.appointment import Appointment
from src.models.call_log import CallLog
from src.models.patient import Patient


# SQLAlchemy event listener for Patient updates
@event.listens_for(Patient, 'after_update')
def cascade_patient_soft_delete(mapper, connection, target):
    """
    Prevents Soft-Delete Orphan Corruption.
    When a Patient is soft-deleted, we MUST cascade that soft-delete to all of their
    appointments and call logs. Otherwise, the system will continue sending SMS reminders
    to deleted patients and displaying phantom appointments on the calendar.
    """
    session = Session.object_session(target)
    # Check if this session update is actually setting is_deleted = True
    if session.is_modified(target, include_collections=False):
        history = sqlalchemy.orm.attributes.get_history(target, 'is_deleted')
        
        # If it was False and is now True
        if history.added and history.added[0] is True and history.deleted and history.deleted[0] is False:
            now = datetime.now(UTC)
            deleted_by = target.deleted_by
            
            # Cascade to Appointments
            try:
                # We use raw connection execution to avoid recursive session flush issues during after_update
                connection.execute(
                    Appointment.__table__.update().
                    where(Appointment.patient_id == target.id).
                    where(Appointment.is_deleted == False).
                    values(is_deleted=True, deleted_at=now, deleted_by=deleted_by)
                )
                
                # Cascade to Call Logs
                connection.execute(
                    CallLog.__table__.update().
                    where(CallLog.patient_id == target.id).
                    where(CallLog.is_deleted == False).
                    values(is_deleted=True, deleted_at=now, deleted_by=deleted_by)
                )
                
                log.info(f"Cascaded soft-delete for patient {target.id} to their appointments and call logs.")
            except Exception as e:
                log.error(f"Failed to cascade soft-delete for patient {target.id}: {str(e)}")

import sqlalchemy.orm.attributes
