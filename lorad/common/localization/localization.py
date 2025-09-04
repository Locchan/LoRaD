from lorad.common.localization.dictionary import DICTIONARY, ENABLED_LOCS, DEFAULT_LOCALE
from lorad.common.utils import globs
from lorad.common.utils.logger import get_logger
from lorad.common.utils.misc import read_config

logger = get_logger()
config = read_config()

def set_global_locale():
    locale = config["LOCALE"]
    locale_found = False
    for alocale in ENABLED_LOCS:
        if alocale["code"] == locale:
            locale_found = True
    if locale_found:
        logger.info(f"Setting locale to {locale}.")
        globs.LOCALE = locale
    if not locale_found:
        globs.LOCALE = DEFAULT_LOCALE
        logger.warning(f"Locale {locale} not found, defaulting to {DEFAULT_LOCALE['code']}.")

def init_localization():
    logger.info("Initializing localization...")
    set_global_locale()
    for anitem in DICTIONARY:
        for alang in ENABLED_LOCS:
            if anitem not in alang["data"]:
                logger.warning(f"{anitem} is not localized for {alang['code']}")

def get_loc(string_name):
    locale = globs.LOCALE
    if string_name in DICTIONARY:
        for alocale in ENABLED_LOCS:
            if locale == alocale["code"]:
                if string_name in alocale["data"]:
                    return alocale["data"][string_name]
                else:
                    return string_name
        return "LOCALIZATION ERROR"
    else:
        return f"UNKNOWN STRING: {string_name}"
