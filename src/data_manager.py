import json
import os
import sys
import uuid

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import List, Dict, Optional
from src.models import Member, Session, AttendanceRecord, SessionType, ActivityType, AttendanceStatus, Semester, SemesterType

class DataManager:
    def __init__(self, data_file="database.json"):
        self.data_file = data_file
        self.members: List[Member] = []
        self.semesters: List[Semester] = []
        self.last_modified = 0
        self.load_data()

    def load_data(self):
        if not os.path.exists(self.data_file):
            return

        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Load Global Members (Legacy support)
                global_members = []
                for m_data in data.get('members', []):
                    m_data.pop('attended_debate', None) # Cleanup legacy
                    global_members.append(Member(**m_data))
                
                self.semesters = []
                
                # Check if data has 'semesters' key (New Format)
                if 'semesters' in data:
                    for s_data in data['semesters']:
                        sessions = []
                        for sess in s_data.get('sessions', []):
                            sess['type'] = SessionType(sess['type'])
                            sess['activities'] = [ActivityType(a) for a in sess['activities']]
                            sessions.append(Session(**sess))
                            
                        records = []
                        for rec in s_data.get('attendance_records', []):
                            rec['activity_type'] = ActivityType(rec['activity_type'])
                            # Legacy migration
                            if rec['status'] == '제출':
                                rec['status'] = AttendanceStatus.WRITTEN
                            elif rec['status'] == '토론자':
                                rec['status'] = AttendanceStatus.DEBATER
                            elif rec['status'] == '발제자':
                                rec['status'] = AttendanceStatus.PRESENTER
                            else:
                                rec['status'] = AttendanceStatus(rec['status'])
                            records.append(AttendanceRecord(**rec))
                        
                        # Load Semester Members
                        sem_members = []
                        if 'members' in s_data:
                            for sm_data in s_data['members']:
                                sem_members.append(Member(**sm_data))
                        else:
                            # Migration: If no members in semester, copy from global
                            import copy
                            sem_members = copy.deepcopy(global_members)

                        semester = Semester(
                            name=s_data['name'],
                            type=SemesterType(s_data['type']),
                            sessions=sessions,
                            attendance_records=records,
                            debater_names=s_data.get('debater_names', []),
                            members=sem_members,
                            id=s_data.get('id', str(uuid.uuid4()))
                        )
                        self.semesters.append(semester)
                
                else:
                    # Legacy Format - Migration
                    print("Migrating legacy data to Semester format...")
                    
                    sessions = []
                    for s in data.get('sessions', []):
                        s['type'] = SessionType(s['type'])
                        s['activities'] = [ActivityType(a) for a in s['activities']]
                        sessions.append(Session(**s))
                    
                    records = []
                    for r in data.get('attendance_records', []):
                        r['activity_type'] = ActivityType(r['activity_type'])
                        r['status'] = AttendanceStatus(r['status'])
                        records.append(AttendanceRecord(**r))
                        
                    for rec in records:
                        if not rec.session_id:
                            matched_session = None
                            for s in sessions:
                                if s.date == rec.session_date and rec.activity_type in s.activities:
                                    matched_session = s
                                    break
                            if matched_session:
                                rec.session_id = matched_session.id
                    
                    import copy
                    legacy_semester = Semester(
                        name="2024-2 이전 데이터",
                        type=SemesterType.REGULAR,
                        sessions=sessions,
                        attendance_records=records,
                        debater_names=[],
                        members=copy.deepcopy(global_members)
                    )
                    self.semesters.append(legacy_semester)

        except Exception as e:
            print(f"Error loading data: {e}")
            import traceback
            traceback.print_exc()

    def save_data(self):
        data = {
            'semesters': []
        }
        
        for sem in self.semesters:
            sem_data = {
                'id': sem.id,
                'name': sem.name,
                'type': sem.type.value,
                'debater_names': sem.debater_names,
                'members': [m.__dict__ for m in sem.members],
                'sessions': [
                    {
                        'id': s.id,
                        'date': s.date,
                        'type': s.type.value,
                        'title': s.title,
                        'activities': [a.value for a in s.activities]
                    } for s in sem.sessions
                ],
                'attendance_records': [
                    {
                        'member_name': r.member_name,
                        'session_date': r.session_date,
                        'activity_type': r.activity_type.value,
                        'status': r.status.value,
                        'late_minutes': r.late_minutes,
                        'session_id': r.session_id
                    } for r in sem.attendance_records
                ]
            }
            data['semesters'].append(sem_data)
        
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            import time
            self.last_modified = time.time()
        except Exception as e:
            print(f"Error saving data: {e}")

    # --- Methods ---

    def add_member(self, semester_id: str, name: str):
        sem = self.get_semester(semester_id)
        if not sem: return
        
        if not any(m.name == name for m in sem.members):
            sem.members.append(Member(name=name))
            self.save_data()
            
    def remove_member(self, semester_id: str, name: str):
        sem = self.get_semester(semester_id)
        if not sem: return
        
        sem.members = [m for m in sem.members if m.name != name]
        self.save_data()

    def add_semester(self, name: str, type: SemesterType):
        self.semesters.append(Semester(name=name, type=type))
        self.save_data()

    def remove_semester(self, semester_id: str):
        self.semesters = [s for s in self.semesters if s.id != semester_id]
        self.save_data()

    def get_semester(self, semester_id: str) -> Optional[Semester]:
        for s in self.semesters:
            if s.id == semester_id:
                return s
        return None

    # Operations within a Semester
    
    def set_debater_status(self, semester_id: str, member_name: str, is_debater: bool):
        sem = self.get_semester(semester_id)
        if not sem: return
        
        if is_debater and member_name not in sem.debater_names:
            sem.debater_names.append(member_name)
        elif not is_debater and member_name in sem.debater_names:
            sem.debater_names.remove(member_name)
        self.save_data()

    def add_session(self, semester_id: str, date: str, session_type: SessionType, title: str, activities: List[ActivityType]):
        sem = self.get_semester(semester_id)
        if sem:
            sem.sessions.append(Session(date, session_type, title, activities))
            self.save_data()
            
    def remove_session(self, semester_id: str, session_id: str):
        sem = self.get_semester(semester_id)
        if sem:
            sem.sessions = [s for s in sem.sessions if s.id != session_id]
            sem.attendance_records = [r for r in sem.attendance_records if r.session_id != session_id]
            self.save_data()

    def update_attendance(self, semester_id: str, member_name: str, session_id: str, session_date: str, activity_type: ActivityType, status: AttendanceStatus, late_minutes: int = 0):
        sem = self.get_semester(semester_id)
        if not sem: return

        # Remove existing record strictly by session_id if possible, or fallback matching
        # Actually session_id should be unique and sufficient.
        sem.attendance_records = [r for r in sem.attendance_records 
                                  if not (r.member_name == member_name and 
                                          r.session_id == session_id and
                                          r.activity_type == activity_type)]
        
        # Add new
        sem.attendance_records.append(AttendanceRecord(member_name, session_date, activity_type, status, late_minutes, session_id))
        self.save_data()

    def get_record(self, semester_id: str, member_name: str, session_id: str, activity_type: ActivityType) -> Optional[AttendanceRecord]:
        sem = self.get_semester(semester_id)
        if not sem: return None
        
        for r in sem.attendance_records:
            # Match by session_id first
            if r.member_name == member_name and r.session_id == session_id and r.activity_type == activity_type:
                return r
        
        return None
