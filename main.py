from neo4j import GraphDatabase
import bim2graph
import logger as logger

ARC_PATH = "ifc_models/Duplex/Duplex_ARC.ifc"

NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "Bs13246578!"

divider = "-" * 100

# TODO:
# 1. Convert IFC2X3 models to IFC4 to utilize DirectionSense property in walls
# 2. Update Cypher queries to filter based on DirectionSense once IFC4 models are used
# 3. Test the extraction and graph generation with updated models


def graph_initiate():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    logger.logText("PROJECT", "Neo4j driver initiated")
    logger.logText("Divider", divider)
    return driver


if __name__ == "__main__":
    logger.logText("PROJECT", "Started")

    # Create driver once for all operations
    driver = graph_initiate()

    try:
        # ====================================================================
        # BIM2GRAPH
        # ====================================================================

        # Generate a BIM-derived graph from BIM models
        bim2graph.generate_graph(driver, ARC_PATH)

        # ====================================================================
        # SENSOR2GRAPH
        # ====================================================================

        # ====================================================================
        # GRAPH MERGING
        # ====================================================================
    finally:
        # Ensure driver is always closed
        driver.close()
        logger.logText("Divider", divider)
        logger.logText("PROJECT", "Neo4j driver closed")

    logger.logText("PROJECT", "Ended")
