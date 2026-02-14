from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, List
from datetime import date
import uuid

class SessionType(Enum):
    REGULAR = "정기"
    VACATION = "방중"

class SemesterType(Enum):
    REGULAR = "정기학기" # Base FP 1.5
    VACATION = "방중학기" # Base FP 1.0

class ActivityType(Enum):
    ATTENDANCE = "출석"
    COMMENT = "댓글"

class AttendanceStatus(Enum):
    PRESENT = "출석"
    LATE = "지각"
    ABSENT = "결석"
    LATE_WITH_EXCUSE = "사유서 지각"
    EARLY_LEAVE_WITH_EXCUSE = "사유서 조퇴"
    F = "F"
    OFFICIAL_EVENT = "공결"
    
    # Specific to comments
    WRITTEN = "작성"
    NOT_SUBMITTED = "미작성"
    DEBATER = "토론자"
    PRESENTER = "발제자"
    EARLY_LEAVE_AS_ABSENT = "조퇴인데 결석(F 0.5회 사용)" # Deprecated, will be migrated to F
    
    # No Fine, No FP
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"

@dataclass
class Session:
    date: str  # YYYY-MM-DD
    type: SessionType
    title: str
    activities: list[ActivityType] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class AttendanceRecord:
    member_name: str
    session_date: str
    activity_type: ActivityType
    status: AttendanceStatus
    late_minutes: int = 0
    session_id: str = ""

@dataclass
class Semester:
    name: str # e.g. "25-1학기 정기"
    type: SemesterType
    sessions: List[Session] = field(default_factory=list)
    attendance_records: List[AttendanceRecord] = field(default_factory=list)
    debater_names: List[str] = field(default_factory=list) # Members who attended debate in this semester
    members: List['Member'] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class Member:
    name: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    is_active: bool = True
    # attended_debate removed from here as it's now per-semester (in Semester.debater_names)
