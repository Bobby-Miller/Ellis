import re
from typing import Optional
from dataclasses import dataclass
from src.database.db import Database

@dataclass
class ParserState:
    IN_GLOBAL = "GLOBAL"
    IN_CONTROLLER = "CONTROLLER"
    IN_DATATYPE = "DATATYPE"
    IN_AOI = "AOI"
    IN_PROGRAM = "PROGRAM"
    IN_TAGS = "TAGS"

class L5KParser:
    def __init__(self, db: Database):
        self.db = db
        self.state = ParserState.IN_GLOBAL
        self.current_controller_id = None
        self.current_udt_id = None
        self.current_scope = None # 'Global' or program name

        # Precompile common regexes
        self.re_controller = re.compile(r"CONTROLLER\s+(?P<name>\w+)")
        self.re_processor = re.compile(r"ProcessorType\s+:=\s+\"(?P<type>[^\"]+)\"")
        self.re_major = re.compile(r"Major\s+:=\s+(?P<major>\d+)")
        self.re_comm = re.compile(r"CommPath\s+:=\s+\"(?P<comm>[^\"]+)\"")

        self.re_datatype = re.compile(r"DATATYPE\s+(?P<name>\w+)")
        self.re_aoi = re.compile(r"ADD_ON_INSTRUCTION_DEFINITION\s+(?P<name>\w+)")
        self.re_program = re.compile(r"PROGRAM\s+(?P<name>\w+)")
        
        # Tag/Member declarations - handle optional semi-colons
        self.re_member = re.compile(r"^\s*(?P<name>[a-zA-Z0-9_]+)\s*:\s*(?P<type>[a-zA-Z0-9_:]+)(?P<array>\[[\d,\s]+\])?(?P<props>.*)")
        # Alias declarations
        self.re_alias = re.compile(r"^\s*(?P<name>[a-zA-Z0-9_]+)\s+OF\s+(?P<base>[a-zA-Z0-9_:.]+)(?P<props>.*)")

        self.re_desc = re.compile(r"Description\s+:=\s+\"(?P<desc>.*?)\"")
        self.re_hidden = re.compile(r"Hidden\s+:=\s+(?P<hidden>\d)")

    def parse_file(self, filepath: str, file_id: int):
        self.state = ParserState.IN_GLOBAL
        self.current_controller_id = None
        self.current_scope = None
        
        # Temporary holding for controller attributes until we close the CONTROLLER header
        temp_controller = {"file_id": file_id, "name": "Unknown", "processor_type": None, "major_version": None, "comm_path": None}
        
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue

                elif self.state == ParserState.IN_GLOBAL:
                    match = self.re_controller.match(line)
                    if match:
                        temp_controller["name"] = match.group("name")
                        self.state = ParserState.IN_CONTROLLER
                        
                        # In case the CONTROLLER definition is on a single line
                        if line.endswith(")") or line.endswith(");"):
                            self.current_controller_id = self.db.insert_controller(**temp_controller)
                            self.current_scope = "Global"
                        continue

                elif self.state == ParserState.IN_CONTROLLER:
                    if "ProcessorType" in line:
                        m = self.re_processor.search(line)
                        if m: temp_controller["processor_type"] = m.group("type")
                    elif "Major :=" in line:
                        m = self.re_major.search(line)
                        if m: temp_controller["major_version"] = int(m.group("major"))
                    elif "CommPath" in line:
                        m = self.re_comm.search(line)
                        if m: temp_controller["comm_path"] = m.group("comm")
                    
                    if self.current_controller_id is None and (line.endswith(")") or line.endswith(");")):
                        # End of CONTROLLER definition header
                        self.current_controller_id = self.db.insert_controller(**temp_controller)
                        self.current_scope = "Global" # Ready for global tags
                        continue

                    # Look for child blocks
                    if line.startswith("DATATYPE"):
                        m = self.re_datatype.search(line)
                        if m:
                            name = m.group("name")
                            # Simple description extraction from the same line if exists
                            desc = self._extract_desc(line)
                            self.current_udt_id = self.db.insert_udt(self.current_controller_id, name, desc, is_aoi=False)
                            self.state = ParserState.IN_DATATYPE
                            continue
                            
                    elif line.startswith("ADD_ON_INSTRUCTION_DEFINITION"):
                        m = self.re_aoi.search(line)
                        if m:
                            name = m.group("name")
                            self.current_udt_id = self.db.insert_udt(self.current_controller_id, name, is_aoi=True)
                            self.state = ParserState.IN_AOI
                            continue

                    elif line.startswith("PROGRAM"):
                        m = self.re_program.search(line)
                        if m:
                            self.current_scope = m.group("name")
                            self.state = ParserState.IN_PROGRAM
                            continue
                            
                    elif line == "TAG":
                        # We are inside CONTROLLER, so these are Global tags
                        self.state = ParserState.IN_TAGS
                        continue

                elif self.state == ParserState.IN_DATATYPE:
                    if line == "END_DATATYPE":
                        self.state = ParserState.IN_CONTROLLER
                        self.current_udt_id = None
                        continue
                    
                    self._parse_udt_member(line)

                elif self.state == ParserState.IN_AOI:
                    if line == "END_ADD_ON_INSTRUCTION_DEFINITION":
                        self.state = ParserState.IN_CONTROLLER
                        self.current_udt_id = None
                        continue
                    
                    # Inside AOI we care about LOCAL_TAGS and PARAMETERS (which we treat as members for now)
                    # We can just run the member regex against lines containing ':'
                    if ":" in line and not line.startswith("Description") and not line.startswith("Hidden"):
                         self._parse_udt_member(line)

                elif self.state == ParserState.IN_PROGRAM:
                    if line == "END_PROGRAM":
                        self.state = ParserState.IN_CONTROLLER
                        self.current_scope = "Global"
                        continue
                    
                    if line == "TAG":
                        self.state = ParserState.IN_TAGS
                        continue

                elif self.state == ParserState.IN_TAGS:
                    if line == "END_TAG":
                        # Return to either CONTROLLER or PROGRAM based on current scope
                        if self.current_scope == "Global":
                            self.state = ParserState.IN_CONTROLLER
                        else:
                            self.state = ParserState.IN_PROGRAM
                        continue
                    
                    self._parse_tag(line)


    def _extract_desc(self, text: str) -> Optional[str]:
        m = self.re_desc.search(text)
        return m.group("desc") if m else None

    def _extract_hidden(self, text: str) -> bool:
        m = self.re_hidden.search(text)
        return m.group("hidden") == "1" if m else False

    def _parse_udt_member(self, line: str):
        # Ignore comments or lines without declarations
        if line.startswith("//") or line.startswith("COMMENT"):
            return
            
        # Strip trailing semicolon for regex
        if line.endswith(";"):
            line = line[:-1]
            
        # Standard member (Name : Type)
        m = self.re_member.search(line)
        if m:
            name = m.group("name")
            data_type = m.group("type")
            array_dim = m.group("array")
            props = m.group("props")
            
            desc = self._extract_desc(props) if props else None
            hidden = self._extract_hidden(props) if props else False
            
            self.db.insert_udt_member(self.current_udt_id, name, data_type, array_dim, hidden, desc)
        else:
            # Maybe it doesn't have the colon, like `DINT Status;` in UDTs
            parts = line.split()
            if len(parts) >= 2:
                # E.g. "DINT Status" -> type=DINT, name=Status
                # Could be "REAL Value (Description := ...)"
                data_type = parts[0]
                # the rest is name and props
                rest = " ".join(parts[1:])
                # find first space or paren to separate name from props
                name_match = re.match(r"^([a-zA-Z0-9_]+)(?:\[[\d,\s]+\])?(.*)", rest)
                if name_match:
                    name = name_match.group(1)
                    props = name_match.group(2)
                    array_dim = re.search(r"(\[[\d,\s]+\])", rest)
                    array_dim = array_dim.group(1) if array_dim else None
                    desc = self._extract_desc(props) if props else None
                    hidden = self._extract_hidden(props) if props else False
                    self.db.insert_udt_member(self.current_udt_id, name, data_type, array_dim, hidden, desc)

    def _parse_tag(self, line: str):
        if line.startswith("//") or line.startswith("COMMENT"):
            return
            
        # Strip trailing semicolon for regex
        if line.endswith(";"):
            line = line[:-1]
            
        m = self.re_alias.search(line)
        if m:
            name = m.group("name")
            alias_for = m.group("base")
            props = m.group("props")
            desc = self._extract_desc(props) if props else None
            hidden = self._extract_hidden(props) if props else False
            self.db.insert_tag(self.current_controller_id, self.current_scope, name, "ALIAS", None, alias_for, hidden, desc)
            return

        m = self.re_member.search(line)
        if m:
            name = m.group("name")
            data_type = m.group("type")
            array_dim = m.group("array")
            props = m.group("props")
            
            desc = self._extract_desc(props) if props else None
            hidden = self._extract_hidden(props) if props else False
            
            self.db.insert_tag(self.current_controller_id, self.current_scope, name, data_type, array_dim, None, hidden, desc)
