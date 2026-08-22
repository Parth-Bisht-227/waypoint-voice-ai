from enum import Enum

# model --> structured representation of data/domain entities...

#  enum -> restricts possible values, 
#  while str -> helps us make those values convenient for APIs/ JSON format
class ApplicationStatus(str, Enum):
    PROCESSING = "processing"
    APPROVED = "approved"
    BLOCKED = "blocked"
    ACTION_REQUIRED = "action_required"



class HandoffReason(str, Enum):
    USER_REQUEST = "user_request"
    UNSUPPORTED_REQUEST = "unsupported_request"
    REPEATED_CLARIFICATION_FAILURE = "repeated_clarification_failure"
    BACKEND_FAILURE = "backend_failure"
    STATE_CONFLICT = "state_conflict"
    CRITICAL_ENTITY_UNCERTAIN = "critical_entity_uncertain"

class HandoffStatus(str, Enum):
    REQUESTED = "requested"