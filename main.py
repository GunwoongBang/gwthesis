import logger as logger
import ifc_to_neo4j

if __name__ == "__main__":
    logger.logText("PROJECT", "Started")
    #region: BIM2GRAPH 
    ifc_to_neo4j.generate_graph() # Generate a BIM-derived graph from BIM models
    #regionEnd
    
    #region: SENSOR2GRAPH
    #regionEnd
    
    #region: GRAPH MERGING
    #regionEnd
    logger.logText("PROJECT", "Ended")