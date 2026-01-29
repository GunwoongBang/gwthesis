-- name: RESET_DATABASE
MATCH (n) DETACH DELETE n

-- name: ENSURE_SCHEMA_SPACES
CREATE CONSTRAINT space_id IF NOT EXISTS FOR (s:Space) REQUIRE s.id IS UNIQUE

-- name: ENSURE_SCHEMA_WALLS
CREATE CONSTRAINT wall_id IF NOT EXISTS FOR (w:Wall) REQUIRE w.id IS UNIQUE

-- name: ENSURE_SCHEMA_LAYERS
CREATE CONSTRAINT layer_id IF NOT EXISTS FOR (l:Layer) REQUIRE l.id IS UNIQUE

-- name: UPSERT_SPACES
UNWIND $spaces AS space
MERGE (s:Space {id: space.id})
SET s.name = space.name,
    s.longName = space.longName,
    s.ifcClass = space.ifcClass

-- name: UPSERT_WALLS
UNWIND $walls AS wall
MERGE (w:Wall {id: wall.id})
SET w.name = wall.name,
    w.ifcClass = wall.ifcClass,
    w.loadBearing = wall.loadBearing,
    w.isExternal = wall.isExternal

-- name: UPSERT_LAYERS
UNWIND $layers AS layer
MERGE (l:Layer {id: layer.id})
SET l.name = layer.name,
    l.ifcClass = layer.ifcClass,
    l.layerIndex = layer.layerIndex,
    l.thickness = layer.thickness

-- name: CREATE_WALL_LAYER_EDGES
UNWIND $layers AS layer
MATCH (w:Wall {id: layer.wall_id})
MATCH (l:Layer {id: layer.id})
MERGE (w)-[:HAS_LAYER]->(l)
SET l.layerIndex = layer.layerIndex

-- name: CREATE_SPACE_WALL_EDGES
UNWIND $edges AS edge
MATCH (s:Space {id: edge.space_id})
MATCH (w:Wall {id: edge.wall_id})
MERGE (s)-[r:BOUNDED_BY]->(w)
SET r.directionSense = edge.directionSense
