#!/usr/bin/env python

from lorad.api import endpoints

def generate_endpoint_plain(anendpoint):
    result = ""
    for amethod in ["GET", "POST", "PUT", "DELETE"]:
        if hasattr(anendpoint, f"impl_{amethod}"):
            result += f"{amethod}: {anendpoint.ENDP_PATH}\n"
            result += f"{anendpoint.DOCSTRING[amethod]}\n"
            params_written = False
            if hasattr(anendpoint, "REQUIRED_FIELDS") and amethod in anendpoint.REQUIRED_FIELDS:
                if not params_written:
                    result += "Parameters:\n"
                    params_written = True
                result += f"\tRequired: {', '.join(anendpoint.REQUIRED_FIELDS[amethod])}\n"
            if hasattr(anendpoint, "OPTIONAL_FIELDS") and amethod in anendpoint.OPTIONAL_FIELDS:
                if not params_written:
                    result += "Parameters:\n"
                    params_written = True
                result += f"\tOptional: {', '.join(anendpoint.OPTIONAL_FIELDS[amethod])}\n"

            if hasattr(anendpoint, "LOGIN_REQUIRED"):
                result += f"Login required: {anendpoint.LOGIN_REQUIRED}\n"
            else:
                result += f"Login required: False\n"
            result += "\n"
    return result

def generate_endpoint_html(anendpoint):
    result = "<html>"
    for amethod in ["GET", "POST", "PUT", "DELETE"]:
        if hasattr(anendpoint, f"impl_{amethod}"):
            result += f"{amethod}: {anendpoint.ENDP_PATH}<br>"
            result += f"{anendpoint.DOCSTRING[amethod]}<br>"
            params_written = False
            if hasattr(anendpoint, "REQUIRED_FIELDS") and amethod in anendpoint.REQUIRED_FIELDS:
                if not params_written:
                    result += "Parameters:<br>"
                    params_written = True
                result += f"\tRequired: {', '.join(anendpoint.REQUIRED_FIELDS[amethod])}<br>"
            if hasattr(anendpoint, "OPTIONAL_FIELDS") and amethod in anendpoint.OPTIONAL_FIELDS:
                if not params_written:
                    result += "Parameters:<br>"
                    params_written = True
                result += f"\tOptional: {', '.join(anendpoint.OPTIONAL_FIELDS[amethod])}<br>"

            if hasattr(anendpoint, "LOGIN_REQUIRED"):
                result += f"Login required: {anendpoint.LOGIN_REQUIRED}<br>"
            else:
                result += f"Login required: False<br>"
            result += "<br></html>"
    return result

def generate_endpoint(anendpoint, format="html"):
    if format == "plain":
        return generate_endpoint_plain(anendpoint)
    if format == "html":
        return generate_endpoint_html(anendpoint)

def get_apidoc(format="html"):
    result = ""
    for anendpoint in endpoints.endpoints_to_register:
        result += generate_endpoint(anendpoint, format)
    return result
