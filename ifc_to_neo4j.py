import ifcopenshell
from neo4j import GraphDatabase
import logger as logger

ARC_PATH = "ifc_models/BIMcollab/01_BIMcollab_Example_ARC.ifc"

NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "Bs13246578!"

MIN_WALLS_PER_SPACE = 4

def safe_str(x):
    return str(x) if x is not None else None

def extract_spaces(model):
    spaces = []
    for space in model.by_type("IfcSpace"):
        name = safe_str(getattr(space, "LongName", None)) or safe_str(space.Name) or space.GlobalId
        spaces.append({"id": space.GlobalId, "name": name, "ifcClass": space.is_a()})
    logger.logText("BIM2GRAPH", f"{len(spaces)} Space elements extracted")
    return spaces

def extract_walls(model):
    walls = []
    for cls in ("IfcWall", "IfcWallStandardCase"):
        for wall in model.by_type(cls):
            name = safe_str(getattr(wall, "LongName", None)) or safe_str(wall.Name) or wall.GlobalId
            walls.append({"id": wall.GlobalId, "name": name, "ifcClass": wall.is_a()})

    walls = list({w["id"]: w for w in walls}.values())
    logger.logText("BIM2GRAPH", f"{len(walls)} Wall elements extracted")
    return walls

def extract_space_wall_edges_and_counts(model):
    space_to_walls = {}

    for rel in model.by_type("IfcRelSpaceBoundary"):
        space = getattr(rel, "RelatingSpace", None)
        elem  = getattr(rel, "RelatedBuildingElement", None)
        if not space or not elem:
            continue

        if elem.is_a() in ("IfcWall", "IfcWallStandardCase"):
            sid = space.GlobalId
            wid = elem.GlobalId
            space_to_walls.setdefault(sid, set()).add(wid)

    # edges = one edge per (space, unique wall)
    edges = [(sid, wid) for sid, wids in space_to_walls.items() for wid in wids]
    counts = {sid: len(wids) for sid, wids in space_to_walls.items()}

    return edges, counts

def filter_spaces_by_wall_count(spaces, edges, min_walls=4):
    """
    Keeps only spaces with >= min_walls wall boundaries.
    Also filters edges to only those spaces.
    """
    edges, counts = edges

    allowed_space_ids = {sid for sid, cnt in counts.items() if cnt >= min_walls}

    filtered_spaces = [s for s in spaces if s["id"] in allowed_space_ids]
    filtered_edges = [(sid, wid) for (sid, wid) in edges if sid in allowed_space_ids]

    logger.logText(
        "BIM2GRAPH",
        f"Spaces kept (>= {min_walls} walls): {len(filtered_spaces)} / {len(spaces)}"
    )

    # Optional: log which ones were dropped
    dropped = [s for s in spaces if s["id"] not in allowed_space_ids]
    if dropped:
        logger.logText("BIM2GRAPH", f"Spaces dropped (< {min_walls} walls): {len(dropped)}")

    return filtered_spaces, filtered_edges

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
        rooms=rooms,
    )

def upsert_walls(tx, walls):
    tx.run(
        """
        UNWIND $walls AS wall
        MERGE (w:Wall {id: wall.id})
        SET w.name = wall.name,
            w.ifcClass = wall.ifcClass
        """,
        walls=walls,
    )

def upsert_room_wall_edges(tx, edges):
    tx.run(
        """
        UNWIND $edges AS e
        MATCH (r:Room {id: e[0]})
        MATCH (w:Wall {id: e[1]})
        MERGE (r)-[:BOUNDED_BY]->(w)
        """,
        edges=edges,
    )

def generate_graph():
    arc = ifcopenshell.open(ARC_PATH)

    spaces = extract_spaces(arc)
    walls = extract_walls(arc)

    edges_and_counts = extract_space_wall_edges_and_counts(arc)
    spaces, edges = filter_spaces_by_wall_count(spaces, edges_and_counts, MIN_WALLS_PER_SPACE)

    logger.logText("BIM2GRAPH", f"Edges to upload: {len(edges)}")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        session.execute_write(reset_database)
        session.execute_write(ensure_schema)

        session.execute_write(upsert_rooms, spaces)
        session.execute_write(upsert_walls, walls)
        session.execute_write(upsert_room_wall_edges, edges)

    driver.close()
    logger.logText("BIM2GRAPH", "Graph upload done")
