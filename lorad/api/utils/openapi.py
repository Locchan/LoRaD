from purest.docs.openapi import generate_full_openapi_spec as _generate_full_openapi_spec


def generate_full_openapi_spec():
    from lorad.api import endpoints

    return _generate_full_openapi_spec(endpoints.endpoints_to_register)
