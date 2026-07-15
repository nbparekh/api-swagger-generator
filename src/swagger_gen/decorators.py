# Global registry array to catalog endpoint metadata
API_REGISTRY = []
"""
A global registry to store metadata for all registered API endpoints.


schemas: dict means: 'You must pass a dictionary here, always.'
schemas: dict | None = None means: 
'If you don't pass anything, it defaults to None, which is perfectly okay.'
"""

def register_api(path: str, 
                 method: str, 
                 schemas: dict | None = None, 
                 errors: dict | None = None):
    """
    A readable, explicit decorator that logs metadata for Swagger generation.
    It returns the original function completely untouched with no execution wrapping.
    """
    if schemas is None:
        schemas = {}
    if errors is None:
        errors = {}

    def decorator(func):
        # Simply append metadata to the global array
        API_REGISTRY.append({
            "path": path,
            "method": method.lower(),
            "func": func,
            "schemas": schemas,
            "errors": errors
        })
        return func  # No wrapper function, returns original function as-is
        
    return decorator