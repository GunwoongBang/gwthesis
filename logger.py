import logging

from lark import logger

handler = logging.FileHandler('log/project.log', mode='w')
# handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
handler.setFormatter(logging.Formatter('%(message)s'))

_initialized_loggers = set()

def logText(phase, text):
    logger = logging.getLogger(phase)
    if phase not in _initialized_loggers:
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        _initialized_loggers.add(phase)
    
    if (phase == "Divider"):
        logger.info(f"{text}")
    else:
        logger.info(f"{phase}: {text}")
