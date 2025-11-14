import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional

class Database:
    def __init__(self, db_name: str = "kousu.db"):
        # Azure App Serviceの永続ストレージ(/home)を使用
        if os.environ.get('WEBSITE_SITE_NAME'):  # Azure環境の判定
            db_dir = '/home/data'
            os.makedirs(db_dir, exist_ok=True)
            self.db_name = os.path.join(db_dir, db_name)
        else:
            self.db_name = db_name
        self.init_database()

    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        # プロジェクトテーブル
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                client TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # メンバーテーブル
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 工数レコードテーブル（メンバーIDを追加）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kousu_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                member_id INTEGER,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                estimated_hours REAL DEFAULT 0,
                planned_hours REAL DEFAULT 0,
                actual_hours REAL DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id),
                FOREIGN KEY (member_id) REFERENCES members (id),
                UNIQUE(project_id, member_id, year, month)
            )
        ''')

        conn.commit()
        conn.close()

    # プロジェクト関連
    def add_project(self, name: str, client: str = "", description: str = "") -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO projects (name, client, description) VALUES (?, ?, ?)",
            (name, client, description)
        )
        project_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return project_id

    def get_all_projects(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
        projects = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return projects

    def get_project(self, project_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # メンバー関連
    def add_member(self, name: str, email: str = "") -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO members (name, email) VALUES (?, ?)",
                (name, email)
            )
            member_id = cursor.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            # 既に存在する場合は既存のIDを返す
            cursor.execute("SELECT id FROM members WHERE name = ?", (name,))
            member_id = cursor.fetchone()[0]
        finally:
            conn.close()
        return member_id

    def get_all_members(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM members ORDER BY name")
        members = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return members

    def get_member(self, member_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM members WHERE id = ?", (member_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # 工数関連
    def add_or_update_kousu(self, project_id: int, year: int, month: int,
                           estimated_hours: float = 0, planned_hours: float = 0,
                           actual_hours: float = 0, notes: str = "",
                           member_id: Optional[int] = None) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM kousu_records WHERE project_id = ? AND member_id IS ? AND year = ? AND month = ?",
            (project_id, member_id, year, month)
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute('''
                UPDATE kousu_records
                SET estimated_hours = ?, planned_hours = ?, actual_hours = ?,
                    notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE project_id = ? AND member_id IS ? AND year = ? AND month = ?
            ''', (estimated_hours, planned_hours, actual_hours, notes, project_id, member_id, year, month))
        else:
            cursor.execute('''
                INSERT INTO kousu_records
                (project_id, member_id, year, month, estimated_hours, planned_hours, actual_hours, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (project_id, member_id, year, month, estimated_hours, planned_hours, actual_hours, notes))

        conn.commit()
        conn.close()
        return True

    def get_kousu_by_period(self, year: Optional[int] = None, month: Optional[int] = None) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()

        query = '''
            SELECT k.*, p.name as project_name, p.client, m.name as member_name
            FROM kousu_records k
            JOIN projects p ON k.project_id = p.id
            LEFT JOIN members m ON k.member_id = m.id
        '''
        params = []

        if year is not None:
            query += " WHERE k.year = ?"
            params.append(year)
            if month is not None:
                query += " AND k.month = ?"
                params.append(month)

        query += " ORDER BY k.year DESC, k.month DESC, p.name, m.name"

        cursor.execute(query, params)
        records = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return records

    def get_kousu_by_project(self, year: Optional[int] = None, month: Optional[int] = None) -> List[Dict]:
        """案件単位で工数を集計"""
        conn = self.get_connection()
        cursor = conn.cursor()

        query = '''
            SELECT
                k.project_id,
                p.name as project_name,
                p.client,
                GROUP_CONCAT(DISTINCT k.year || '年' || k.month || '月') as periods,
                SUM(k.estimated_hours) as estimated_hours,
                SUM(k.planned_hours) as planned_hours,
                SUM(k.actual_hours) as actual_hours,
                GROUP_CONCAT(DISTINCT m.name) as members
            FROM kousu_records k
            JOIN projects p ON k.project_id = p.id
            LEFT JOIN members m ON k.member_id = m.id
        '''
        params = []

        if year is not None:
            query += " WHERE k.year = ?"
            params.append(year)
            if month is not None:
                query += " AND k.month = ?"
                params.append(month)

        query += " GROUP BY k.project_id ORDER BY p.name"

        cursor.execute(query, params)
        records = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return records

    def get_kousu_by_member(self, year: Optional[int] = None, month: Optional[int] = None) -> List[Dict]:
        """メンバー単位で工数を集計"""
        conn = self.get_connection()
        cursor = conn.cursor()

        query = '''
            SELECT
                k.member_id,
                m.name as member_name,
                m.email,
                k.year,
                k.month,
                SUM(k.estimated_hours) as estimated_hours,
                SUM(k.planned_hours) as planned_hours,
                SUM(k.actual_hours) as actual_hours,
                GROUP_CONCAT(DISTINCT p.name) as projects
            FROM kousu_records k
            LEFT JOIN members m ON k.member_id = m.id
            JOIN projects p ON k.project_id = p.id
        '''
        params = []

        if year is not None:
            query += " WHERE k.year = ?"
            params.append(year)
            if month is not None:
                query += " AND k.month = ?"
                params.append(month)

        query += " GROUP BY k.member_id, k.year, k.month ORDER BY k.year DESC, k.month DESC, m.name"

        cursor.execute(query, params)
        records = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return records

    def get_summary_by_period(self, year: Optional[int] = None, month: Optional[int] = None) -> Dict:
        records = self.get_kousu_by_period(year, month)

        total_estimated = sum(r['estimated_hours'] for r in records)
        total_planned = sum(r['planned_hours'] for r in records)
        total_actual = sum(r['actual_hours'] for r in records)

        return {
            'total_estimated': total_estimated,
            'total_planned': total_planned,
            'total_actual': total_actual,
            'record_count': len(records),
            'records': records
        }

    def get_all_years_months(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT year, month
            FROM kousu_records
            ORDER BY year DESC, month DESC
        ''')
        periods = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return periods
