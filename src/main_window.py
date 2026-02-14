import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTabWidget, QLabel, QLineEdit, QPushButton, QTableWidget, 
                             QTableWidgetItem, QComboBox, QMessageBox, QHeaderView, QDateEdit,
                             QDialog, QFormLayout, QSpinBox, QCheckBox, QFileDialog, QMenu,
                             QTreeWidget, QTreeWidgetItem, QRadioButton, QButtonGroup, QInputDialog)
from PyQt6.QtCore import Qt, QDate, QTime
from PyQt6.QtGui import QColor, QAction

from src.models import Member, Session, SessionType, ActivityType, AttendanceStatus, Semester, SemesterType
from src.data_manager import DataManager
from src.calc_engine import FineCalculator
from src.exporter import Exporter


class SemesterWidget(QWidget):
    def __init__(self, main_window, semester: Semester):
        super().__init__()
        self.main_window = main_window
        self.data_manager = main_window.data_manager
        self.calculator = main_window.calculator
        self.exporter = main_window.exporter
        self.semester = semester
        
        self.init_ui()
        self.load_initial_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Tab 1: Member Management
        self.tab_members = QWidget()
        self.init_member_tab()
        self.tabs.addTab(self.tab_members, "구성원 관리")
        
        # Tab 2: Attendance Management
        self.tab_attendance = QWidget()
        self.init_attendance_tab()
        self.tabs.addTab(self.tab_attendance, "출결 현황")

        
        # Tab 3: Report & Calculation
        self.tab_report = QWidget()
        self.init_report_tab()
        self.tabs.addTab(self.tab_report, "벌금 리포트")

    def init_member_tab(self):
        layout = QVBoxLayout(self.tab_members)
        
        # Input Area
        form_layout = QHBoxLayout()
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("이름 입력")
        
        btn_add = QPushButton("회원 추가")
        btn_add.clicked.connect(self.add_member)
        
        form_layout.addWidget(QLabel("이름:"))
        form_layout.addWidget(self.input_name)
        form_layout.addWidget(btn_add)
        
        layout.addLayout(form_layout)
        
        # Member List
        self.table_members = QTableWidget()
        self.table_members.setColumnCount(3)
        self.table_members.setHorizontalHeaderLabels(["이름", "토론대회 참석 여부", "관리"])
        self.table_members.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_members.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.table_members.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        layout.addWidget(self.table_members)
        
        self.load_members_to_table()

    def load_members_to_table(self):
        self.table_members.setRowCount(0)
        # Use semester members
        for member in self.semester.members:
            row = self.table_members.rowCount()
            self.table_members.insertRow(row)
            
            # Name
            item_name = QTableWidgetItem(member.name)
            item_name.setFlags(item_name.flags() ^ Qt.ItemFlag.ItemIsEditable) 
            self.table_members.setItem(row, 0, item_name)
            
            # Debate Attendance
            combo_debate = QComboBox()
            combo_debate.addItems(["아니오", "예"])
            
            is_att = member.name in self.semester.debater_names
            combo_debate.setCurrentIndex(1 if is_att else 0)
            
            combo_debate.currentIndexChanged.connect(lambda idx, m=member.name: self.update_member_debate(m, idx))
            self.table_members.setCellWidget(row, 1, combo_debate)
            
            # Delete Button
            btn_del = QPushButton("삭제")
            btn_del.clicked.connect(lambda _, n=member.name: self.delete_member(n))
            self.table_members.setCellWidget(row, 2, btn_del)

    def update_member_debate(self, member_name, index):
        is_attended = (index == 1)
        self.data_manager.set_debater_status(self.semester.id, member_name, is_attended)

    def add_member(self):
        name = self.input_name.text().strip()
        if not name:
            QMessageBox.warning(self, "오류", "이름을 입력해주세요.")
            return
            
        self.data_manager.add_member(self.semester.id, name)
        self.input_name.clear()
        self.load_members_to_table()
        self.refresh_attendance_table()

    def delete_member(self, name):
        reply = QMessageBox.question(self, "삭제 확인", f"'{name}' 회원을 이 학기에서 삭제하시겠습니까?\n(출결 기록은 남아있을 수 있습니다)",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.data_manager.remove_member(self.semester.id, name)
            self.load_members_to_table()
            self.refresh_attendance_table()

    def init_attendance_tab(self):
        layout = QVBoxLayout(self.tab_attendance)
        
        # Controls
        control_layout = QHBoxLayout()
        
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        
        self.date_edit.setCalendarPopup(True)
        
        self.combo_activity_type = QComboBox()
        self.combo_activity_type.addItems(["출석 (Attendance)", "댓글 (Comment)"])
        self.combo_activity_type.currentIndexChanged.connect(self.on_activity_type_changed)
        
        self.input_title = QLineEdit()
        self.input_title.setText("정규세션")
        self.input_title.setPlaceholderText("세션 제목")

        btn_add_session = QPushButton("세션 추가")
        btn_add_session.clicked.connect(self.add_session)
        
        control_layout.addWidget(QLabel("날짜:"))
        control_layout.addWidget(self.date_edit)
        control_layout.addWidget(QLabel("활동:"))
        control_layout.addWidget(self.combo_activity_type)
        control_layout.addWidget(QLabel("제목:"))
        control_layout.addWidget(self.input_title)
        control_layout.addWidget(btn_add_session)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        # Delete Session Button Area
        btn_layout = QHBoxLayout()
        self.btn_delete_session = QPushButton("선택한 세션 삭제")
        self.btn_delete_session.clicked.connect(self.delete_selected_session)
        self.btn_delete_session.setStyleSheet("background-color: #FFEBEE; color: red;")
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_delete_session)
        
        layout.addLayout(btn_layout)

        # Grid
        self.table_attendance = QTableWidget()
        self.table_attendance.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_attendance.horizontalHeader().customContextMenuRequested.connect(self.on_header_context_menu)
        self.table_attendance.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.table_attendance.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        layout.addWidget(self.table_attendance)

    def load_initial_data(self):
        self.refresh_attendance_table()

    def refresh_attendance_table(self):
        # Sort sessions
        sorted_sessions = sorted(self.semester.sessions, key=lambda s: s.date)
        
        headers = ["이름"]
        self.col_mapping = {} # col_index -> (Session, ActivityType)
        
        col_idx = 1
        for session in sorted_sessions:
            if ActivityType.ATTENDANCE in session.activities:
                headers.append(f"{session.date}\n({session.title}) 출석")
                self.col_mapping[col_idx] = (session, ActivityType.ATTENDANCE)
                col_idx += 1
            if ActivityType.COMMENT in session.activities:
                headers.append(f"{session.date}\n({session.title})")
                self.col_mapping[col_idx] = (session, ActivityType.COMMENT)
                col_idx += 1
                
        self.table_attendance.setColumnCount(len(headers))
        self.table_attendance.setHorizontalHeaderLabels(headers)
        
        # Rows - Changed from self.data_manager.members to self.semester.members
        members = self.semester.members
        self.table_attendance.setRowCount(len(members))
        
        for r, member in enumerate(members):
            # Name
            item_name = QTableWidgetItem(member.name)
            item_name.setFlags(item_name.flags() ^ Qt.ItemFlag.ItemIsEditable) 
            self.table_attendance.setItem(r, 0, item_name)
            
            # Attendance Cells
            for c in range(1, len(headers)):
                session, activity_type = self.col_mapping[c]
                record = self.data_manager.get_record(self.semester.id, member.name, session.id, activity_type)
                
                # Create Combo
                combo = QComboBox()
                if activity_type == ActivityType.ATTENDANCE:
                    # Exclude items as requested
                    exclusions = [AttendanceStatus.WRITTEN, AttendanceStatus.NOT_SUBMITTED, 
                                  AttendanceStatus.DEBATER, AttendanceStatus.PRESENTER,
                                  AttendanceStatus.OFFICIAL_EVENT,
                                  AttendanceStatus.EARLY_LEAVE_AS_ABSENT]
                    options = [s.value for s in AttendanceStatus if s not in exclusions]
                else: 
                    options = [AttendanceStatus.WRITTEN.value, AttendanceStatus.NOT_SUBMITTED.value, AttendanceStatus.LATE.value, 
                               AttendanceStatus.DEBATER.value, AttendanceStatus.PRESENTER.value]
                
                combo.addItems(["-"] + options)
                
                if record:
                    if record.status == AttendanceStatus.LATE and record.late_minutes > 0:
                        late_str = f"{record.late_minutes}분 지각"
                        if late_str not in options:
                            combo.addItem(late_str)
                        combo.setCurrentText(late_str)
                    else:
                        combo.setCurrentText(record.status.value)
                
                combo.currentTextChanged.connect(lambda text, m=member, s=session, a=activity_type, cb=combo: self.on_status_change(m, s, a, text, cb))
                self.table_attendance.setCellWidget(r, c, combo)

    def on_status_change(self, member, session, activity_type, text, combo_widget):
        if text == "-":
            return

        status = None
        late_minutes = 0
        
        if "분 지각" in text:
            status = AttendanceStatus.LATE
            try:
                late_minutes = int(text.split("분")[0])
            except:
                late_minutes = 0
        else:
            try:
                status = AttendanceStatus(text)
            except ValueError:
                return 

        if status == AttendanceStatus.LATE and activity_type == ActivityType.ATTENDANCE and "분 지각" not in text:
            mins, ok = QInputDialog.getInt(self, "지각 시간 입력", f"{member.name}님의 지각 시간(분):", 
                                           value=0, min=0, max=300)
            if ok:
                late_minutes = mins
                combo_widget.blockSignals(True)
                late_str = f"{late_minutes}분 지각"
                if combo_widget.findText(late_str) == -1:
                    combo_widget.addItem(late_str)
                combo_widget.setCurrentText(late_str)
                combo_widget.blockSignals(False)
            else:
                pass

        self.data_manager.update_attendance(self.semester.id, member.name, session.id, session.date, activity_type, status, late_minutes)
        self.check_outdated_reports()

    def on_activity_type_changed(self, index):
        if index == 0:
            self.input_title.setText("정규세션")
            self.input_title.setPlaceholderText("세션 제목")
        else:
            self.input_title.clear()
            self.input_title.setPlaceholderText("토론 주제")

    def add_session(self):
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        
        # Derive SessionType from SemesterType
        if self.semester.type == SemesterType.REGULAR:
            stype = SessionType.REGULAR
        else: # VACATION
            stype = SessionType.VACATION
            
        is_att = (self.combo_activity_type.currentIndex() == 0)
        title = self.input_title.text().strip()
        
        if not title:
            QMessageBox.warning(self, "오류", "세션 제목을 입력해주세요.")
            return
            
        activities = [ActivityType.ATTENDANCE] if is_att else [ActivityType.COMMENT]
        
        # Duplicate Check within Current Semester
        existing_session = None
        for s in self.semester.sessions:
            if s.date == date_str:
                if is_att:
                    if ActivityType.ATTENDANCE in s.activities:
                         existing_session = s
                         break
                else: 
                     if ActivityType.COMMENT in s.activities and s.title == title:
                         existing_session = s
                         break
        
        if existing_session:
            msg = ""
            if is_att:
                msg = f"{date_str}에 이미 출석 세션이 존재합니다.\n덮어쓰시겠습니까?"
            else:
                msg = f"{date_str}에 '{title}' 댓글 세션이 이미 존재합니다.\n덮어쓰시겠습니까?"
                
            reply = QMessageBox.question(self, "중복 세션", msg,
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            self.data_manager.remove_session(self.semester.id, existing_session.id)

        self.data_manager.add_session(self.semester.id, date_str, stype, title, activities)
        self.refresh_attendance_table()

    def delete_selected_session(self):
        current_col = self.table_attendance.currentColumn()
        if current_col < 1 or current_col not in self.col_mapping:
            QMessageBox.information(self, "알림", "삭제할 세션의 열(셀)을 선택해주세요.")
            return

        session, activity = self.col_mapping[current_col]
        self.confirm_delete_session(session)

    def on_header_context_menu(self, pos):
        logical_index = self.table_attendance.horizontalHeader().logicalIndexAt(pos)
        if logical_index < 1: return
        if logical_index not in self.col_mapping: return
        
        session, activity = self.col_mapping[logical_index]
        menu = QMenu(self)
        action_delete = QAction(f"{session.date} {session.title} 삭제", self)
        action_delete.triggered.connect(lambda: self.confirm_delete_session(session))
        menu.addAction(action_delete)
        menu.exec(self.table_attendance.horizontalHeader().viewport().mapToGlobal(pos))

    def confirm_delete_session(self, session):
         reply = QMessageBox.question(self, "세션 삭제", 
                                      f"{session.date} ({session.title}) 세션을 삭제하시겠습니까?",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
         if reply == QMessageBox.StandardButton.Yes:
             self.data_manager.remove_session(self.semester.id, session.id)
             self.refresh_attendance_table()

    # --- Report Tab ---
    def init_report_tab(self):
        layout = QVBoxLayout(self.tab_report)
        
        tool_layout = QHBoxLayout()
        btn_generate = QPushButton("현재 상태로 리포트 생성")
        btn_generate.clicked.connect(self.generate_report_snapshot)
        
        tool_layout.addWidget(btn_generate)
        tool_layout.addStretch()
        layout.addLayout(tool_layout)
        
        self.report_tabs = QTabWidget()
        self.report_tabs.setTabsClosable(True)
        self.report_tabs.tabCloseRequested.connect(lambda idx: self.report_tabs.removeTab(idx))
        layout.addWidget(self.report_tabs)

    def generate_report_snapshot(self):
        if not self.semester.members:
             QMessageBox.warning(self, "데이터 없음", "회원이 없습니다. '구성원 관리' 탭에서 회원을 추가해주세요.")
             return

        # Pop up dialog for report options
        dialog = QDialog(self)
        dialog.setWindowTitle("리포트 생성 옵션")
        layout = QVBoxLayout(dialog)
        chk_deduct = QCheckBox("프리패스 공제 여부 (체크시 출결벌금에 공제해서 계산)")
        layout.addWidget(chk_deduct)
        
        btn_box = QHBoxLayout()
        btn_ok = QPushButton("생성")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(dialog.reject)
        
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)
        
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        deduct_fp = chk_deduct.isChecked()

        results = self.calculator.calculate_all(self.semester.members, 
                                                self.semester.sessions, 
                                                self.semester.attendance_records,
                                                self.semester.type,
                                                self.semester.debater_names)
        
        if not results:
             QMessageBox.warning(self, "알림", "리포트를 생성할 데이터가 충분하지 않습니다.")
             return

        import time
        import copy
        timestamp_str = QDate.currentDate().toString("yyyy-MM-dd") + " " +  QTime.currentTime().toString("HH:mm:ss")
        
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        
        info_text = f"생성 일시: {timestamp_str}"
        if deduct_fp:
            info_text += " (프리패스 공제 적용)"
        info_label = QLabel(info_text)
        
        tab_widget.generated_at = time.time()
        tab_widget.results = results
        tab_widget.sessions_snapshot = copy.deepcopy(self.semester.sessions)
        tab_widget.deduct_fp = deduct_fp
        
        btn_export = QPushButton("이 리포트 Excel 내보내기")
        btn_export.clicked.connect(lambda _, w=tab_widget: self.export_snapshot(w))
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(info_label)
        header_layout.addStretch()
        header_layout.addWidget(btn_export)
        tab_layout.addLayout(header_layout)
        
        table = QTableWidget()
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        tab_layout.addWidget(table)
        
        self.populate_report_table(table, results, tab_widget.sessions_snapshot, deduct_fp)
        
        title_prefix = "리포트_공제O" if deduct_fp else "리포트_공제X"
        tab_title = f"{title_prefix}({QDate.currentDate().toString('MM-dd')}_{QTime.currentTime().toString('HH-mm')})"
        
        self.report_tabs.addTab(tab_widget, tab_title)
        self.report_tabs.setCurrentWidget(tab_widget)

    def populate_report_table(self, table: QTableWidget, results, sessions_snapshot, deduct_fp=False):
        table.clear()
        sorted_sessions = sorted(sessions_snapshot, key=lambda s: s.date)
        columns = [] 
        for s in sorted_sessions:
            if ActivityType.ATTENDANCE in s.activities:
                columns.append((s, ActivityType.ATTENDANCE, f"{s.date}\n출석"))
            if ActivityType.COMMENT in s.activities:
                columns.append((s, ActivityType.COMMENT, f"{s.date}\n댓글"))
                
        headers = ["비고 / 항목"]
        headers.extend([c[2] for c in columns])
        
        if deduct_fp:
            headers.extend(["잔여FP\n공제액", "댓글\n불참수", "댓글벌금\n부과대상", "임시벌금 합", "실납부액"])
        else:
            headers.extend(["잔여FP\n공제액", "댓글\n불참수", "댓글벌금\n부과대상", "벌금 합"])
        
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(results) * 6)
        
        summary_start_col_idx = 1 + len(columns)
        
        current_row = 0
        for name, data in results.items():
            r = current_row
            
            # Row 1
            self.set_cell(table, r, 0, name, bold=True, bg=QColor("#E3F2FD"))
            for idx, (sess, act, _) in enumerate(columns):
                val = "-"
                cell_color = None
                if act == ActivityType.ATTENDANCE:
                    for d in data['attendance_details']:
                        if d['date'] == sess.date:
                            val = d['status']
                            if d['fine'] > 0: cell_color = QColor("#FFEEEE")
                            break
                elif act == ActivityType.COMMENT:
                     for d in data['comment_details']:
                        if d['date'] == sess.date and d.get('title') == sess.title:
                            val = d['status']
                            if d['point'] > 0: cell_color = QColor("#FFF8E1")
                            break
                        elif d['date'] == sess.date: # Fallback
                             val = d['status']
                             if d['point'] > 0: cell_color = QColor("#FFF8E1")

                self.set_cell(table, r, 1+idx, val, bg=cell_color)

            # Summaries Row 1
            self.set_cell(table, r, summary_start_col_idx, "토론대회\n참여 여부")
            base = 1.5 if self.semester.type == SemesterType.REGULAR else 1.0
            debate_yes = data['initial_fp'] > base
            self.set_cell(table, r, summary_start_col_idx+1, "예" if debate_yes else "아니오")
            
            # Row 2
            self.set_cell(table, r+1, 0, "잔여 프리패스")
            for idx, (sess, act, _) in enumerate(columns):
                val = "-"
                if act == ActivityType.ATTENDANCE:
                    for d in data['attendance_details']:
                        if d['date'] == sess.date:
                            val = str(d['remaining_fp'])
                            break
                self.set_cell(table, r+1, 1+idx, val)
            self.set_cell(table, r+1, summary_start_col_idx, f"{data['remaining_fp_value']:,}")

            # Row 3
            self.set_cell(table, r+2, 0, "댓글 불참수")
            for idx, (sess, act, _) in enumerate(columns):
                val = "-"
                if act == ActivityType.COMMENT:
                     for d in data['comment_details']:
                        if d['date'] == sess.date and d.get('title') == sess.title:
                             val = str(d['point'])
                             break
                        elif d['date'] == sess.date:
                             val = str(d['point'])
                self.set_cell(table, r+2, 1+idx, val)
            self.set_cell(table, r+2, summary_start_col_idx+1, str(data['total_comment_points']))
            self.set_cell(table, r+2, summary_start_col_idx+2, "대상" if data['is_comment_fine_target'] else "-")

            # Row 4
            self.set_cell(table, r+3, 0, "댓글 벌금")
            for idx, (sess, act, _) in enumerate(columns):
                val = "-"
                if act == ActivityType.COMMENT:
                     for d in data['comment_details']:
                        if d['date'] == sess.date and d.get('title') == sess.title:
                             val = f"{d['potential_fine']:,}"
                             break
                        elif d['date'] == sess.date:
                             val = f"{d['potential_fine']:,}"
                self.set_cell(table, r+3, 1+idx, val)
            self.set_cell(table, r+3, summary_start_col_idx+3, f"{data['total_comment_fine']:,}")
            
            # Row 5
            self.set_cell(table, r+4, 0, "출석 벌금")
            for idx, (sess, act, _) in enumerate(columns):
                val = "-"
                if act == ActivityType.ATTENDANCE:
                    for d in data['attendance_details']:
                        if d['date'] == sess.date:
                            val = f"{d['fine']:,}"
                            break
                self.set_cell(table, r+4, 1+idx, val)
            self.set_cell(table, r+4, summary_start_col_idx+3, f"{data['total_attendance_fine']:,}")

            # Row 6
            if deduct_fp:
                self.set_cell(table, r+5, 0, "벌금 총액") 
                
                # Logic:
                # Actual Payment = Max(0, AttendanceFine - FreePassValue) + CommentFine
                att_fine = data['total_attendance_fine']
                comm_fine = data['total_comment_fine']
                fp_val = data['remaining_fp_value']
                
                deducted_att_fine = max(0, att_fine - fp_val)
                actual_payment = deducted_att_fine + comm_fine
                
                # Column: 임시벌금 합 (summary_start_col_idx + 3)
                self.set_cell(table, r+5, summary_start_col_idx+3, f"{data['total_fine']:,}", bold=False)
                # Column: 실납부액 (summary_start_col_idx + 4)
                self.set_cell(table, r+5, summary_start_col_idx+4, f"{actual_payment:,}원", bold=True, color=QColor("red"))
            else:
                self.set_cell(table, r+5, 0, "벌금 총액")
                self.set_cell(table, r+5, summary_start_col_idx+3, f"{data['total_fine']:,}원", bold=True, color=QColor("red"))
            
            current_row += 6
            
        table.resizeColumnsToContents()
        table.resizeRowsToContents()

    def set_cell(self, table, row, col, text, bold=False, bg=None, color=None):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if bold:
            f = item.font()
            f.setBold(True)
            item.setFont(f)
        if bg:
            item.setBackground(bg)
        if color:
            item.setForeground(color)
        table.setItem(row, col, item)

    def export_snapshot(self, tab_widget):
        deduct_fp = getattr(tab_widget, 'deduct_fp', False)
        prefix = "리포트_공제O" if deduct_fp else "리포트_공제X"
        date_str = QDate.currentDate().toString("yyyy-MM-dd")
        time_str = QTime.currentTime().toString("HH-mm") # Changed to use current time or original gen time? Usually current export time or gen time. Sticking to current based on user request "Time and Date"
        # User requested "Report_... (Date_Time)".
        # Actually it's better to use the generated time if possible, but user said "becomes ... (time and date)".
        # Usually file name timestamp = time of export.
        default_name = f"{prefix}({date_str}_{time_str}).xlsx"
        
        filename, _ = QFileDialog.getSaveFileName(self, "Excel 저장", default_name, "Excel Files (*.xlsx)")
        if filename:
            try:
                self.exporter.export_to_excel(filename, tab_widget.results, tab_widget.sessions_snapshot, deduct_fp)
                QMessageBox.information(self, "완료", "파일이 저장되었습니다.")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"저장 중 오류 발생: {str(e)}")

    def check_outdated_reports(self):
        count = self.report_tabs.count()
        for i in range(count):
            widget = self.report_tabs.widget(i)
            if hasattr(widget, 'generated_at'):
                if widget.generated_at < self.data_manager.last_modified:
                    for child in widget.findChildren(QLabel):
                        if "생성 일시" in child.text() and "(Outdated)" not in child.text():
                             child.setText(child.text() + " (Outdated - 데이터 변경됨)")
                             child.setStyleSheet("color: red; font-weight: bold;")


class MainWindow(QMainWindow):
    def __init__(self, data_manager: DataManager = None):
        super().__init__()
        self.setWindowTitle("고란도란 출결 및 벌금 관리 (Semester Integrated)")
        self.resize(1200, 800)
        
        self.data_manager = data_manager if data_manager else DataManager()
        self.calculator = FineCalculator()
        self.exporter = Exporter()
        
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        self.main_tabs = QTabWidget()
        self.main_tabs.setTabsClosable(True)
        self.main_tabs.tabCloseRequested.connect(self.on_tab_close_requested)
        self.main_tabs.setMovable(True) # Option for better UX
        layout.addWidget(self.main_tabs)
        
        # Add Semester Button (Corner Widget)
        # Using QToolButton for a compact look
        from PyQt6.QtWidgets import QToolButton
        btn_add = QToolButton()
        btn_add.setText("+")
        btn_add.setToolTip("새 학기 추가")
        font = btn_add.font()
        font.setBold(True)
        btn_add.setFont(font)
        btn_add.setFixedSize(30, 30)
        btn_add.clicked.connect(self.prompt_add_semester)
        
        # Place it on the TopLeftCorner (standard position for tab bars often implies 'after tabs' is hard, 
        # but TopLeft puts it before. TopRight puts it far right. 
        # Chrome puts it after tabs. Achieving 'after tabs' perfectly requires dummy tab or subclass.
        # User requested "Left End", so TopLeftCorner is the most accurate implementation of that request.
        self.main_tabs.setCornerWidget(btn_add, Qt.Corner.TopLeftCorner)
        
        self.semester_widgets = {} 
        self.load_semesters()
        
        # Automatically select the last semester (latest one)
        if self.main_tabs.count() > 0:
            self.main_tabs.setCurrentIndex(self.main_tabs.count() - 1)

    def load_semesters(self):
        # Store current index to restore if possible? Or just load.
        self.main_tabs.clear()
        self.semester_widgets = {}
        
        for semester in self.data_manager.semesters:
            widget = SemesterWidget(self, semester)
            self.main_tabs.addTab(widget, semester.name)
            self.semester_widgets[semester.id] = widget
            
    def on_tab_close_requested(self, index):
        widget = self.main_tabs.widget(index)
        if isinstance(widget, SemesterWidget):
             self.prompt_delete_semester(widget.semester)

    def prompt_add_semester(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("학기 추가")
        layout = QFormLayout(dialog)
        
        name_edit = QLineEdit()
        type_combo = QComboBox()
        type_combo.addItems([SemesterType.REGULAR.value, SemesterType.VACATION.value])
        
        layout.addRow("학기 이름 (예: 25-1학기 정기):", name_edit)
        layout.addRow("학기 구분:", type_combo)
        
        buttons = QHBoxLayout()
        btn_ok = QPushButton("생성")
        btn_ok.clicked.connect(dialog.accept)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(dialog.reject)
        buttons.addWidget(btn_ok)
        buttons.addWidget(btn_cancel)
        layout.addRow(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = name_edit.text().strip()
            if not name: return
            
            stype_str = type_combo.currentText()
            stype = SemesterType.REGULAR if stype_str == SemesterType.REGULAR.value else SemesterType.VACATION
            
            self.data_manager.add_semester(name, stype)
            self.load_semesters()
            self.main_tabs.setCurrentIndex(self.main_tabs.count() - 1)

    def prompt_delete_semester(self, semester):
        text, ok = QInputDialog.getText(self, "학기 삭제 확인", 
                                        f"'{semester.name}' 을(를) 삭제하시겠습니까?\n모든 데이터가 삭제됩니다.\n삭제하시려면 '이해했습니다'를 입력하세요.")
        if ok and text == "이해했습니다":
            self.data_manager.remove_semester(semester.id)
            self.load_semesters()
        elif ok:
            QMessageBox.warning(self, "오류", "입력 문구가 일치하지 않아 삭제가 취소되었습니다.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
