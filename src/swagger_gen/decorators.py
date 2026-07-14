API_REGISTRY = []

def register_api(path, method="post", schemas=None):
    """Decorator to register lambda handlers for dynamic Swagger generation."""
    def decorator(func):
        API_REGISTRY.append({
            "path": path,
            "method": method.lower(),
            "func": func,
            "schemas": schemas or {}
        })
        return func
    return decorator