#!/usr/bin/env python

from lorad.api import endpoints

# GPT-heavy area

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

def generate_endpoint_fragment(anendpoint):
    html = ""
    for amethod in ["GET", "POST", "PUT", "DELETE"]:
        if hasattr(anendpoint, f"impl_{amethod}"):
            html += f'<div class="endpoint">'
            html += f'<div class="method">{amethod} <code>{anendpoint.ENDP_PATH}</code></div>'

            docstring = anendpoint.DOCSTRING.get(amethod, "No documentation provided.")
            html += f'<p>{docstring}</p>'

            has_params = False
            html += '<div class="params">'
            if hasattr(anendpoint, "REQUIRED_FIELDS") and amethod in anendpoint.REQUIRED_FIELDS:
                html += '<div class="section-title">Required Parameters:</div><ul>'
                for field in anendpoint.REQUIRED_FIELDS[amethod]:
                    html += f'<li><code>{field}</code></li>'
                html += '</ul>'
                has_params = True

            if hasattr(anendpoint, "OPTIONAL_FIELDS") and amethod in anendpoint.OPTIONAL_FIELDS:
                html += '<div class="section-title">Optional Parameters:</div><ul>'
                for field in anendpoint.OPTIONAL_FIELDS[amethod]:
                    html += f'<li><code>{field}</code></li>'
                html += '</ul>'
                has_params = True

            if not has_params:
                html += '<p><em>No parameters.</em></p>'
            html += '</div>'

            login_required = getattr(anendpoint, "LOGIN_REQUIRED", False)
            html += f'<div class="section-title">Login required:</div><p>{"Yes" if login_required else "No"}</p>'

            html += '</div>'  # .endpoint
    return html


def wrap_api_doc_html(endpoint_fragments):
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>API Documentation</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 2rem;
            background-color: #f9f9f9;
            color: #333;
        }}
        .endpoint {{
            background-color: #fff;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #007BFF;
        }}
        ul {{
            list-style: none;
            padding: 0;
        }}
        li {{
            margin: 0.25rem 0;
        }}
        .method {{
            font-weight: bold;
            font-size: 1.1rem;
        }}
        .section-title {{
            margin-top: 1rem;
            font-weight: bold;
            color: #555;
        }}
    </style>
</head>
<body>
<h1>API Endpoint Documentation</h1>
{endpoint_fragments}
</body>
</html>
"""

def generate_endpoint(anendpoint, format="html"):
    if format == "plain":
        return generate_endpoint_plain(anendpoint)
    if format == "html":
        return generate_endpoint_fragment(anendpoint)

def get_apidoc(format="html"):
    result = ""
    for anendpoint in endpoints.endpoints_to_register:
        result += generate_endpoint(anendpoint, format)
    if format=="html":
        return wrap_api_doc_html(result)
    return result
