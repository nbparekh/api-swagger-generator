import os
import sys
import json
import importlib
import yaml
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec.yaml_utils import load_operations_from_docstring

from swagger_gen.decorators import API_REGISTRY


class SpecBuilder:
    """Compiles the final OpenAPI specification from registry metadata and sidecars."""

    def __init__(self, config: dict):
        self.config = config
        self.spec = APISpec(
            title=config["info"]["title"],
            version=config["info"]["version"],
            openapi_version=config["info"]["openapi_version"],
            description=config["info"].get("description", ""),
            plugins=[MarshmallowPlugin()],
        )
        self._registered_schemas = set()

    def register_security_schemes(self) -> "SpecBuilder":
        for name, data in self.config.get("security_schemes", {}).items():
            self.spec.components.security_scheme(name, data)
        return self

    def register_endpoints(self, registry: list) -> "SpecBuilder":
        for entry in registry:
            path = entry["path"]
            method = entry["method"]
            schemas = entry["schemas"]
            errors = entry.get("errors", {})

            print(f"📑 Processing endpoint: {method.upper()} {path}")
            self._register_schemas(schemas)
            
            operations = self._resolve_operations(entry)
            operations = self._inject_dynamic_error_responses(operations, method, errors)
            
            self.spec.path(path=path, operations=operations)
        return self

    def write(self, workspace_root: str) -> None:
        settings = self.config["settings"]
        output_filename = os.path.join(workspace_root, settings["output_file"])
        output_format = settings.get("format", "json").strip().lower()

        with open(output_filename, "w") as f:
            if output_format in ["yaml", "yml"]:
                yaml.dump(self.spec.to_dict(), f, default_flow_style=False, sort_keys=False)
                print(f"\n✨ Spec compiled successfully at: {output_filename}")
            else:
                json.dump(self.spec.to_dict(), f, indent=2)
                print(f"\n✨ Spec compiled successfully at: {output_filename}")

    def _register_schemas(self, schemas: dict) -> None:
        for name, schema_cls in schemas.items():
            if name not in self._registered_schemas:
                self.spec.components.schema(name, schema=schema_cls)
                self._registered_schemas.add(name)

    def _resolve_operations(self, entry: dict) -> dict:
        func = entry["func"]
        method = entry["method"]
        operations = load_operations_from_docstring(func.__doc__)
        
        if not operations:
            operations = self._load_from_sidecar(func, method)
        return operations if operations else {}

    def _inject_dynamic_error_responses(self, operations: dict, method: str, errors: dict) -> dict:
        method_lower = method.lower()
        if method_lower not in operations or not errors:
            return operations

        if "responses" not in operations[method_lower]:
            operations[method_lower]["responses"] = {}

        responses = operations[method_lower]["responses"]

        for exception_cls, status_code in errors.items():
            status_str = str(status_code)
            if status_str not in responses:
                responses[status_str] = {
                    "description": f"Returned when a {exception_cls.__name__} exception occurs.",
                    "schema": {
                        "$ref": "#/components/schemas/ErrorResponse"
                    } if "ErrorResponse" in self._registered_schemas else {"type": "object"}
                }
                
        if "500" not in responses:
            responses["500"] = {
                "description": "Internal server error fallback.",
                "schema": {
                    "$ref": "#/components/schemas/ErrorResponse"
                } if "ErrorResponse" in self._registered_schemas else {"type": "object"}
            }

        return operations

    def _load_from_sidecar(self, func, method: str) -> dict | None:
        module = importlib.import_module(func.__module__)
        module_file = getattr(module, "__file__", None)
        if not module_file:
            return None

        base_path = os.path.splitext(module_file)[0]
        for ext in [".yaml", ".yml", ".json"]:
            sidecar_path = base_path + ext
            if os.path.exists(sidecar_path):
                try:
                    with open(sidecar_path, "r") as f:
                        content = yaml.safe_load(f) if ext != ".json" else json.load(f)
                        if isinstance(content, dict):
                            method_lower = method.lower()
                            if method_lower in content:
                                return {method_lower: content[method_lower]}
                            return content
                except Exception as e:
                    print(f"⚠️ Error reading sidecar {sidecar_path}: {e}")
        return None


def load_config(workspace_root: str) -> dict:
    config_path = os.path.join(workspace_root, "swagger_config.json")
    defaults = {
        "info": {"title": "API", "version": "1.0.0", "openapi_version": "3.0.2"},
        "settings": {"handlers_directory": "src/handlers", "output_file": "openapi.json", "format": "json"},
        "security_schemes": {}
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                user_config = json.load(f)
                defaults["info"].update(user_config.get("info", {}))
                defaults["settings"].update(user_config.get("settings", {}))
                defaults["security_schemes"] = user_config.get("security_schemes", {})
        except Exception as e:
            print(f"⚠️ Failed to parse config file: {e}")
    return defaults


def discover_and_import_handlers(workspace_root: str, handlers_relative_path: str) -> None:
    handlers_path = os.path.abspath(os.path.join(workspace_root, handlers_relative_path))
    if not os.path.exists(handlers_path):
        return
    for root, _, files in os.walk(handlers_path):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                rel_to_root = os.path.relpath(os.path.join(root, file), workspace_root)
                module_name = rel_to_root.replace(os.sep, ".").rstrip(".py")
                try:
                    importlib.import_module(module_name)
                except Exception as e:
                    print(f"⚠️ Error importing module {module_name}: {e}")


def main() -> None:
    workspace_root = os.getcwd()
    if workspace_root not in sys.path:
        sys.path.insert(0, workspace_root)

    config = load_config(workspace_root)
    discover_and_import_handlers(workspace_root, config["settings"]["handlers_directory"])

    (SpecBuilder(config)
     .register_security_schemes()
     .register_endpoints(API_REGISTRY)
     .write(workspace_root))


if __name__ == "__main__":
    main()