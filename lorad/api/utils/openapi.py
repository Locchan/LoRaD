from lorad.api import endpoints

# GPT-heavy area

def generate_swagger_path(anendpoint):
    path_item = {}

    for method in ["get", "post", "put", "delete"]:
        impl_name = f"impl_{method.upper()}"
        if hasattr(anendpoint, impl_name):
            parameters = []

            # Add required fields
            if hasattr(anendpoint, "REQUIRED_FIELDS") and method.upper() in anendpoint.REQUIRED_FIELDS:
                for field in anendpoint.REQUIRED_FIELDS[method.upper()]:
                    parameters.append({
                        "name": field,
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"}
                    })

            # Add optional fields
            if hasattr(anendpoint, "OPTIONAL_FIELDS") and method.upper() in anendpoint.OPTIONAL_FIELDS:
                for field in anendpoint.OPTIONAL_FIELDS[method.upper()]:
                    parameters.append({
                        "name": field,
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"}
                    })

            operation = {
                "summary": anendpoint.DOCSTRING.get(method.upper(), ""),
                "parameters": parameters,
                "responses": {
                    "200": {
                        "description": "Successful response"
                    }
                }
            }

            # If login required, reference the security scheme
            if getattr(anendpoint, "LOGIN_REQUIRED", False):
                operation["security"] = [{"AuthHeader": []}]

            path_item[method] = operation

    return {anendpoint.ENDP_PATH: path_item}


def generate_full_openapi_spec():
    paths = {}
    for endpoint in endpoints.endpoints_to_register:
        paths.update(generate_swagger_path(endpoint))

    openapi_spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "LoRaD rest API",
            "version": "1.0.0"
        },
        "paths": paths,
        "components": {
            "securitySchemes": {
                "AuthHeader": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "Authorization",
                    "description": "Format: `username, token`"
                }
            }
        }
    }

    return openapi_spec
