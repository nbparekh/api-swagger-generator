import json

def handle_exception(exception: Exception, event: dict, error_map: dict) -> dict:
    """
    Converts Python exceptions into a uniform API Gateway response structure.
    Matches the exact schema layout expected by the client application.
    """
    headers = event.get("headers", {}) or {}
    correlation_id = headers.get("X-Correlation-ID") or headers.get("x-correlation-id", "N/A")
    exception_class = exception.__class__

    # If the exception is known and mapped, return its designated status code
    if exception_class in error_map:
        status_code = error_map[exception_class]
        error_name = getattr(exception, "error_type", exception_class.__name__)
        error_msg = getattr(exception, "message", str(exception))

        return {
            "statusCode": status_code,
            "headers": {
                "Content-Type": "application/json",
                "X-Correlation-ID": correlation_id
            },
            "body": json.dumps({
                "status": "failed",
                "transaction_id": correlation_id,
                "data": None,
                "error_details": {
                    "error": error_name,
                    "message": error_msg,
                    "requestId": correlation_id
                }
            })
        }

    # Fallback for unexpected internal system crashes
    print(f"💥 Unhandled system exception: {str(exception)}")
    return {
        "statusCode": 500,
        "headers": {
            "Content-Type": "application/json",
            "X-Correlation-ID": correlation_id
        },
        "body": json.dumps({
            "status": "failed",
            "transaction_id": correlation_id,
            "data": None,
            "error_details": {
                "error": "InternalServerError",
                "message": "An unexpected error occurred on the server.",
                "requestId": correlation_id
            }
        })
    }