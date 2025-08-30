import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager
from config import DATABASE_PATH


@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize the database with required tables."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Invoice cycles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoice_cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                hourly_rate REAL,
                currency TEXT DEFAULT 'INR',
                client_name TEXT,
                client_address TEXT,
                client_gstin TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Calendar events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                duration_hours REAL NOT NULL,
                cycle_id INTEGER,
                FOREIGN KEY (cycle_id) REFERENCES invoice_cycles (id)
            )
        ''')
        
        # Invoices table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id INTEGER NOT NULL,
                invoice_number TEXT UNIQUE NOT NULL,
                invoice_date DATE NOT NULL,
                due_date DATE NOT NULL,
                total_hours REAL NOT NULL,
                hourly_rate REAL NOT NULL,
                total_amount REAL NOT NULL,
                pdf_path TEXT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cycle_id) REFERENCES invoice_cycles (id)
            )
        ''')
        
        # User profile table for invoice details
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                address TEXT NOT NULL,
                account_name TEXT,
                account_number TEXT,
                ifsc_code TEXT,
                bank_name TEXT,
                account_type TEXT,
                pan TEXT,
                logo_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()


class InvoiceCycle:
    @staticmethod
    def create(name: str, start_date: str, end_date: str, 
               hourly_rate: Optional[float] = None,
               client_name: Optional[str] = None,
               client_address: Optional[str] = None,
               client_gstin: Optional[str] = None) -> int:
        """Create a new invoice cycle."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO invoice_cycles 
                (name, start_date, end_date, hourly_rate, client_name, client_address, client_gstin)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, start_date, end_date, hourly_rate, client_name, client_address, client_gstin))
            conn.commit()
            return cursor.lastrowid
    
    @staticmethod
    def list_all() -> List[Dict]:
        """List all invoice cycles."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, start_date, end_date, hourly_rate, 
                       client_name, created_at
                FROM invoice_cycles
                ORDER BY created_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def get(cycle_id: int) -> Optional[Dict]:
        """Get a specific invoice cycle."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM invoice_cycles WHERE id = ?
            ''', (cycle_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def update_rate(cycle_id: int, hourly_rate: float):
        """Update hourly rate for a cycle."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE invoice_cycles SET hourly_rate = ? WHERE id = ?
            ''', (hourly_rate, cycle_id))
            conn.commit()


class CalendarEvent:
    @staticmethod
    def bulk_insert(events: List[Dict], cycle_id: Optional[int] = None):
        """Insert multiple calendar events."""
        with get_db() as conn:
            cursor = conn.cursor()
            for event in events:
                cursor.execute('''
                    INSERT OR REPLACE INTO calendar_events 
                    (event_id, title, description, start_time, end_time, duration_hours, cycle_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event['id'],
                    event['summary'],
                    event.get('description', ''),
                    event['start'],
                    event['end'],
                    event['duration_hours'],
                    cycle_id
                ))
            conn.commit()
    
    @staticmethod
    def get_unassigned(start_date: str, end_date: str) -> List[Dict]:
        """Get unassigned events within date range."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM calendar_events 
                WHERE cycle_id IS NULL 
                AND DATE(start_time) >= ? 
                AND DATE(end_time) <= ?
                ORDER BY start_time
            ''', (start_date, end_date))
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def assign_to_cycle(event_ids: List[int], cycle_id: int):
        """Assign events to an invoice cycle."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE calendar_events 
                SET cycle_id = ? 
                WHERE id IN ({})
            '''.format(','.join('?' * len(event_ids))), 
            [cycle_id] + event_ids)
            conn.commit()
    
    @staticmethod
    def get_by_cycle(cycle_id: int) -> List[Dict]:
        """Get all events for a specific cycle."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM calendar_events 
                WHERE cycle_id = ?
                ORDER BY start_time
            ''', (cycle_id,))
            return [dict(row) for row in cursor.fetchall()]


class Invoice:
    @staticmethod
    def create(cycle_id: int, invoice_number: str, invoice_date: str,
               due_date: str, total_hours: float, hourly_rate: float,
               total_amount: float, pdf_path: str) -> int:
        """Create a new invoice record."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO invoices 
                (cycle_id, invoice_number, invoice_date, due_date, 
                 total_hours, hourly_rate, total_amount, pdf_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (cycle_id, invoice_number, invoice_date, due_date,
                  total_hours, hourly_rate, total_amount, pdf_path))
            conn.commit()
            return cursor.lastrowid
    
    @staticmethod
    def get_next_invoice_number() -> str:
        """Generate next invoice number."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT MAX(CAST(SUBSTR(invoice_number, 2) AS INTEGER)) as max_num
                FROM invoices
                WHERE invoice_number LIKE '#%'
            ''')
            result = cursor.fetchone()
            max_num = result['max_num'] if result['max_num'] else 0
            return f"#{max_num + 1:03d}"
    
    @staticmethod
    def list_all() -> List[Dict]:
        """List all invoices with cycle information."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    i.*,
                    c.name as cycle_name,
                    c.client_name
                FROM invoices i
                JOIN invoice_cycles c ON i.cycle_id = c.id
                ORDER BY i.generated_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def get_by_number(invoice_number: str) -> Optional[Dict]:
        """Get invoice by invoice number."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    i.*,
                    c.name as cycle_name,
                    c.client_name
                FROM invoices i
                JOIN invoice_cycles c ON i.cycle_id = c.id
                WHERE i.invoice_number = ?
            ''', (invoice_number,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def delete(invoice_number: str) -> bool:
        """Delete invoice by invoice number and optionally delete PDF file."""
        # First get the invoice to check if PDF file exists
        invoice = Invoice.get_by_number(invoice_number)
        if not invoice:
            return False
            
        # Delete PDF file if it exists
        if invoice.get('pdf_path'):
            pdf_path = Path(invoice['pdf_path'])
            if pdf_path.exists():
                pdf_path.unlink()
        
        # Delete from database
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM invoices WHERE invoice_number = ?', (invoice_number,))
            conn.commit()
            return cursor.rowcount > 0


class UserProfile:
    @staticmethod
    def get_or_create() -> Dict:
        """Get user profile or create default."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_profile ORDER BY id DESC LIMIT 1')
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            else:
                # Create default profile
                cursor.execute('''
                    INSERT INTO user_profile 
                    (full_name, address)
                    VALUES (?, ?)
                ''', ('Your Name', 'Your Address'))
                conn.commit()
                return {
                    'id': cursor.lastrowid,
                    'full_name': 'Your Name',
                    'address': 'Your Address'
                }
    
    @staticmethod
    def update(profile_data: Dict):
        """Update user profile."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE user_profile 
                SET full_name = ?, address = ?, account_name = ?,
                    account_number = ?, ifsc_code = ?, bank_name = ?,
                    account_type = ?, pan = ?
                WHERE id = (SELECT MAX(id) FROM user_profile)
            ''', (
                profile_data.get('full_name'),
                profile_data.get('address'),
                profile_data.get('account_name'),
                profile_data.get('account_number'),
                profile_data.get('ifsc_code'),
                profile_data.get('bank_name'),
                profile_data.get('account_type'),
                profile_data.get('pan')
            ))
            conn.commit()