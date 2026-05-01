import json
import logging
import re
from typing import Dict, List, Any
from src.database.db import Database
from src.config.config import ExportConfig
from src.exporter.builtins import BUILTIN_UDTS

logger = logging.getLogger(__name__)

# Standard mapping for atomic types
DATA_TYPE_MAPPING = {
    "BOOL": "Boolean",
    "BIT": "Boolean",
    "SINT": "Int1",
    "INT": "Int2",
    "DINT": "Int4",
    "REAL": "Float4",
    "STRING": "String"
}

IGNORED_ROCKWELL_TYPES = {
    'SERIAL_PORT_CONTROL', 'AXIS_CIP_DRIVE', 'MOTION_GROUP', 
    'MOTION_INSTRUCTION', 'ADD', 'DIV', 'MOV', 'ALM', 'FAL',
    'SELECT_ENHANCED', 'SCALE', 'AXIS_SERVO',
}

class IgnitionExporter:
    def __init__(self, db: Database, config: ExportConfig):
        self.db = db
        self.config = config
        
        # Caching
        self.udts_by_id = {}
        self.udt_members_by_udt_id = {}
        
        self._load_cache()

    def _load_cache(self):
        with self.db.conn:
            # Load all UDTs
            cur = self.db.conn.execute("SELECT * FROM udts")
            for row in cur:
                self.udts_by_id[row['id']] = dict(row)
                self.udt_members_by_udt_id[row['id']] = []
            
            # Load UDT members
            cur = self.db.conn.execute("SELECT * FROM udt_members")
            for row in cur:
                udt_id = row['udt_id']
                if udt_id in self.udt_members_by_udt_id:
                    self.udt_members_by_udt_id[udt_id].append(dict(row))

    def _get_udt_by_name(self, name: str, controller_id: int) -> dict:
        for udt in self.udts_by_id.values():
            if udt['name'].upper() == name.upper() and udt['controller_id'] == controller_id:
                return udt
        return None

    def _get_canonical_udt_by_name(self, name: str) -> dict:
        for udt in self.udts_by_id.values():
            if udt['name'].upper() == name.upper():
                return udt
        return None

    def export(self) -> Dict[str, Any]:
        root_tags = []
        
        # 1. Generate _types_ folder for all UDTs used in this controller
        # For simplicity in this exporter, we dump all parsed UDT definitions 
        # into the types folder. A strictly optimized exporter might only include referenced UDTs.
        types_folder = {
            "name": "_types_",
            "tagType": "Folder",
            "tags": self._generate_udt_types()
        }
        root_tags.append(types_folder)
        
        # 2. Process each controller
        cur_controllers = self.db.conn.execute("SELECT * FROM controllers")
        for ctrl in cur_controllers:
            ctrl_folder = {
                "name": ctrl['name'],
                "tagType": "Folder",
                "tags": []
            }
            
            # Keep track of program folders
            program_folders: Dict[str, dict] = {}
            
            # Fetch tags for this controller
            cur_tags = self.db.conn.execute("SELECT * FROM tags WHERE controller_id = ?", (ctrl['id'],))
            for tag_row in cur_tags:
                tag = dict(tag_row)
                
                # Check Configuration (Whitelist / Rename)
                if not self.config.should_export(ctrl['name'], tag['scope'], tag['name']):
                    continue
                    
                final_name = self.config.get_rename(ctrl['name'], tag['scope'], tag['name'])
                
                ig_tag = self._create_ignition_tag(tag, final_name, ctrl['name'])
                
                if ig_tag:
                    if tag['scope'] == 'Global':
                        ctrl_folder['tags'].append(ig_tag)
                    else:
                        # Nested program folder
                        prog_name = tag['scope']
                        if prog_name not in program_folders:
                            program_folders[prog_name] = {
                                "name": prog_name,
                                "tagType": "Folder",
                                "tags": []
                            }
                        program_folders[prog_name]['tags'].append(ig_tag)
            
            # Append program folders to controller
            for prog_folder in program_folders.values():
                ctrl_folder['tags'].append(prog_folder)
                
            root_tags.append(ctrl_folder)
            
        return {
            "name": "",
            "tagType": "Provider",
            "tags": root_tags
        }

    def _generate_udt_types(self) -> List[dict]:
        udt_types = []
        existing_udt_names = set()
        
        for udt in self.udts_by_id.values():
            if udt['name'].upper() in existing_udt_names:
                continue
            existing_udt_names.add(udt['name'].upper())
            
            # Create UDT Definition structure
            members = self.udt_members_by_udt_id.get(udt['id'], [])
            
            udt_def = {
                "name": udt['name'],
                "tagType": "UdtType",
                "parameters": {
                    "DeviceName": {"dataType": "String"},
                    "TagPrefix": {"dataType": "String"}
                },
                "tags": []
            }
            
            for mem in members:
                # Same resolution logic as actual tags, but relative pathing
                ig_mem = self._create_ignition_tag(mem, mem['name'], "{DeviceName}", prefix="{TagPrefix}.", is_udt_def=True)
                if ig_mem:
                    udt_def['tags'].append(ig_mem)
            
            udt_types.append(udt_def)
            
        # Append Built-in UDTs if they are not already defined
        for builtin in BUILTIN_UDTS:
            if builtin['name'].upper() not in existing_udt_names:
                udt_def = {
                    "name": builtin['name'],
                    "tagType": "UdtType",
                    "parameters": {
                        "DeviceName": {"dataType": "String"},
                        "TagPrefix": {"dataType": "String"}
                    },
                    "tags": []
                }
                for mem in builtin['members']:
                    # Fake a db member dict
                    mem_dict = {
                        "name": mem['name'],
                        "data_type": mem['data_type'],
                        "array_dimensions": mem['array_dimensions'],
                        "alias_for": None
                    }
                    ig_mem = self._create_ignition_tag(mem_dict, mem['name'], "{DeviceName}", prefix="{TagPrefix}.", is_udt_def=True)
                    if ig_mem:
                        udt_def['tags'].append(ig_mem)
                udt_types.append(udt_def)
            
        return udt_types

    def _create_ignition_tag(self, tag_data: dict, final_name: str, device_name: str, prefix: str = "", is_udt_def: bool = False) -> dict:
        dt = tag_data['data_type']
        array_dim = tag_data.get('array_dimensions')
        
        # Skip internal ZZZZZZ placeholders used in L5K
        if 'ZZZZZZ' in final_name or 'ZZZZZZ' in tag_data.get('name', ''):
            return None

        # Skip explicit 'N' tags (often internal placeholders in instruction blocks)
        if final_name.upper() == 'N' or tag_data.get('name', '').upper() == 'N':
            return None
            
        # Skip unsupported AOPs / internal instruction types
        if dt.upper() in IGNORED_ROCKWELL_TYPES:
            logger.debug(f"Skipping unsupported Rockwell type: {dt}")
            return None
        
        # Alias resolution (Basic)
        # Note: If it's an alias to an array element or specific member, we just point the OPC path to the base.
        base_path = tag_data.get('alias_for') or tag_data['name']
        
        if dt == "ALIAS":
            # If data type is missing (common in L5K aliases), infer from path or default to BOOL
            if re.search(r'\.\d+$', base_path) or "PIO" in base_path:
                dt = "BOOL"
            else:
                dt = "BOOL" # Safe fallback for unknown aliases
        
        # Formulate OPC Item Path based on Scope
        # If it's a global tag, no prefix. If program scoped, prefix with Program:ProgramName.
        # But OPC UA syntax usually expects: ns=1;s=[Device]Program:ProgName.TagName or similar
        # For simplicity we construct the direct path.
        if tag_data.get('scope') and tag_data['scope'] != 'Global':
            # Ignition OPC UA path for program scoped tags
            logix_path = f"Program:{tag_data['scope']}.{base_path}"
        else:
            logix_path = base_path
        
        # If inside UDT def, the opc path is parameterized
        if is_udt_def:
            opc_item_path = {
                "bindType": "parameter",
                "binding": f"ns=1;s=[{device_name}]{prefix}{base_path}"
            }
        else:
            opc_item_path = f"ns=1;s=[{device_name}]{prefix}{logix_path}"

        # Resolve Type
        ig_type = DATA_TYPE_MAPPING.get(dt)
        
        if ig_type:
            # Atomic Tag
            tag = {
                "name": final_name,
                "tagType": "AtomicTag",
                "dataType": ig_type,
                "valueSource": "opc",
                "opcServer": "Ignition OPC UA Server",
                "opcItemPath": opc_item_path
            }
        else:
            # Udt Instance
            tag = {
                "name": final_name,
                "tagType": "UdtInstance",
                "typeId": dt,
                "parameters": {
                    "DeviceName": {"dataType": "String", "value": device_name},
                    "TagPrefix": {"dataType": "String", "value": f"{prefix}{logix_path}"}
                },
                "tags": []
            }
            if is_udt_def:
                # Bind parameters for nested UDTs
                tag['parameters']["DeviceName"]["value"] = {"bindType": "parameter", "binding": device_name}
                tag['parameters']["TagPrefix"]["value"] = {"bindType": "parameter", "binding": f"{prefix}{logix_path}."}
                
                # Do NOT recursively populate the tags array when inside a UDT definition. 
                # Ignition automatically inherits members from the UdtType.
                # Supplying them here explicitly causes Bad_Unsupported errors for override mismatches.
                return tag

            # Recursively populate the tags array for this UDT instance
            # Note: UDT instances outside of definitions (actual tag instances) should have their 
            # internal member tags listed explicitly to ensure proper property overrides and parameter inheritance in Ignition.
            # We look up the canonical UDT definition from cache by name (the first one exported)
            # This ensures that instances only attempt to override members that were actually written to _types_
            udt_def = self._get_canonical_udt_by_name(dt)
            if udt_def:
                members = self.udt_members_by_udt_id.get(udt_def['id'], [])
                for mem in members:
                    # In an instance, members are just simple representations. If it's another Udt, it recurses.
                    # We pass is_udt_def=is_udt_def so the bindings carry through correctly.
                    mem_tag = self._create_ignition_tag(
                        mem, 
                        mem['name'], 
                        device_name, 
                        prefix=f"{prefix}{logix_path}." if not is_udt_def else "{TagPrefix}.", 
                        is_udt_def=is_udt_def
                    )
                    if mem_tag:
                        tag['tags'].append(mem_tag)
            else:
                # Check if it's a builtin
                for builtin in BUILTIN_UDTS:
                        if builtin['name'].upper() == dt.upper():
                            for mem in builtin['members']:
                                mem_dict = {
                                    "name": mem['name'],
                                    "data_type": mem['data_type'],
                                    "array_dimensions": mem['array_dimensions'],
                                    "alias_for": None
                                }
                                mem_tag = self._create_ignition_tag(
                                    mem_dict, 
                                    mem['name'], 
                                    device_name, 
                                    prefix=f"{prefix}{logix_path}." if not is_udt_def else "{TagPrefix}.", 
                                    is_udt_def=is_udt_def
                                )
                                if mem_tag:
                                    tag['tags'].append(mem_tag)
                            break

        # Handle Arrays (Ignition Native Arrays)
        if array_dim:
            # For native arrays, we just ensure the dataType has 'Array'
            # Note: Ignition represents array types usually natively if the OPC server returns an array.
            # We can hint it in the data type if it's atomic (e.g. Int4Array)
            if 'dataType' in tag:
                tag['dataType'] = f"{tag['dataType']}Array"
                
        # Optional props
        if tag_data.get('description'):
            tag['documentation'] = tag_data['description']
            
        return tag
