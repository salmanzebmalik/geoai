import logging
import sys

# Define consistent log format
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def get_logger(name: str):
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Remove any existing handlers
        logger.propagate = False  # This prevents duplicate logs
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt=LOG_DATE_FORMAT)
        )
        logger.addHandler(handler)
    
    return logger