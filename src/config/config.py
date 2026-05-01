import json
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ExportConfig:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.database_name = "l5k_project.db"
        self.tags: Dict[str, dict] = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.filepath):
            logger.warning(f"Config file not found: {self.filepath}. Using defaults.")
            return

        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)
            
            # Check if using the new structured format
            if "database" in data or "tags" in data:
                self.database_name = data.get("database", "l5k_project.db")
                self.tags = data.get("tags", {})
            else:
                # Support the older flat format temporarily
                self.tags = data
                
            logger.info(f"Loaded configuration. Database: {self.database_name}, Tags config: {len(self.tags)} entries.")
        except Exception as e:
            logger.error(f"Failed to load config {self.filepath}: {e}")
            self.tags = {}

    def get_database_path(self) -> str:
        """
        Returns the path to the database. Since it should be saved to the main directory,
        we use the raw filename which resolves to the current working directory,
        or we can ensure it's absolute based on the current execution directory.
        """
        return os.path.abspath(self.database_name)

    def should_export(self, controller: str, scope: str, name: str) -> bool:
        """
        Check if a given tag matches the config.
        We check the flattened name: 'Scope.Name' or just 'Name' if Global.
        """
        match_name = name if scope == 'Global' else f"{scope}.{name}"
        
        # Support both flat format and controller-grouped format
        ctrl_tags = self.tags.get(controller, self.tags)
        
        entry = ctrl_tags.get(match_name)
        if not entry:
            return False
        return entry.get('export', False)

    def get_rename(self, controller: str, scope: str, name: str) -> str:
        """
        Returns the mapped rename value, or the original name if not specified.
        """
        match_name = name if scope == 'Global' else f"{scope}.{name}"
        
        ctrl_tags = self.tags.get(controller, self.tags)
        
        entry = ctrl_tags.get(match_name, {})
        return entry.get('rename', name)
