import sqlite3
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT UNIQUE NOT NULL,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS controllers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER,
    name TEXT NOT NULL,
    processor_type TEXT,
    major_version INTEGER,
    comm_path TEXT,
    FOREIGN KEY(file_id) REFERENCES files(id)
);

CREATE TABLE IF NOT EXISTS udts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    controller_id INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    is_aoi BOOLEAN DEFAULT 0,
    FOREIGN KEY(controller_id) REFERENCES controllers(id)
);

CREATE TABLE IF NOT EXISTS udt_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    udt_id INTEGER,
    name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    array_dimensions TEXT,
    hidden BOOLEAN DEFAULT 0,
    description TEXT,
    FOREIGN KEY(udt_id) REFERENCES udts(id)
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    controller_id INTEGER,
    scope TEXT NOT NULL,  -- 'Global' or Program name
    name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    array_dimensions TEXT,
    alias_for TEXT,
    hidden BOOLEAN DEFAULT 0,
    description TEXT,
    FOREIGN KEY(controller_id) REFERENCES controllers(id)
);
"""

class ControllerExistsError(Exception):
    """Raised when attempting to insert a controller that already exists."""
    pass

class Database:
    def __init__(self, db_path: str = "l5k_project.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        # Enable foreign keys
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        with self.conn:
            self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.close()

    def is_file_ingested(self, filepath: str) -> bool:
        with self.conn:
            cur = self.conn.execute("SELECT id FROM files WHERE filepath = ?", (filepath,))
            return cur.fetchone() is not None

    def insert_file(self, filepath: str) -> int:
        with self.conn:
            cursor = self.conn.execute("INSERT INTO files (filepath) VALUES (?)", (filepath,))
            return cursor.lastrowid

    def delete_file(self, file_id: int):
        with self.conn:
            self.conn.execute("DELETE FROM files WHERE id = ?", (file_id,))

    def insert_controller(self, file_id: int, name: str, processor_type: Optional[str] = None, 
                          major_version: Optional[int] = None, comm_path: Optional[str] = None) -> int:
        with self.conn:
            # Check if controller already exists by name
            cur = self.conn.execute("SELECT id FROM controllers WHERE name = ?", (name,))
            if cur.fetchone():
                raise ControllerExistsError(f"Controller '{name}' already exists in the database.")
                
            cursor = self.conn.execute(
                "INSERT INTO controllers (file_id, name, processor_type, major_version, comm_path) VALUES (?, ?, ?, ?, ?)",
                (file_id, name, processor_type, major_version, comm_path)
            )
            return cursor.lastrowid

    def insert_udt(self, controller_id: int, name: str, description: Optional[str] = None, is_aoi: bool = False) -> int:
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO udts (controller_id, name, description, is_aoi) VALUES (?, ?, ?, ?)",
                (controller_id, name, description, is_aoi)
            )
            return cursor.lastrowid

    def insert_udt_member(self, udt_id: int, name: str, data_type: str, 
                          array_dimensions: Optional[str] = None, hidden: bool = False, description: Optional[str] = None):
        with self.conn:
            self.conn.execute(
                "INSERT INTO udt_members (udt_id, name, data_type, array_dimensions, hidden, description) VALUES (?, ?, ?, ?, ?, ?)",
                (udt_id, name, data_type, array_dimensions, hidden, description)
            )

    def insert_tag(self, controller_id: int, scope: str, name: str, data_type: str, 
                   array_dimensions: Optional[str] = None, alias_for: Optional[str] = None, 
                   hidden: bool = False, description: Optional[str] = None):
        with self.conn:
            self.conn.execute(
                "INSERT INTO tags (controller_id, scope, name, data_type, array_dimensions, alias_for, hidden, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (controller_id, scope, name, data_type, array_dimensions, alias_for, hidden, description)
            )
