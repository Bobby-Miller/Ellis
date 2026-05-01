import xml.etree.ElementTree as ET
import logging
from typing import Optional
from src.database.db import Database

logger = logging.getLogger(__name__)

class L5XParser:
    def __init__(self, db: Database):
        self.db = db

    def parse_file(self, filepath: str, file_id: int):
        logger.info(f"Parsing L5X XML structure for {filepath}...")
        
        # We use a standard ElementTree parse. For exceptionally large files, iterparse could be used,
        # but standard tree parsing handles Logix XMLs well on modern hardware.
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        # The root is typically <RSLogix5000Content>
        # Under it is <Controller>
        controller_node = root.find("Controller")
        if controller_node is None:
            logger.error(f"No <Controller> element found in {filepath}")
            return
            
        ctrl_name = controller_node.attrib.get("Name", "Unknown")
        processor_type = controller_node.attrib.get("ProcessorType")
        major_version = controller_node.attrib.get("MajorRev")
        comm_path = controller_node.attrib.get("CommPath")
        
        # Insert Controller
        controller_id = self.db.insert_controller(
            file_id=file_id, 
            name=ctrl_name, 
            processor_type=processor_type, 
            major_version=int(major_version) if major_version and major_version.isdigit() else None, 
            comm_path=comm_path
        )
        
        # Parse DataTypes
        datatypes_node = controller_node.find("DataTypes")
        if datatypes_node is not None:
            for dt_node in datatypes_node.findall("DataType"):
                dt_name = dt_node.attrib.get("Name")
                if not dt_name: continue
                
                desc = self._get_description(dt_node)
                udt_id = self.db.insert_udt(controller_id, dt_name, desc, is_aoi=False)
                
                members_node = dt_node.find("Members")
                if members_node is not None:
                    for mem_node in members_node.findall("Member"):
                        self._parse_member_node(mem_node, udt_id)
                        
        # Parse AOIs
        aoi_node = controller_node.find("AddOnInstructionDefinitions")
        if aoi_node is not None:
            for def_node in aoi_node.findall("AddOnInstructionDefinition"):
                aoi_name = def_node.attrib.get("Name")
                if not aoi_name: continue
                
                desc = self._get_description(def_node)
                udt_id = self.db.insert_udt(controller_id, aoi_name, desc, is_aoi=True)
                
                # Parameters
                params_node = def_node.find("Parameters")
                if params_node is not None:
                    for p_node in params_node.findall("Parameter"):
                        self._parse_member_node(p_node, udt_id)
                        
                # LocalTags
                localtags_node = def_node.find("LocalTags")
                if localtags_node is not None:
                    for lt_node in localtags_node.findall("LocalTag"):
                        self._parse_member_node(lt_node, udt_id)
                        
        # Parse Global Tags
        tags_node = controller_node.find("Tags")
        if tags_node is not None:
            for tag_node in tags_node.findall("Tag"):
                self._parse_tag_node(tag_node, controller_id, "Global")
                
        # Parse Programs
        programs_node = controller_node.find("Programs")
        if programs_node is not None:
            for prog_node in programs_node.findall("Program"):
                prog_name = prog_node.attrib.get("Name")
                if not prog_name: continue
                
                prog_tags_node = prog_node.find("Tags")
                if prog_tags_node is not None:
                    for tag_node in prog_tags_node.findall("Tag"):
                        self._parse_tag_node(tag_node, controller_id, prog_name)

    def _get_description(self, node: ET.Element) -> Optional[str]:
        desc_node = node.find("Description")
        if desc_node is not None and desc_node.text:
            return desc_node.text.strip()
        return None

    def _parse_member_node(self, node: ET.Element, udt_id: int):
        name = node.attrib.get("Name")
        data_type = node.attrib.get("DataType")
        dimension = node.attrib.get("Dimension", "0")
        hidden_str = node.attrib.get("Hidden", "false").lower()
        hidden = hidden_str == "true" or hidden_str == "1"
        
        array_dim = f"[{dimension}]" if dimension and dimension != "0" else None
        desc = self._get_description(node)
        
        if name and data_type:
            self.db.insert_udt_member(udt_id, name, data_type, array_dim, hidden, desc)

    def _parse_tag_node(self, node: ET.Element, controller_id: int, scope: str):
        name = node.attrib.get("Name")
        tag_type = node.attrib.get("TagType", "Base")
        data_type = node.attrib.get("DataType", "UNKNOWN")
        dimension = node.attrib.get("Dimension", "0")
        alias_for = node.attrib.get("AliasFor")
        
        hidden = False # L5X <Tag> nodes don't typically have a Hidden attribute like Members do, but we handle just in case
        
        array_dim = f"[{dimension}]" if dimension and dimension != "0" else None
        desc = self._get_description(node)
        
        if not name:
            return
            
        if tag_type == "Alias" and alias_for:
            self.db.insert_tag(controller_id, scope, name, data_type, array_dim, alias_for, hidden, desc)
        else:
            self.db.insert_tag(controller_id, scope, name, data_type, array_dim, None, hidden, desc)
