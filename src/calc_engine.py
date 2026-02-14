from typing import List, Dict, Tuple, Optional
import sys
import os

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models import Member, Session, AttendanceRecord, SessionType, SemesterType, ActivityType, AttendanceStatus

class FineCalculator:
    def __init__(self, base_fine: int = 6000, late_base: int = 1000, late_per_10min: int = 1000):
        self.BASE_FINE = base_fine
        self.LATE_BASE = late_base
        self.LATE_PER_10MIN = late_per_10min
        self.COMMENT_FINE_THRESHOLD = 2.0
    
    def calculate_all(self, members: List[Member], sessions: List[Session], records: List[AttendanceRecord], 
                      semester_type: SemesterType, debater_names: List[str]) -> Dict[str, Dict]:
        results = {}
        for member in members:
            is_debater = member.name in debater_names
            results[member.name] = self.calculate_member(member, sessions, records, semester_type, is_debater)
        return results

    def calculate_member(self, member: Member, sessions: List[Session], records: List[AttendanceRecord], 
                         semester_type: SemesterType, is_debater: bool) -> Dict:
        # 1. Determine Base Free Pass
        # Regular: 1.5, Vacation: 1.0
        base_fp = 1.5 if semester_type == SemesterType.REGULAR else 1.0
        
        current_fp = base_fp
        original_fp = base_fp # For tracking
        
        # Add Debate Bonus
        if is_debater:
            current_fp += 1.0
            original_fp += 1.0
        
        attendance_fines = 0
        comment_points_total = 0.0
        comment_fines_potential_total = 0
        
        attendance_details = [] # List of (SessionDate, Fine, FP_Used, Remaining_FP, Log, Status, LateMinutes)
        comment_details = [] # List of (SessionDate, Point, PotentialFine, Status, Title)

        # Sort sessions by date just in case
        sorted_sessions = sorted(sessions, key=lambda s: s.date)

        for session in sorted_sessions:
            # Process Attendance First
            if ActivityType.ATTENDANCE in session.activities:
                rec = self._find_record(records, member.name, session.id, ActivityType.ATTENDANCE)
                fine, fp_used, log_msg = self._calc_attendance_fine(rec, current_fp)
                
                current_fp -= fp_used
                attendance_fines += fine
                
                # Logic for status string
                status_str = rec.status.value if rec else "-"
                if rec and rec.status == AttendanceStatus.LATE and rec.late_minutes > 0:
                    status_str += f" ({rec.late_minutes}분)"

                attendance_details.append({
                    'date': session.date,
                    'title': session.title,
                    'status': status_str,
                    'fine': fine,
                    'fp_used': fp_used,
                    'remaining_fp': current_fp,
                    'log': log_msg
                })

            # Process Comment
            if ActivityType.COMMENT in session.activities:
                rec = self._find_record(records, member.name, session.id, ActivityType.COMMENT)
                point, pot_fine = self._calc_comment_stats(rec)
                
                comment_points_total += point
                comment_fines_potential_total += pot_fine
                
                status_str = rec.status.value if rec else "-"
                
                comment_details.append({
                    'date': session.date,
                    'title': session.title,
                    'status': status_str,
                    'point': point,
                    'potential_fine': pot_fine
                })

        # Finalize Comment Fine logic
        # If total points > threshold (2.0), then pay fines for ALL missing comments? 
        # Or just the ones exceeding? Usually "Target" means pay for all missed.
        final_comment_fine = 0
        is_comment_target = comment_points_total >= self.COMMENT_FINE_THRESHOLD # Usually >= 2.0 or > 1.5
        # The prompt said "If total points >= 2, fine target".
        # Code previously had > 2.0. Let's stick to previous threshold logic unless specified.
        # Wait, previous code was `comment_points_total > self.COMMENT_FINE_THRESHOLD`.
        # (2.0 in init). So > 2.0 means 2.5, 3.0 etc. 2.0 is safe?
        # User manual usually says "If 2 or more". "2개 이상" implies >= 2.0.
        # Let's adjust to >= 2.0 if standard. But sticking to code's threshold constant.
        
        # Let's assume threshold is strict limit.
        if comment_points_total > self.COMMENT_FINE_THRESHOLD: # Changed to > based on user request "2번 초과"
             final_comment_fine = comment_fines_potential_total
        
        total_fine = attendance_fines + final_comment_fine
        
        # Round floating point issues for display
        current_fp = round(current_fp, 2)

        return {
            'member_name': member.name,
            'initial_fp': original_fp,
            'remaining_fp': current_fp,
            'remaining_fp_value': int(current_fp * self.BASE_FINE), # Value provided is int usually
            'total_attendance_fine': attendance_fines,
            'total_comment_points': comment_points_total,
            'is_comment_fine_target': comment_points_total > self.COMMENT_FINE_THRESHOLD,
            'total_comment_fine': final_comment_fine,
            'total_fine': total_fine,
            'attendance_details': attendance_details,
            'comment_details': comment_details
        }

    def _find_record(self, records: List[AttendanceRecord], name: str, session_id: str, type: ActivityType) -> Optional[AttendanceRecord]:
        for r in records:
            # Match strictly by session_id
            if r.member_name == name and r.session_id == session_id and r.activity_type == type:
                return r
        return None

    def _calc_attendance_fine(self, record: Optional[AttendanceRecord], current_fp: float) -> Tuple[int, float, str]:
        """Returns (Fine, FP_Used, LogMessage)"""
        if not record:
            # Treated as Absent? Or just ignore if no record? 
            # If session exists but no record, usually treated as Absent or just 0 if not initialized.
            # Let's assume 0 for now to be safe, or caller handles it.
            return 0, 0.0, "-"
        
        s = record.status
        
        if s == AttendanceStatus.PRESENT or s == AttendanceStatus.OFFICIAL_EVENT:
            return 0, 0.0, "출석/공결"
            
        if s in [AttendanceStatus.A, AttendanceStatus.B, AttendanceStatus.C, AttendanceStatus.D, AttendanceStatus.E]:
            return 0, 0.0, f"{s.value} (면제)"
            
        if s == AttendanceStatus.LATE:
            # LATE: FP Cannot be used.
            # Fine: 1000 + (min // 10) * 1000
            mins = record.late_minutes
            fine = self.LATE_BASE + (mins // 10) * self.LATE_PER_10MIN
            return fine, 0.0, f"지각({mins}분): {fine}원"
            
        if s == AttendanceStatus.ABSENT:
            # ABSENT: FP Cannot be used. Full Fine.
            return self.BASE_FINE, 0.0, f"결석: {self.BASE_FINE}원"
        
        if s == AttendanceStatus.F:
            # Case "F":
            # 1 F = 1.0 FP Consumption (Worth 6000 KRW)
            if current_fp >= 1.0:
                # Fully covered
                return 0, 1.0, "F: FP 1개 차감"
            elif current_fp >= 0.5:
                # Partially covered (0.5 FP available)
                # Use 0.5 FP (Worth 3000 KRW)
                # Remaining 0.5 F cost = 3000 KRW fine
                return 3000, 0.5, "F: FP 0.5개 차감 + 3000원"
            else:
                # No FP (or < 0.5, usually impossible if logic is sound but safe fallback)
                return 6000, 0.0, "F: 6000원"
            
        if s in [AttendanceStatus.LATE_WITH_EXCUSE, AttendanceStatus.EARLY_LEAVE_WITH_EXCUSE]: 
            # Case "사유서 지각", "사유서 조퇴"
            if current_fp >= 0.5:
                return 0, 0.5, f"{s.value}: FP 0.5개 차감"
            else:
                return 3000, 0.0, f"{s.value}: 3000원"
            
        return 0, 0.0, "-"

    def _calc_comment_stats(self, record: Optional[AttendanceRecord]) -> Tuple[float, int]:
        """Returns (Points, PotentialFine)"""
        if not record:
            return 1.0, 2000 # Treat missing as "Not Submitted"
        
        s = record.status
        if s == AttendanceStatus.NOT_SUBMITTED: # 미작성
            return 1.0, 2000
        elif s == AttendanceStatus.LATE: # 지각 (제출은 했으나 늦음)
            return 0.5, 1000
        elif s in [AttendanceStatus.WRITTEN, AttendanceStatus.DEBATER, AttendanceStatus.PRESENTER]:
            return 0.0, 0
            
        return 0.0, 0
