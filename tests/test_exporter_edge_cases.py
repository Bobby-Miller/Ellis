import pytest
import json
from src.database.db import Database
from src.exporter.exporter import IgnitionExporter

class MockExportConfig:
    def should_export(self, controller: str, scope: str, name: str) -> bool:
        return True

    def get_rename(self, controller: str, scope: str, name: str) -> str:
        return name

@pytest.fixture
def test_db():
    db = Database(":memory:")
    
    # Insert File and Controller
    file_id = db.insert_file("test.L5K")
    ctrl_id = db.insert_controller(file_id, "TestPLC")

    # Insert Canonical MoveT
    move_t_id = db.insert_udt(ctrl_id, "MoveT")
    db.insert_udt_member(move_t_id, "Feedrate", "REAL")
    db.insert_udt_member(move_t_id, "Position", "REAL")
    db.insert_udt_member(move_t_id, "ZZZZZZZZZZMoveT2", "INT")

    # We will simulate a second controller with a different MoveT that has InRequest (not canonical)
    ctrl_id_2 = db.insert_controller(file_id, "TestPLC2")
    move_t_2_id = db.insert_udt(ctrl_id_2, "MoveT")
    db.insert_udt_member(move_t_2_id, "Feedrate", "REAL")
    db.insert_udt_member(move_t_2_id, "Position", "REAL")
    db.insert_udt_member(move_t_2_id, "InRequest", "BOOL") # This should be ignored by the instances since it's not in the canonical

    # Insert Tags for ctrl_id
    db.insert_tag(ctrl_id, "Global", "N", "DINT") # Should be ignored
    db.insert_tag(ctrl_id, "Global", "Selector", "SELECT_ENHANCED") # Should be ignored
    db.insert_tag(ctrl_id, "Global", "MyTimer", "TIMER") # Should map to builtin
    db.insert_tag(ctrl_id, "Global", "MyAlias", "ALIAS", alias_for="SomeBase.3") # Should infer BOOL
    db.insert_tag(ctrl_id, "Global", "MyMove", "MoveT") # Should export Feedrate and Position, skip ZZZZZZ
    
    # Insert Tags for ctrl_id_2
    db.insert_tag(ctrl_id_2, "Global", "MyMove2", "MoveT") # Should export Feedrate and Position, skip InRequest because it uses canonical
    
    return db

def test_exporter_edge_cases(test_db):
    exporter = IgnitionExporter(test_db, MockExportConfig())
    result = exporter.export()

    # Get the _types_ folder
    types_folder = next((f for f in result['tags'] if f['name'] == '_types_'), None)
    assert types_folder is not None, "Types folder should exist"

    # Find MoveT in types
    move_t_def = next((t for t in types_folder['tags'] if t['name'] == 'MoveT'), None)
    assert move_t_def is not None, "MoveT should be defined in types"
    
    # Verify ZZZZZZ is stripped from MoveT definition
    member_names = [m['name'] for m in move_t_def['tags']]
    assert "ZZZZZZZZZZMoveT2" not in member_names, "ZZZZZZ tags should be stripped from definitions"
    assert "Feedrate" in member_names
    assert "Position" in member_names
    assert "InRequest" not in member_names, "InRequest should not be in the canonical definition"

    # Verify Built-in TIMER was automatically appended
    timer_def = next((t for t in types_folder['tags'] if t['name'] == 'TIMER'), None)
    assert timer_def is not None, "TIMER builtin should be automatically injected into types"
    timer_members = [m['name'] for m in timer_def['tags']]
    assert "PRE" in timer_members
    assert "DN" in timer_members

    # Find Controller Folders
    ctrl1_folder = next((f for f in result['tags'] if f['name'] == 'TestPLC'), None)
    assert ctrl1_folder is not None
    
    ctrl2_folder = next((f for f in result['tags'] if f['name'] == 'TestPLC2'), None)
    assert ctrl2_folder is not None

    # Check tags inside TestPLC
    ctrl1_tag_names = [t['name'] for t in ctrl1_folder['tags']]
    
    # 1. Ignore 'N' tag
    assert "N" not in ctrl1_tag_names, "'N' tag should be ignored"

    # 2. Ignore SELECT_ENHANCED
    assert "Selector" not in ctrl1_tag_names, "SELECT_ENHANCED tags should be ignored"

    # 3. Builtin TIMER Instance
    my_timer = next((t for t in ctrl1_folder['tags'] if t['name'] == 'MyTimer'), None)
    assert my_timer is not None
    assert my_timer['tagType'] == 'UdtInstance'
    assert my_timer['typeId'] == 'TIMER'
    
    # 4. Alias Fallback
    my_alias = next((t for t in ctrl1_folder['tags'] if t['name'] == 'MyAlias'), None)
    assert my_alias is not None
    assert my_alias['tagType'] == 'AtomicTag'
    assert my_alias['dataType'] == 'Boolean' # Because alias_for="SomeBase.3"

    # 5. UDT Instance populated from Canonical definition (TestPLC1)
    my_move = next((t for t in ctrl1_folder['tags'] if t['name'] == 'MyMove'), None)
    assert my_move is not None
    assert my_move['tagType'] == 'UdtInstance'
    my_move_tags = [t['name'] for t in my_move['tags']]
    assert "Feedrate" in my_move_tags
    assert "Position" in my_move_tags
    assert "ZZZZZZZZZZMoveT2" not in my_move_tags

    # 6. UDT Instance populated from Canonical definition (TestPLC2 overrides shouldn't inject non-canonical elements)
    my_move_2 = next((t for t in ctrl2_folder['tags'] if t['name'] == 'MyMove2'), None)
    assert my_move_2 is not None
    my_move_2_tags = [t['name'] for t in my_move_2['tags']]
    assert "Feedrate" in my_move_2_tags
    assert "InRequest" not in my_move_2_tags, "Instance should only populate members present in the canonical UDT definition to avoid Bad_Unsupported"
