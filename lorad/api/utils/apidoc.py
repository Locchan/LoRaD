from purest.docs.apidoc import get_apidoc as _get_apidoc


def get_apidoc(format="html"):
    from lorad.api import endpoints

    return _get_apidoc(endpoints.endpoints_to_register, format=format)
