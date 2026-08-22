from datetime import date
from pydantic import BaseModel
from .models import (
    ApplicationStatus,
    HandoffReason,
    HandoffStatus,
)

# pydantic code logic...

# this means: Whenever our API claims to return an application,
#  this is the expected structure.
class ApplicationResponse(BaseModel):
    application_id: str
    destination: str
    status: ApplicationStatus
    travel_date: date

class MissingDocumentsResponse(BaseModel):
    application_id: str
    missing_documents: list[str]
     
class TravelDateUpdateRequest(BaseModel):
    new_date: date
    idempotency_key: str

class TravelDateUpdateResponse(BaseModel):
    application_id: str
    old_date: date
    new_date: date
    changed: bool  # this will be useful later to check for retry, idempotency logic...

#  pydantic gurantees, that the data is as per the mentioned format


class HandoffRequest(BaseModel):
    reason_code: HandoffReason

class HandoffResponse(BaseModel):
    handoff_id: str
    application_id: str
    reason_code: HandoffReason
    status: HandoffStatus