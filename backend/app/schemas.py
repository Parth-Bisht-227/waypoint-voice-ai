from datetime import date
from pydantic import BaseModel, ConfigDict, Field, field_validator
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


class ApplicationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid") #  means that callers may send only the fields defines in this class
    destination: str = Field(max_length=80)
    travel_date: date

    @field_validator("destination")
    @classmethod
    def destination_must_not_be_blank(cls, value: str) -> str:
        destination = value.strip()
        if not destination:
            raise ValueError("Destination must not be blank")
        return destination

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


class VoiceTokenResponse(BaseModel):
    server_url: str
    participant_token: str
    room_name: str
    participant_identity: str
