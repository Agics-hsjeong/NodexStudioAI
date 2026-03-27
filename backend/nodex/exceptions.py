from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    code = "API_ERROR"
    message = "request failed"

    if isinstance(response.data, dict):
        if "detail" in response.data:
            message = str(response.data.get("detail"))
        elif "error" in response.data and isinstance(response.data["error"], dict):
            return response
        else:
            # serializer field errors
            first_key = next(iter(response.data), None)
            if first_key is not None:
                val = response.data[first_key]
                if isinstance(val, list) and val:
                    message = str(val[0])
                else:
                    message = str(val)
    else:
        message = str(response.data)

    if response.status_code == 400:
        code = "BAD_REQUEST"
    elif response.status_code == 401:
        code = "UNAUTHORIZED"
    elif response.status_code == 403:
        code = "FORBIDDEN"
    elif response.status_code == 404:
        code = "NOT_FOUND"
    elif response.status_code == 429:
        code = "RATE_LIMITED"
    elif response.status_code >= 500:
        code = "SERVER_ERROR"

    response.data = {"error": {"code": code, "message": message}}
    return response

