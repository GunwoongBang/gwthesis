import ifcopenshell
import logger as logger


def extract_spaces(model):
    """Extract all spaces from the IFC model"""
    spaces = []
    for space in model.by_type("IfcSpace"):
        space_data = {
            "id": space.GlobalId,
            "name": space.Name if hasattr(space, "Name") else "Unknown",
            "longName": space.LongName if hasattr(space, "LongName") else None,
            "ifcClass": space.is_a()
        }
        spaces.append(space_data)

    logger.logText("BIM2GRAPH", f"{len(spaces)} Space elements extracted")
    return spaces


def extract_walls(model):
    """Extract all walls from the IFC model"""
    walls = []

    # Get all walls (IfcWall includes IfcWallStandardCase as subtypes)
    for wall in model.by_type("IfcWall"):
        # Extract loadBearing and isExternal properties
        load_bearing = None
        is_external = None

        if hasattr(wall, "IsDefinedBy"):
            for rel in wall.IsDefinedBy:
                if rel.is_a("IfcRelDefinesByProperties"):
                    prop_set = rel.RelatingPropertyDefinition
                    if prop_set.is_a("IfcPropertySet"):
                        if hasattr(prop_set, "HasProperties"):
                            for prop in prop_set.HasProperties:
                                if prop.is_a("IfcPropertySingleValue"):
                                    if prop.Name == "LoadBearing":
                                        value = getattr(
                                            prop, "NominalValue", None)
                                        if value is not None:
                                            load_bearing = value.wrappedValue if hasattr(
                                                value, "wrappedValue") else str(value)
                                    elif prop.Name == "IsExternal":
                                        value = getattr(
                                            prop, "NominalValue", None)
                                        if value is not None:
                                            is_external = value.wrappedValue if hasattr(
                                                value, "wrappedValue") else str(value)

        wall_data = {
            "id": wall.GlobalId,
            "name": wall.Name if hasattr(wall, "Name") else "Unknown",
            "ifcClass": wall.is_a(),
            "loadBearing": load_bearing,
            "isExternal": is_external
        }
        walls.append(wall_data)

    logger.logText("BIM2GRAPH", f"{len(walls)} Wall elements extracted")
    return walls


def extract_layers(model, walls):
    """Extract all material layers from walls"""
    layers = []
    wall_ids = {w["id"] for w in walls}

    # Get all IFC wall objects for material lookup
    ifc_walls = {}
    for wall_type in ("IfcWall", "IfcWallStandardCase"):
        for wall in model.by_type(wall_type):
            ifc_walls[wall.GlobalId] = wall

    # Extract layers from each wall
    for wall_id, ifc_wall in ifc_walls.items():
        if wall_id not in wall_ids:
            continue

        # Check for material layer sets
        if hasattr(ifc_wall, "HasAssociations"):
            for assoc in ifc_wall.HasAssociations:
                if assoc.is_a("IfcRelAssociatesMaterial"):
                    material = assoc.RelatingMaterial

                    # Handle IfcMaterialLayerSetUsage
                    if material.is_a("IfcMaterialLayerSetUsage"):
                        layer_set = material.ForLayerSet
                        if layer_set and hasattr(layer_set, "MaterialLayers"):
                            for i, mat_layer in enumerate(layer_set.MaterialLayers):
                                layer_data = {
                                    "id": f"{wall_id}_layer_{i}",
                                    "wall_id": wall_id,
                                    "layerIndex": i,
                                    "thickness": getattr(mat_layer, "LayerThickness", None),
                                    "name": mat_layer.Material.Name if mat_layer.Material and hasattr(mat_layer.Material, "Name") else f"Layer {i}",
                                    "ifcClass": "IfcMaterialLayer"
                                }
                                layers.append(layer_data)

                    # Handle IfcMaterialLayerSet
                    elif material.is_a("IfcMaterialLayerSet"):
                        if hasattr(material, "MaterialLayers"):
                            for i, mat_layer in enumerate(material.MaterialLayers):
                                layer_data = {
                                    "id": f"{wall_id}_layer_{i}",
                                    "wall_id": wall_id,
                                    "layerIndex": i,
                                    "thickness": getattr(mat_layer, "LayerThickness", None),
                                    "name": mat_layer.Material.Name if mat_layer.Material and hasattr(mat_layer.Material, "Name") else f"Layer {i}",
                                    "ifcClass": "IfcMaterialLayer"
                                }
                                layers.append(layer_data)

    logger.logText("BIM2GRAPH", f"{len(layers)} Wall Layer elements extracted")
    return layers


def extract_space_wall_edges(model):
    """Extract space-wall relationships with direction sense"""
    edges = []

    for rel in model.by_type("IfcRelSpaceBoundary"):
        space = getattr(rel, "RelatingSpace", None)
        element = getattr(rel, "RelatedBuildingElement", None)

        if not space or not element:
            continue

        # Only process walls
        if not element.is_a("IfcWall"):
            continue

        direction_sense = getattr(rel, "DirectionSense", None)

        edge_data = {
            "space_id": space.GlobalId,
            "wall_id": element.GlobalId,
            "directionSense": direction_sense
        }
        edges.append(edge_data)

    logger.logText(
        "BIM2GRAPH", f"{len(edges)} Space-Wall edges with direction sense extracted")
    return edges


# Neo4j database operations

def reset_database(tx):
    """Delete all nodes and relationships from the database"""
    tx.run("MATCH (n) DETACH DELETE n")
    logger.logText("BIM2GRAPH", "Database reset")


def ensure_schema(tx):
    """Create unique constraints for all node types"""
    tx.run("CREATE CONSTRAINT space_id IF NOT EXISTS FOR (s:Space) REQUIRE s.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT wall_id IF NOT EXISTS FOR (w:Wall) REQUIRE w.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT layer_id IF NOT EXISTS FOR (l:Layer) REQUIRE l.id IS UNIQUE")
    logger.logText("BIM2GRAPH", "Schema constraints created")


def upsert_spaces(tx, spaces):
    """Create or update Space nodes in Neo4j"""
    tx.run(
        """
        UNWIND $spaces AS space
        MERGE (s:Space {id: space.id})
        SET s.name = space.name,
            s.longName = space.longName,
            s.ifcClass = space.ifcClass
        """,
        spaces=spaces
    )
    logger.logText("BIM2GRAPH", f"Upserted {len(spaces)} Space nodes")


def upsert_walls(tx, walls):
    """Create or update Wall nodes in Neo4j"""
    tx.run(
        """
        UNWIND $walls AS wall
        MERGE (w:Wall {id: wall.id})
        SET w.name = wall.name,
            w.ifcClass = wall.ifcClass,
            w.loadBearing = wall.loadBearing,
            w.isExternal = wall.isExternal
        """,
        walls=walls
    )
    logger.logText("BIM2GRAPH", f"Upserted {len(walls)} Wall nodes")


def upsert_layers(tx, layers):
    """Create or update Layer nodes in Neo4j"""
    tx.run(
        """
        UNWIND $layers AS layer
        MERGE (l:Layer {id: layer.id})
        SET l.name = layer.name,
            l.ifcClass = layer.ifcClass,
            l.layerIndex = layer.layerIndex,
            l.thickness = layer.thickness
        """,
        layers=layers
    )
    logger.logText("BIM2GRAPH", f"Upserted {len(layers)} Layer nodes")


def create_wall_layer_edges(tx, layers):
    """Create relationships between walls and their layers"""
    tx.run(
        """
        UNWIND $layers AS layer
        MATCH (w:Wall {id: layer.wall_id})
        MATCH (l:Layer {id: layer.id})
        MERGE (w)-[:HAS_LAYER]->(l)
        SET l.layerIndex = layer.layerIndex
        """,
        layers=layers
    )
    logger.logText(
        "BIM2GRAPH", f"Created {len(layers)} Wall-Layer relationships")


def create_space_wall_edges(tx, edges):
    """Create space-wall relationships with direction sense"""
    tx.run(
        """
        UNWIND $edges AS edge
        MATCH (s:Space {id: edge.space_id})
        MATCH (w:Wall {id: edge.wall_id})
        MERGE (s)-[r:BOUNDED_BY]->(w)
        SET r.directionSense = edge.directionSense
        """,
        edges=edges
    )
    logger.logText(
        "BIM2GRAPH", f"Created {len(edges)} Space-Wall relationships with direction sense")


def generate_graph(driver, arc_path):
    """Main function to generate the BIM graph"""

    # Load IFC model
    model = ifcopenshell.open(arc_path)

    # Extract data
    spaces = extract_spaces(model)
    walls = extract_walls(model)
    layers = extract_layers(model, walls)
    space_wall_edges = extract_space_wall_edges(model)

    # Write to Neo4j
    with driver.session() as session:
        session.execute_write(reset_database)
        session.execute_write(ensure_schema)
        session.execute_write(upsert_spaces, spaces)
        session.execute_write(upsert_walls, walls)
        session.execute_write(upsert_layers, layers)
        session.execute_write(create_wall_layer_edges, layers)
        session.execute_write(create_space_wall_edges, space_wall_edges)

    logger.logText("BIM2GRAPH", "BIM2GRAPH generation complete")
