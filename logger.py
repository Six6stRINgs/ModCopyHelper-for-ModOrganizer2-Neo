import logging
import mobase
from pathlib import Path

PLUGIN_NAME = "ModCopyHelper"  

def setup_logger(organizer: mobase.IOrganizer) -> logging.Logger:
    log_level_str = organizer.pluginSetting(PLUGIN_NAME, "logLevel")
    log_level = logging.INFO
    if log_level_str: 
        log_level_str = log_level_str.lower()
        if log_level_str == "debug":
            log_level = logging.DEBUG
        elif log_level_str == "warning":
            log_level = logging.WARNING
        elif log_level_str == "error":
            log_level = logging.ERROR

    logger = logging.getLogger(PLUGIN_NAME)
    logger.setLevel(log_level)

    if logger.hasHandlers():
        logger.handlers.clear()

    class MO2LogHandler(logging.Handler):
        def __init__(self, organizer_obj: mobase.IOrganizer):
            super().__init__()
            self._organizer = organizer_obj

        def emit(self, record: logging.LogRecord):
            log_entry = self.format(record)
            try:
                self._organizer.logMessage(log_entry, record.levelno)
            except AttributeError as e_attr:
                print(f"MO2 Logging Fallback (AttributeError for logMessage): {e_attr} - Message: {log_entry}")
            except Exception as e_other:
                print(f"MO2 Logging Fallback (Other Exception for logMessage): {e_other} - Message: {log_entry}")
                            
    mo2_handler = MO2LogHandler(organizer)
    formatter = logging.Formatter(f'%(asctime)s - {PLUGIN_NAME} - %(levelname)s - %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    mo2_handler.setFormatter(formatter)
    logger.addHandler(mo2_handler)

    try:
        plugin_data_base_path = Path(organizer.paths().pluginDataPath())
        plugin_data_path = plugin_data_base_path / PLUGIN_NAME.lower().replace(" ", "_")
        plugin_data_path.mkdir(parents=True, exist_ok=True)
        log_file = plugin_data_path / f"{PLUGIN_NAME.lower().replace(' ', '_')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.info(f"File logging to: {log_file}")
    except Exception as e:
        logger.warning(f"Failed to set up file logger: {e}", exc_info=True)

    logger.info(f"{PLUGIN_NAME} logger initialized with level {logging.getLevelName(log_level)}.")
    return logger

LOGGER: logging.Logger = logging.getLogger(PLUGIN_NAME)

def get_logger() -> logging.Logger:
    return LOGGER