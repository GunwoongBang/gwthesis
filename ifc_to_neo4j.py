import ifcopenshell
from neo4j import GraphDatabase
import logger as logger

ARC_PATH = "ifc_models/BIMcollab/01_BIMcollab_Example_ARC.ifc"

NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "Bs13246578!"

MIN_WALLS_PER_SPACE = 2


def safe_str(x):
    return str(x) if x is not None else None


def extract_spaces(model):
    spaces = []
    for space in model.by_type("IfcSpace"):
        name = (
            safe_str(getattr(space, "LongName", None))
            or safe_str(space.Name)
            or space.GlobalId
        )
        spaces.append({"id": space.GlobalId, "name": name,
                      "ifcClass": space.is_a()})
    logger.logText("BIM2GRAPH", f"{len(spaces)} Space elements extracted")
    return spaces


def extract_wall_properties(wall):
    """Extract basic wall properties (excluding materials for separate processing)"""
    properties = {
        "id": wall.GlobalId,
        "name": safe_str(getattr(wall, "Name", None)),
        "longName": safe_str(getattr(wall, "LongName", None)),
        "description": safe_str(getattr(wall, "Description", None)),
        "objectType": safe_str(getattr(wall, "ObjectType", None)),
        "ifcClass": wall.is_a(),
        "tag": safe_str(getattr(wall, "Tag", None)),
    }

    # Extract property sets
    if hasattr(wall, "IsDefinedBy"):
        property_sets = {}
        for rel in wall.IsDefinedBy:
            if rel.is_a("IfcRelDefinesByProperties"):
                prop_set = rel.RelatingPropertyDefinition
                if prop_set.is_a("IfcPropertySet"):
                    ps_name = prop_set.Name
                    property_sets[ps_name] = {}
                    if hasattr(prop_set, "HasProperties"):
                        for prop in prop_set.HasProperties:
                            if prop.is_a("IfcPropertySingleValue"):
                                value = getattr(prop, "NominalValue", None)
                                if value is not None:
                                    if hasattr(value, "wrappedValue"):
                                        property_sets[ps_name][
                                            prop.Name
                                        ] = value.wrappedValue
                                    else:
                                        property_sets[ps_name][prop.Name] = str(
                                            value)
        properties["propertySets"] = property_sets

    return properties


def extract_wall_materials(wall):
    """Extract material information separately for creating Material nodes"""
    wall_materials = []
    
    if hasattr(wall, "HasAssociations"):
        for assoc in wall.HasAssociations:
            if assoc.is_a("IfcRelAssociatesMaterial"):
                material = assoc.RelatingMaterial
                wall_id = wall.GlobalId
                
                if material.is_a("IfcMaterial"):
                    # Single material
                    mat_global_id = getattr(material, 'GlobalId', f"mat_{id(material)}")
                    wall_materials.append({
                        "wall_id": wall_id,
                        "material_id": f"{wall_id}_mat_{mat_global_id}",
                        "name": material.Name,
                        "description": safe_str(getattr(material, "Description", None)),
                        "thickness": None,
                    })
                    
                elif material.is_a("IfcMaterialList"):
                    # Simple material list
                    for i, mat in enumerate(material.Materials):
                        mat_global_id = getattr(mat, 'GlobalId', f"mat_{id(mat)}")
                        wall_materials.append({
                            "wall_id": wall_id,
                            "material_id": f"{wall_id}_list_{i}_{mat_global_id}",
                            "name": mat.Name if hasattr(mat, "Name") else None,
                            "description": safe_str(getattr(mat, "Description", None)),
                            "thickness": None,
                        })
                        
                elif material.is_a("IfcMaterialLayerSetUsage"):
                    # Detailed layered construction
                    layer_set = material.ForLayerSet
                    if layer_set and hasattr(layer_set, "MaterialLayers"):
                        for i, layer in enumerate(layer_set.MaterialLayers):
                            mat_global_id = getattr(layer.Material, 'GlobalId', f"mat_{id(layer.Material)}") if layer.Material else f"layer_{i}"
                            wall_materials.append({
                                "wall_id": wall_id,
                                "material_id": f"{wall_id}_layer_{i}_{mat_global_id}",
                                "name": layer.Material.Name if layer.Material else None,
                                "description": safe_str(getattr(layer.Material, "Description", None)) if layer.Material else None,
                                "type": "layer",
                                "thickness": getattr(layer, "LayerThickness", None),
                                "directionSense": getattr(material, "DirectionSense", None),
                                "offsetFromReferenceLine": getattr(material, "OffsetFromReferenceLine", None),
                                "layerIndex": i
                            })
                            
                elif material.is_a("IfcMaterialLayerSet"):
                    # Direct layer set reference
                    for i, layer in enumerate(material.MaterialLayers):
                        mat_global_id = getattr(layer.Material, 'GlobalId', f"mat_{id(layer.Material)}") if layer.Material else f"layer_{i}"
                        wall_materials.append({
                            "wall_id": wall_id,
                            "material_id": f"{wall_id}_layer_{i}_{mat_global_id}",
                            "name": layer.Material.Name if layer.Material else None,
                            "description": safe_str(getattr(layer.Material, "Description", None)) if layer.Material else None,
                            "type": "layer",
                            "thickness": getattr(layer, "LayerThickness", None),
                            "directionSense": None,
                            "offsetFromReferenceLine": None,
                            "layerIndex": i
                        })
    
    return wall_materials


def extract_walls(model):
    walls = []
    wall_materials = []
    
    for cls in ("IfcWall", "IfcWallStandardCase"):
        for wall in model.by_type(cls):
            wall_data = extract_wall_properties(wall)
            walls.append(wall_data)
            
            # Extract materials separately
            wall_materials.extend(extract_wall_materials(wall))

    walls = list({w["id"]: w for w in walls}.values())
    logger.logText("BIM2GRAPH", f"{len(walls)} Wall elements extracted")
    logger.logText("BIM2GRAPH", f"{len(wall_materials)} Wall-Material associations extracted")
    return walls, wall_materials


def extract_space_wall_edges_and_counts(model):
    space_to_walls = {}

    for rel in model.by_type("IfcRelSpaceBoundary"):
        space = getattr(rel, "RelatingSpace", None)
        elem = getattr(rel, "RelatedBuildingElement", None)
        if not space or not elem:
            continue

        if elem.is_a() in ("IfcWall", "IfcWallStandardCase"):
            sid = space.GlobalId
            wid = elem.GlobalId
            space_to_walls.setdefault(sid, set()).add(wid)

    # edges = one edge per (space, unique wall)
    edges = [(sid, wid) for sid, wids in space_to_walls.items()
             for wid in wids]
    counts = {sid: len(wids) for sid, wids in space_to_walls.items()}

    logger.logText("BIM2GRAPH", f"{len(edges)} edges extracted")

    return edges, counts


def filter_spaces_by_wall_count(spaces, edges, min_walls):
    """
    Keeps only spaces with >= min_walls wall boundaries.
    Also filters edges to only those spaces.
    """
    edges, counts = edges

    allowed_space_ids = {sid for sid,
                         cnt in counts.items() if cnt >= min_walls}

    filtered_spaces = [s for s in spaces if s["id"] in allowed_space_ids]
    filtered_edges = [(sid, wid)
                      for (sid, wid) in edges if sid in allowed_space_ids]

    return filtered_spaces, filtered_edges


# --- Neo4j functions ---


def reset_database(tx):
    tx.run("MATCH (n) DETACH DELETE n")


def ensure_schema(tx):
    tx.run(
        "CREATE CONSTRAINT space_id IF NOT EXISTS FOR (s:Space) REQUIRE s.id IS UNIQUE"
    )
    tx.run(
        "CREATE CONSTRAINT wall_id IF NOT EXISTS FOR (w:Wall) REQUIRE w.id IS UNIQUE"
    )
    tx.run(
        "CREATE CONSTRAINT material_id IF NOT EXISTS FOR (m:Material) REQUIRE m.id IS UNIQUE"
    )


def upsert_spaces(tx, spaces):
    tx.run(
        """
        UNWIND $spaces AS space
        MERGE (s:Space {id: space.id})
        SET s.name = space.name,
            s.ifcClass = space.ifcClass
        """,
        spaces=spaces,
    )


def upsert_walls(tx, walls):
    # Convert propertySets to JSON strings for Neo4j compatibility
    for wall in walls:
        if 'propertySets' in wall and wall['propertySets']:
            import json
            wall['propertySetsJson'] = json.dumps(wall['propertySets'])
        else:
            wall['propertySetsJson'] = None
    
    tx.run(
        """
        UNWIND $walls AS wall
        MERGE (w:Wall {id: wall.id})
        SET w.name = wall.name,
            w.longName = wall.longName,
            w.description = wall.description,
            w.objectType = wall.objectType,
            w.ifcClass = wall.ifcClass,
            w.tag = wall.tag,
            w.propertySets = wall.propertySetsJson
        """,
        walls=walls,
    )


def upsert_materials(tx, materials):
    tx.run(
        """
        UNWIND $materials AS material
        MERGE (m:Material {id: material.material_id})
        SET m.name = material.name,
            m.description = material.description,
            m.type = material.type,
            m.thickness = material.thickness,
            m.directionSense = material.directionSense,
            m.offsetFromReferenceLine = material.offsetFromReferenceLine,
            m.layerIndex = material.layerIndex
        """,
        materials=materials,
    )


def upsert_wall_material_edges(tx, wall_materials):
    tx.run(
        """
        UNWIND $wall_materials AS wm
        MATCH (w:Wall {id: wm.wall_id})
        MATCH (m:Material {id: wm.material_id})
        MERGE (w)-[:HAS_MATERIAL]->(m)
        """,
        wall_materials=wall_materials,
    )


def upsert_space_wall_edges(tx, edges):
    tx.run(
        """
        UNWIND $edges AS e
        MATCH (s:Space {id: e[0]})
        MATCH (w:Wall {id: e[1]})
        MERGE (s)-[:BOUNDED_BY]->(w)
        """,
        edges=edges,
    )


def generate_graph():
    arc = ifcopenshell.open(ARC_PATH)

    spaces = extract_spaces(arc)
    walls, wall_materials = extract_walls(arc)

    edges_and_counts = extract_space_wall_edges_and_counts(arc)
    spaces, edges = filter_spaces_by_wall_count(
        spaces, edges_and_counts, MIN_WALLS_PER_SPACE
    )

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        session.execute_write(reset_database)
        session.execute_write(ensure_schema)

        session.execute_write(upsert_spaces, spaces)
        session.execute_write(upsert_walls, walls)
        session.execute_write(upsert_materials, wall_materials)
        session.execute_write(upsert_space_wall_edges, edges)
        session.execute_write(upsert_wall_material_edges, wall_materials)

    driver.close()
    logger.logText("BIM2GRAPH", "BIM2GRAPH done")
