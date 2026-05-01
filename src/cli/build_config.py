import sys
import json
import logging
from pathlib import Path
import re

from src.database.db import Database

logger = logging.getLogger(__name__)

def build_config_command(args):
    hmi_config_file = Path(args.hmi_config)
    
    if not hmi_config_file.exists():
        logger.error(f"HMI config file not found: {hmi_config_file}")
        sys.exit(1)
        
    try:
        with open(hmi_config_file, 'r') as f:
            hmi_config = json.load(f)
    except Exception as e:
        logger.error(f"Failed to parse HMI config file: {e}")
        sys.exit(1)
        
    database_path = hmi_config.get("database", args.db)
    shortcut_map = hmi_config.get("shortcut_map", {})
    tags_list = hmi_config.get("hmi_tags", [])
    
    if not tags_list:
        logger.error("Could not find 'hmi_tags' array in the config file.")
        sys.exit(1)
            
    # Optional Database validation
    db = Database(database_path) if Path(database_path).exists() else None
    if not db:
        logger.warning(f"Database {database_path} not found. Skipping tag validation.")
        
    output_config = {
        "database": database_path,
        "tags": {}
    }
    
    valid_count = 0
    invalid_count = 0
    
    for full_path in tags_list:
        # e.g., "[IFC1_IUS_PLC]Program:MainProgram.PCVD_Seal_Pressure"
        # e.g., "[IFC1_IUS_PLC]UDHLift.Cylinder[0].PI.Feedback.Device"
        
        match = re.match(r"^\[(.*?)\](.*)", full_path)
        if not match:
            logger.warning(f"Invalid tag format (missing shortcut): {full_path}")
            continue
            
        shortcut = match.group(1)
        tag_path = match.group(2)
        
        controller_name = shortcut_map.get(shortcut)
        if not controller_name:
            logger.warning(f"Shortcut '{shortcut}' not found in map. Skipping: {full_path}")
            continue
            
        if controller_name not in output_config["tags"]:
            output_config["tags"][controller_name] = {}
            
        # Parse scope and base tag
        scope = "Global"
        
        # Check if program scoped
        if tag_path.startswith("Program:"):
            parts = tag_path.split(".", 1)
            if len(parts) > 1:
                scope = parts[0].replace("Program:", "")
                remainder = parts[1]
            else:
                logger.warning(f"Malformed program tag: {full_path}")
                continue
        else:
            remainder = tag_path
            
        # The base tag is the part before the next '.' or '['
        base_tag = re.split(r"[\.\[]", remainder)[0]
        
        # Construct the match_name exactly as the exporter expects
        match_name = base_tag if scope == "Global" else f"{scope}.{base_tag}"
        
        # Validate against database if possible
        if db:
            cur = db.conn.execute(
                "SELECT t.id FROM tags t JOIN controllers c ON t.controller_id = c.id WHERE c.name = ? AND t.scope = ? AND t.name = ?",
                (controller_name, scope, base_tag)
            )
            if not cur.fetchone():
                logger.debug(f"Tag not found in database: Controller={controller_name}, Scope={scope}, Tag={base_tag} (Path: {full_path})")
                invalid_count += 1
                # We still add it, but it's good to log
            else:
                valid_count += 1
        
        # Add to config dict
        output_config["tags"][controller_name][match_name] = {
            "export": True,
            "rename": base_tag # Can be manually changed later
        }
        
    if db:
        db.close()
        logger.info(f"Database validation: {valid_count} tags found, {invalid_count} tags missing/mismatched.")
        
    total_tags = sum(len(c) for c in output_config["tags"].values())
    logger.info(f"Generated config with {total_tags} base tags across {len(output_config['tags'])} controllers.")
    
    with open(args.output, 'w') as f:
        json.dump(output_config, f, indent=2)
        
    logger.info(f"Configuration saved to {args.output}")