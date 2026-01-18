import ifcopenshell
import logger as logger

ARC_PATH = "ifc_models/BIMcollab/BIMcollab_ARC.ifc"

MIN_WALLS_PER_SPACE = 0


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
    properties = {
        "id": wall.GlobalId,
        "name": safe_str(getattr(wall, "Name", None)),
        "longName": safe_str(getattr(wall, "LongName", None)),
        "description": safe_str(getattr(wall, "Description", None)),
        # "objectType": safe_str(getattr(wall, "ObjectType", None)),
        "ifcClass": wall.is_a(),
        "loadBearing": None,
        "isExternal": None,
    }

    # Extract properties as attributes
    if hasattr(wall, "IsDefinedBy"):
        for rel in wall.IsDefinedBy:
            if rel.is_a("IfcRelDefinesByProperties"):
                prop_set = rel.RelatingPropertyDefinition
                if prop_set.is_a("IfcPropertySet"):
                    if hasattr(prop_set, "HasProperties"):
                        for prop in prop_set.HasProperties:
                            if prop.is_a("IfcPropertySingleValue"):
                                value = getattr(prop, "NominalValue", None)
                                if value is not None:
                                    if prop.Name == "LoadBearing":
                                        if hasattr(value, "wrappedValue"):
                                            properties["loadBearing"] = value.wrappedValue
                                        else:
                                            properties["loadBearing"] = str(
                                                value)
                                    elif prop.Name == "IsExternal":
                                        if hasattr(value, "wrappedValue"):
                                            properties["isExternal"] = value.wrappedValue
                                        else:
                                            properties["isExternal"] = str(
                                                value)

    return properties


def extract_materials(wall):
    """Extract material information separately for creating Material nodes and Layer nodes"""
    wall_layers = []
    wall_materials = []

    if hasattr(wall, "HasAssociations"):
        for assoc in wall.HasAssociations:
            if assoc.is_a("IfcRelAssociatesMaterial"):
                material = assoc.RelatingMaterial
                wall_id = wall.GlobalId

                if material.is_a("IfcMaterial"):
                    # Single material - use name-based ID for deduplication
                    mat_name = material.Name if hasattr(
                        material, 'Name') and material.Name else f"unnamed_mat_{id(material)}"
                    mat_id = f"mat_{mat_name.replace(' ', '_').replace('-', '_')}"

                    # Create a layer node for single material (layer 0)
                    layer_id = f"{wall_id}_layer_0"
                    wall_layers.append({
                        "layer_id": layer_id,
                        "wall_id": wall_id,
                        "layerIndex": 0,
                        "thickness": None,
                        "directionSense": None,
                        "offsetFromReferenceLine": None,
                        "material_id": mat_id
                    })

                    wall_materials.append({
                        "material_id": mat_id,
                        "name": material.Name,
                        "description": safe_str(getattr(material, "Description", None)),
                        "type": "single"
                    })

                elif material.is_a("IfcMaterialList"):
                    # Simple material list - use name-based IDs for deduplication
                    for i, mat in enumerate(material.Materials):
                        mat_name = mat.Name if hasattr(
                            mat, 'Name') and mat.Name else f"unnamed_mat_{id(mat)}"
                        mat_id = f"mat_{mat_name.replace(' ', '_').replace('-', '_')}"

                        # Create layer node for each material in list
                        layer_id = f"{wall_id}_list_layer_{i}"
                        wall_layers.append({
                            "layer_id": layer_id,
                            "wall_id": wall_id,
                            "layerIndex": i,
                            "thickness": None,
                            "directionSense": None,
                            "offsetFromReferenceLine": None,
                            "material_id": mat_id
                        })

                        wall_materials.append({
                            "material_id": mat_id,
                            "name": mat.Name if hasattr(mat, "Name") else None,
                            "description": safe_str(getattr(mat, "Description", None)),
                            "type": "list_item"
                        })

                elif material.is_a("IfcMaterialLayerSetUsage"):
                    # Detailed layered construction - use name-based IDs for deduplication
                    layer_set = material.ForLayerSet
                    if layer_set and hasattr(layer_set, "MaterialLayers"):
                        for i, layer in enumerate(layer_set.MaterialLayers):
                            if layer.Material:
                                mat_name = layer.Material.Name if hasattr(
                                    layer.Material, 'Name') and layer.Material.Name else f"unnamed_mat_{id(layer.Material)}"
                                mat_id = f"mat_{mat_name.replace(' ', '_').replace('-', '_')}"
                            else:
                                mat_id = f"layer_{i}_empty"

                            # Create layer node for each layer
                            layer_id = f"{wall_id}_layer_{i}"
                            wall_layers.append({
                                "layer_id": layer_id,
                                "wall_id": wall_id,
                                "layerIndex": i,
                                "thickness": getattr(layer, "LayerThickness", None),
                                "directionSense": getattr(material, "DirectionSense", None),
                                "offsetFromReferenceLine": getattr(material, "OffsetFromReferenceLine", None),
                                "material_id": mat_id
                            })

                            wall_materials.append({
                                "material_id": mat_id,
                                "name": layer.Material.Name if layer.Material else None,
                                "description": safe_str(getattr(layer.Material, "Description", None)) if layer.Material else None,
                                "type": "layer"
                            })

                elif material.is_a("IfcMaterialLayerSet"):
                    # Direct layer set reference - use name-based IDs for deduplication
                    for i, layer in enumerate(material.MaterialLayers):
                        if layer.Material:
                            mat_name = layer.Material.Name if hasattr(
                                layer.Material, 'Name') and layer.Material.Name else f"unnamed_mat_{id(layer.Material)}"
                            mat_id = f"mat_{mat_name.replace(' ', '_').replace('-', '_')}"
                        else:
                            mat_id = f"layer_{i}_empty"

                        # Create layer node for each layer
                        layer_id = f"{wall_id}_layer_{i}"
                        wall_layers.append({
                            "layer_id": layer_id,
                            "wall_id": wall_id,
                            "layerIndex": i,
                            "thickness": getattr(layer, "LayerThickness", None),
                            "directionSense": None,
                            "offsetFromReferenceLine": None,
                            "material_id": mat_id
                        })

                        wall_materials.append({
                            "material_id": mat_id,
                            "name": layer.Material.Name if layer.Material else None,
                            "description": safe_str(getattr(layer.Material, "Description", None)) if layer.Material else None,
                            "type": "layer"
                        })

    return wall_layers, wall_materials


def extract_walls(model):
    walls = []
    materials = []
    layers = []

    for cls in ("IfcWall", "IfcWallStandardCase"):
        for wall in model.by_type(cls):
            wall_data = extract_wall_properties(wall)
            walls.append(wall_data)

            # Extract materials and layers separately
            wall_layers, wall_materials = extract_materials(wall)
            layers.extend(wall_layers)
            materials.extend(wall_materials)

    walls = list({w["id"]: w for w in walls}.values())
    # Deduplicate materials and layers
    layers = list({l["layer_id"]: l for l in layers}.values())
    materials = list({m["material_id"]: m for m in materials}.values())

    logger.logText("BIM2GRAPH", f"{len(walls)} Wall elements extracted")
    logger.logText("BIM2GRAPH", f"{len(layers)} Layer element extracted")
    logger.logText("BIM2GRAPH", f"{len(materials)} Material elements extracted")
    return walls, layers, materials


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

    edges = [(sid, wid) for sid, wids in space_to_walls.items()
             for wid in wids]
    counts = {sid: len(wids) for sid, wids in space_to_walls.items()}

    logger.logText("BIM2GRAPH", f"{len(edges)} Space-Wall edges extracted")

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


'''
TODO
Currently the graph is missing the following:
- Semantic enrichment for material order/thickness (BIMcollab)
'''
# --- Neo4j functions ---


def reset_database(tx):
    tx.run("MATCH (n) DETACH DELETE n")


def ensure_schema(tx):
    tx.run("CREATE CONSTRAINT space_id IF NOT EXISTS FOR (s:Space) require s.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT wall_id IF NOT EXISTS FOR (w:Wall) require w.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT layer_id IF NOT EXISTS FOR (l:Layer) require l.id IS UNIQUE")
    tx.run("CREATE CONSTRAINT material_id IF NOT EXISTS FOR (m:Material) require m.id IS UNIQUE")


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
    tx.run(
        """
        UNWIND $walls AS wall
        MERGE (w:Wall {id: wall.id})
        SET w.name = wall.name,
            w.longName = wall.longName,
            w.description = wall.description,
            w.objectType = wall.objectType,
            w.ifcClass = wall.ifcClass,
            w.loadBearing = wall.loadBearing,
            w.isExternal = wall.isExternal
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
            m.type = material.type
        """,
        materials=materials,
    )


def upsert_layers(tx, layers):
    tx.run(
        """
        UNWIND $layers AS layer
        MERGE (l:Layer {id: layer.layer_id})
        SET l.layerIndex = layer.layerIndex,
            l.thickness = layer.thickness,
            l.directionSense = layer.directionSense,
            l.offsetFromReferenceLine = layer.offsetFromReferenceLine
        """,
        layers=layers,
    )


def upsert_wall_layer_edges(tx, wall_layers):
    tx.run(
        """
        UNWIND $wall_layers AS wl
        MATCH (w:Wall {id: wl.wall_id})
        MATCH (l:Layer {id: wl.layer_id})
        MERGE (w)-[:HAS_LAYER]->(l)
        """,
        wall_layers=wall_layers,
    )


def upsert_layer_material_edges(tx, wall_layers):
    tx.run(
        """
        UNWIND $wall_layers AS wl
        MATCH (l:Layer {id: wl.layer_id})
        MATCH (m:Material {id: wl.material_id})
        MERGE (l)-[:HAS_MATERIAL]->(m)
        """,
        wall_layers=wall_layers,
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


def generate_graph(driver):
    arc = ifcopenshell.open(ARC_PATH)

    spaces = extract_spaces(arc)
    walls, layers, materials = extract_walls(arc)

    edges_and_counts = extract_space_wall_edges_and_counts(arc)
    spaces, edges = filter_spaces_by_wall_count(
        spaces, edges_and_counts, MIN_WALLS_PER_SPACE
    )

    with driver.session() as session:
        session.execute_write(reset_database)
        session.execute_write(ensure_schema)

        session.execute_write(upsert_spaces, spaces)
        session.execute_write(upsert_walls, walls)
        session.execute_write(upsert_layers, layers)
        session.execute_write(upsert_materials, materials)
        session.execute_write(upsert_space_wall_edges, edges)
        session.execute_write(upsert_wall_layer_edges, layers)
        session.execute_write(upsert_layer_material_edges, layers)
    logger.logText("BIM2GRAPH", "BIM2GRAPH done")
