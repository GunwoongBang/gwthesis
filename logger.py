import logging

logger = logging.getLogger('b2g')
logger.setLevel(logging.INFO)
handler = logging.FileHandler('b2g.log', mode='w')
handler.setFormatter(logging.Formatter('%(levelname)s:%(name)s:%(message)s'))
logger.addHandler(handler)

def logText(text):
    logger.info(text)