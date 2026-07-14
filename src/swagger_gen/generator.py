import os
import sys
import json
import importlib
import yaml
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec.yaml_utils import load_operations_from_docstring

from swagger_gen.decorators import API_REGISTRY

def load_config(workspace_root):
    """Loads Swagger configurations from swagger_config.json in the calling project."""
    config_path = os.path.join(workspace_root, "swagger_config.json")
    defaults = {
        "info": {
            "title": "Serverless API",
            "version": "1.0.0",
            "openapi_version": "3.0.2",
            "description": "Generated AWS Lambda API documentation."
        },
        "settings": {
            "handlers_directory": "src/handlers",
            "output_file": "openapi.json",
            "format": "json"
        }
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                user_config = json.load(f)
                defaults["info"].update(user_config.get("info", {}))
                defaults["settings"].update(user_config.get("settings", {}))
                print(f"⚙️ Loaded configuration from {config_path}")
        except Exception as e:
            print(f"⚠️ Warning: Failed to parse config file ({e}). Using defaults.")
    else:
        print("ℹ️ No swagger_config.json found. Using defaults.")
        
    return defaults

def discover_and_import_handlers(workspace_root, handlers_relative_path):
    """Dynamically imports hander files to trigger decorators."""
    handlers_path = os.path.abspath(os.path.join(workspace_root, handlers_relative_path))
    if not os.path.exists(handlers_path):
        print(f"❌ Error: Handlers directory '{handlers_path}' not found.")
        return

    for root, _, files in os.walk(handlers_path):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                rel_to_root = os.path.relpath(os.path.join(root, file), workspace_root)
                module_name = rel_to_root.replace(os.sep, ".").rstrip(".py")
                try:
                    importlib.import_module(module_name)
                    print(f"✅ Successfully imported: {module_name}")
                except Exception as e:
                    print(f"⚠️ Failed to dynamically import {module_name}: {e}")

def main():
    workspace_root = os.getcwd()
    
    if workspace_root not in sys.path:
        sys.path.insert(0, workspace_root)

    config = load_config(workspace_root)
    
    print(f"🔍 Analyzing Workspace Root: {workspace_root}")
    discover_and_import_handlers(workspace_root, config["settings"]["handlers_directory"])

    spec = APISpec(
        title=config["info"]["title"],
        version=config["info"]["version"],
        openapi_version=config["info"]["openapi_version"],
        description=config["info"].get("description", ""),
        plugins=[MarshmallowPlugin()],
    )

    registered_schemas = set()

    for entry in API_REGISTRY:
        path = entry["path"]
        func = entry["func"]
        schemas = entry["schemas"]

        print(f"📑 Processing endpoint: {entry['method'].upper()} {path}")

        for schema_name, schema_cls in schemas.items():
            if schema_name not in registered_schemas:
                spec.components.schema(schema_name, schema=schema_cls)
                registered_schemas.add(schema_name)

        operations = load_operations_from_docstring(func.__doc__)
        spec.path(path=path, operations=operations)

    output_filename = os.path.join(workspace_root, config["settings"]["output_file"])
    output_format = config["settings"].get("format", "json").strip().lower()

    with open(output_filename, "w") as f:
        if output_format in ["yaml", "yml"]:
            yaml.dump(spec.to_dict(), f, default_flow_style=False, sort_keys=False)
            print(f"\n✨ Generation complete! YAML Spec written to: {output_filename}")
        else:
            json.dump(spec.to_dict(), f, indent=2)
            print(f"\n✨ Generation complete! JSON Spec written to: {output_filename}")

if __name__ == "__main__":
    main()