import logging

logger = logging.getLogger(__name__)

def logText(text):
    logging.basicConfig(filename='shared/b2g.log', level=logging.INFO)
    logger.info(text)