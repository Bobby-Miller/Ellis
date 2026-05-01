import sys
import json
import logging
from pathlib import Path

from src.database.db import Database, ControllerExistsError
from src.parser.l5k_parser import L5KParser
from src.parser.l5x_parser import L5XParser
from src.config.config import ExportConfig
from src.exporter.exporter import IgnitionExporter

logger = logging.getLogger(__name__)

def ingest_command(args):
    config = ExportConfig(args.config)
    db_path = config.get_database_path()
    
    db = Database(db_path)
    l5k_parser = L5KParser(db)
    l5x_parser = L5XParser(db)
    
    target_path = Path(args.path)
    
    if not target_path.exists():
        logger.error(f"Path does not exist: {target_path}")
        sys.exit(1)
        
    files_to_process = []
    if target_path.is_file():
        ext = target_path.suffix.lower()
        if ext in ['.l5k', '.l5x']:
            files_to_process.append(target_path)
    elif target_path.is_dir():
        files_to_process.extend(target_path.glob("*.L5K"))
        files_to_process.extend(target_path.glob("*.l5k"))
        files_to_process.extend(target_path.glob("*.L5X"))
        files_to_process.extend(target_path.glob("*.l5x"))
        
    if not files_to_process:
        logger.warning(f"No L5K/L5X files found in {target_path}")
        return

    for filepath in files_to_process:
        str_path = str(filepath.absolute())
        if db.is_file_ingested(str_path):
            logger.info(f"Skipping already ingested file: {filepath.name}")
            continue
            
        logger.info(f"Ingesting: {filepath.name}...")
        file_id = db.insert_file(str_path)
        
        try:
            ext = filepath.suffix.lower()
            if ext == '.l5k':
                l5k_parser.parse_file(str_path, file_id)
            elif ext == '.l5x':
                l5x_parser.parse_file(str_path, file_id)
                
            logger.info(f"Successfully parsed {filepath.name}")
        except ControllerExistsError as e:
            logger.info(f"Skipping file {filepath.name}: {e}")
            db.delete_file(file_id)
        except Exception as e:
            logger.error(f"Error parsing {filepath.name}: {e}")
            db.delete_file(file_id)

    db.close()
    logger.info("Ingestion complete.")

def export_command(args):
    config = ExportConfig(args.config)
    db_path = config.get_database_path()
    
    if not Path(db_path).exists():
        logger.error(f"Database does not exist: {db_path}. Run ingest first.")
        sys.exit(1)

    db = Database(db_path)
    
    logger.info("Generating export from database...")
    exporter = IgnitionExporter(db, config)
    result = exporter.export()
    
    with open(args.output, 'w') as f:
        json.dump(result, f, indent=2)
        
    logger.info(f"Export saved to {args.output}")
    db.close()
