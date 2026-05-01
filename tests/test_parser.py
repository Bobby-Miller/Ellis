import json
from src.database.db import Database
from src.parser.l5k_parser import L5KParser
from src.exporter.exporter import IgnitionExporter
from src.config.config import ExportConfig

def test_parser():
    db = Database(":memory:") # In-memory
    parser = L5KParser(db)
    
    # Let's parse a small subset of an L5K file to test
    with open("test.L5K", "w") as f:
        f.write("""
CONTROLLER PLC_Test (ProcessorType := "1768-L45")
    DATATYPE MyUDT
        DINT Status;
        REAL Value (Description := "A Value");
    END_DATATYPE
    
    ADD_ON_INSTRUCTION_DEFINITION MyAOI
        LOCAL_TAGS
            DINT LocalVal;
        END_LOCAL_TAGS
        PARAMETERS
            REAL InVal;
        END_PARAMETERS
    END_ADD_ON_INSTRUCTION_DEFINITION

    TAG
        PT001 : REAL (Description := "Pressure Trans");
        ArrayTag : DINT[10];
        AliasTag OF PT001;
        UDT_Tag : MyUDT;
    END_TAG

    PROGRAM MainProgram
        TAG
            PCVD_Seal_Pressure : REAL;
            LocalArr : REAL[5,5];
        END_TAG
    END_PROGRAM
        """)
        
    file_id = db.insert_file("test.L5K")
    parser.parse_file("test.L5K", file_id)
    
    print("DB STATS:")
    print("Controllers:", db.conn.execute("SELECT count(*) FROM controllers").fetchone()[0])
    print("UDTs:", db.conn.execute("SELECT count(*) FROM udts").fetchone()[0])
    print("MEMBERS:", db.conn.execute("SELECT count(*) FROM udt_members").fetchone()[0])
    print("TAGS:", db.conn.execute("SELECT count(*) FROM tags").fetchone()[0])
    
    assert db.conn.execute("SELECT count(*) FROM controllers").fetchone()[0] == 1
    assert db.conn.execute("SELECT count(*) FROM udts").fetchone()[0] == 2
    assert db.conn.execute("SELECT count(*) FROM udt_members").fetchone()[0] == 2
    
    tags = db.conn.execute("SELECT * FROM tags").fetchall()
    assert len(tags) == 6
    
    print("Database validation passed!")
    
    # Write a temporary config file for testing config logic
    test_config_data = {
        "database": ":memory:",
        "tags": {
            "PT001": {"export": True, "rename": "PressureTransmitter001"},
            "ArrayTag": {"export": True},
            "AliasTag": {"export": True},
            "UDT_Tag": {"export": True},
            "MainProgram.PCVD_Seal_Pressure": {"export": True, "rename": "Seal_Pressure"}
        }
    }
    with open("test_config.json", "w") as f:
        json.dump(test_config_data, f)
        
    config = ExportConfig("test_config.json")
    
    # Exporter Test
    exporter = IgnitionExporter(db, config)
    result = exporter.export()
    
    print(json.dumps(result, indent=2))
    
    # Check array tag handling
    for t in result['tags'][1]['tags']:
        if t['name'] == 'ArrayTag':
            assert t['dataType'] == 'Int4Array'
            
    # Check program folder
    prog_folder = next((t for t in result['tags'][1]['tags'] if t.get('tagType') == 'Folder'), None)
    assert prog_folder is not None
    assert prog_folder['name'] == 'MainProgram'
    assert prog_folder['tags'][0]['name'] == 'Seal_Pressure'

if __name__ == "__main__":
    test_parser()
