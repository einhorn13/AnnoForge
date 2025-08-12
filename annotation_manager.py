# annotation_manager.py
import sqlite3
import json
import logging

class AnnotationManager:
    """
    Manages storage and retrieval of complex, plugin-specific data using an
    SQLite database. Each project gets its own .db file.
    
    This allows plugins to save structured data (like settings, coordinates,
    or metadata) associated with a specific image item.
    """
    def __init__(self):
        self.conn = None

    def connect(self, db_path: str):
        """Connects to the SQLite database and creates tables if they don't exist."""
        try:
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self._create_table()
            logging.info(f"Successfully connected to annotation database: {db_path}")
        except sqlite3.Error as e:
            logging.error(f"Database connection failed to {db_path}: {e}")
            self.conn = None

    def _create_table(self):
        """Creates the 'annotations' table if it doesn't already exist."""
        if not self.conn: return
        try:
            with self.conn:
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS annotations (
                        item_id TEXT NOT NULL,
                        plugin_name TEXT NOT NULL,
                        data TEXT NOT NULL,
                        PRIMARY KEY (item_id, plugin_name)
                    )
                """)
        except sqlite3.Error as e:
            logging.error(f"Failed to create annotations table: {e}")
            
    def save_data(self, item_id: str, plugin_name: str, data: dict):
        """
        Saves or updates a plugin's data for a specific item.
        The data dictionary is stored as a JSON string.
        """
        if not self.conn:
            logging.warning("Cannot save data, no database connection.")
            return

        json_data = json.dumps(data)
        try:
            with self.conn:
                self.conn.execute("""
                    INSERT INTO annotations (item_id, plugin_name, data)
                    VALUES (?, ?, ?)
                    ON CONFLICT(item_id, plugin_name) DO UPDATE SET
                        data = excluded.data
                """, (item_id, plugin_name, json_data))
            logging.debug(f"Saved data for {item_id} from plugin {plugin_name}")
        except sqlite3.Error as e:
            logging.error(f"Failed to save annotation for {item_id} [{plugin_name}]: {e}")

    def get_data(self, item_id: str, plugin_name: str) -> dict | None:
        """
        Retrieves a plugin's data for a specific item.
        Returns the data as a dictionary, or None if not found.
        """
        if not self.conn:
            logging.warning("Cannot get data, no database connection.")
            return None

        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT data FROM annotations
                WHERE item_id = ? AND plugin_name = ?
            """, (item_id, plugin_name))
            
            result = cursor.fetchone()
            if result:
                return json.loads(result[0])
            return None
        except (sqlite3.Error, json.JSONDecodeError) as e:
            logging.error(f"Failed to retrieve or decode annotation for {item_id} [{plugin_name}]: {e}")
            return None

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logging.info("Annotation database connection closed.")