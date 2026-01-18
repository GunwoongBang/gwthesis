from neo4j import GraphDatabase
import bim2graph
import logger as logger

ARC_PATH = "ifc_models/BIMcollab/BIMcollab_ARC.ifc"

NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "Bs13246578!"

divider = "-" * 50


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
        # region: BIM2GRAPH
        bim2graph.generate_graph(driver)  # Generate a BIM-derived graph from BIM models
        # regionEnd

        # region: SENSOR2GRAPH
        # regionEnd

        # region: GRAPH MERGING
        # regionEnd
        
    finally:
        # Ensure driver is always closed
        driver.close()
        logger.logText("Divider", divider)
        logger.logText("PROJECT", "Neo4j driver closed")
    
    logger.logText("PROJECT", "Ended")
