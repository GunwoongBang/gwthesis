import ifcopenshell
from neo4j import GraphDatabase
import logger

IFC_PATH = "ifc_models/NBU_Duplex-Apt_Arch-Optimized.ifc"

NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "Bs13246578!"

logger.logText("Started")

def safe_str(x):
    return str(x) if x is not None else None

def extract_rooms(model):
    rooms = []
    for space in model.by_type("IfcSpace"):
        name = safe_str(getattr(space, "LongName", None)) or safe_str(space.Name) or space.GlobalId
        rooms.append({
            "id": space.GlobalId,
            "name": name,
            "ifcClass": space.is_a(),
        })
    return rooms

def extract_walls(model):
    walls = []
    for wall in model.by_type("IfcWall"):
        name = safe_str(getattr(wall, "LongName", None)) or safe_str(wall.Name) or wall.GlobalId
        walls.append({
            "id": wall.GlobalId,
            "name": name,
            "ifcClass": wall.is_a(),
        })
    return walls

def extract_rel(model):
    rels = []

    return rels
# --- Neo4j functions ---
def reset_database(tx):
    tx.run("MATCH (n) DETACH DELETE n")

def ensure_schema(tx):
    tx.run("CREATE CONSTRAINT room_id IF NOT EXISTS FOR (r:Room) REQUIRE r.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT wall_id IF NOT EXISTS FOR (w:Wall) REQUIRE w.id IS UNIQUE")

def upsert_rooms(tx, rooms):
    tx.run(
        """
        UNWIND $rooms AS room
        MERGE (r:Room {id: room.id})
        SET r.name = room.name,
            r.ifcClass = room.ifcClass
        """,
        rooms=rooms
    )

def upsert_walls(tx, walls):
    tx.run(
        """
        UNWIND $walls AS wall
        MERGE (w:Wall {id: wall.id})
        SET w.name = wall.name,
            w.ifcClass = wall.ifcClass
        """,
        walls = walls
    )

def main():
    model = ifcopenshell.open(IFC_PATH)
    rooms = extract_rooms(model)
    walls = extract_walls(model)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        session.execute_write(reset_database)
        # 1) schema transaction (separate)
        session.execute_write(ensure_schema)

        # 2) data transaction (separate)
        session.execute_write(upsert_rooms, rooms)
        session.execute_write(upsert_walls, walls)

    driver.close()
    logger.logText("Nodes created/updated in Neo4j")

if __name__ == "__main__":
    main()
