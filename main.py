import argparse
import logging
import sys

from src.cli.commands import ingest_command, export_command
from src.cli.build_config import build_config_command

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(
        description="L5K to Ignition Tag Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest a single L5K file into the database
  python main.py --config config.json ingest "hanwha_l5k/6698 PLC Rev07.L5K"

  # Ingest a directory of L5K files into the database
  python main.py --config config.json ingest ./hanwha_l5k

  # Export tags to a JSON file using the tags defined in config.json
  python main.py --config config.json export --output ignition_tags.json
"""
    )
    parser.add_argument("--config", type=str, default="config.json", help="Path to configuration JSON file (default: config.json)")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # Ingest subcommand
    ingest_parser = subparsers.add_parser(
        "ingest", 
        help="Ingest L5K/L5X files into the database",
        description="Ingest a single .L5K/.L5X file or a directory containing .L5K/.L5X files into the SQLite database. Keeps track of ingested files to prevent duplicates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  python main.py --config config.json ingest ./hanwha_l5k"
    )
    ingest_parser.add_argument("path", type=str, help="Path to an .L5K/.L5X file or a directory containing .L5K/.L5X files")
    ingest_parser.set_defaults(func=ingest_command)
    
    # Export subcommand
    export_parser = subparsers.add_parser(
        "export", 
        help="Export tags to Ignition JSON",
        description="Export tags from the SQLite database to an Ignition-compatible JSON file based on the configuration dictionary.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  python main.py --config config.json export --output my_tags.json"
    )
    export_parser.add_argument("--output", type=str, default="ignition_tags.json", help="Path to output JSON file")
    export_parser.set_defaults(func=export_command)
    
    # Help subcommand
    help_parser = subparsers.add_parser("help", help="Show this help message")
    
    # Build Config subcommand
    build_config_parser = subparsers.add_parser(
        "build-config",
        help="Build a config.json from an HMI configuration JSON",
        description="Parses a unified JSON configuration file containing HMI strings and a shortcut map dictionary to generate an exporter configuration.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  python main.py build-config hmi_config.json --output config.json"
    )
    build_config_parser.add_argument("hmi_config", type=str, help="Path to the unified HMI JSON configuration file")
    build_config_parser.add_argument("--output", type=str, default="config.json", help="Path to the output config.json file (default: config.json)")
    build_config_parser.add_argument("--db", type=str, default="l5k_project.db", help="Path to the SQLite database for tag validation (overrides the path in hmi_config.json if specified)")
    build_config_parser.set_defaults(func=build_config_command)
    
    args = parser.parse_args()
    
    if args.command == "help" or args.command is None:
        parser.print_help()
        sys.exit(0)
        
    args.func(args)

if __name__ == "__main__":
    main()
