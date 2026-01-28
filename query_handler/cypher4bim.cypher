// Query 1: Find all walls with loadBearing=true
MATCH (w:Wall {loadBearing: true})
RETURN w.id as id, w.name as name, w.ifcClass as ifcClass, w.isExternal as isExternal
ORDER BY w.name;

// Query 2: Find all external walls
MATCH (w:Wall {isExternal: true})
RETURN w.id as id, w.name as name, w.ifcClass as ifcClass, w.loadBearing as loadBearing
ORDER BY w.name;

// Query 3: Find all layers for a specific wall
MATCH (w:Wall {id: $wall_id})-[:HAS_LAYER]->(l:Layer)
RETURN w.name as wall_name, l.id as layer_id, l.name as layer_name, l.thickness as thickness, l.layerIndex as layerIndex
ORDER BY l.layerIndex;

// Query 4: Find all spaces with their bounding walls
MATCH (s:Space)-[:BOUNDED_BY]->(w:Wall)
RETURN s.id as space_id, s.name as space_name, COUNT(w) as wall_count
ORDER BY s.name;

// Query 5: Find load bearing walls that are also external
MATCH (w:Wall {loadBearing: true, isExternal: true})
RETURN w.id as id, w.name as name, w.ifcClass as ifcClass
ORDER BY w.name;

// Find all space-wall relationships with their direction sense
MATCH (s:Space)-[r:BOUNDED_BY]->(w:Wall)
RETURN s.name, w.name, r.directionSense

// Find walls facing a specific space with POSITIVE direction
MATCH (s:Space {id: $space_id})-[r:BOUNDED_BY {directionSense: "POSITIVE"}]->(w:Wall)
RETURN w.name, w.id

// Find the layer order from a space's perspective
MATCH (s:Space)-[r:BOUNDED_BY]->(w:Wall)-[:HAS_LAYER]->(l:Layer)
WHERE s.id = $space_id AND w.id = $wall_id
RETURN l.layerIndex, l.name, r.directionSense
ORDER BY CASE WHEN r.directionSense = "POSITIVE" THEN l.layerIndex ELSE -l.layerIndex END