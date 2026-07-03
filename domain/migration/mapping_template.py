import json
import os
from datetime import datetime
from typing import Any


class MappingTemplate:
    @staticmethod
    def save(template: dict, filepath: str) -> None:
        """Save template dict to JSON file."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(template, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load(filepath: str) -> dict:
        """Load template dict from JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def create(source_type: str, target_type: str, name: str = "") -> dict:
        """Create a new empty template."""
        return {
            "template_name": name or f"Mapping {source_type} → {target_type}",
            "created_at": datetime.now().isoformat(),
            "source": {"type": source_type, "version": ""},
            "target": {"type": target_type, "version": ""},
            "overrides": {},
        }

    @staticmethod
    def add_override(template: dict, table_name: str, column_name: str,
                     target_type: str, default_value: str | None = None) -> dict:
        """Add a column-level override to the template."""
        if table_name not in template["overrides"]:
            template["overrides"][table_name] = {}
        entry = {"target_type": target_type}
        if default_value:
            entry["default"] = default_value
        template["overrides"][table_name][column_name] = entry
        return template

    @staticmethod
    def add_global_override(template: dict, source_type: str, target_type: str) -> dict:
        """Add a global type override (applies to all columns of this source type)."""
        if "global" not in template["overrides"]:
            template["overrides"]["global"] = {}
        template["overrides"]["global"][source_type] = {"target_type": target_type}
        return template

    @staticmethod
    def get_override(template: dict, table_name: str, column_name: str) -> dict | None:
        """Get column-level override if exists."""
        table_overrides = template.get("overrides", {}).get(table_name, {})
        return table_overrides.get(column_name)

    @staticmethod
    def get_global_override(template: dict, source_type: str) -> str | None:
        """Get global override target type for a source type."""
        global_overrides = template.get("overrides", {}).get("global", {})
        entry = global_overrides.get(source_type)
        if entry:
            return entry.get("target_type")
        return None

    @staticmethod
    def apply_to_mapping(template: dict, table_name: str, column_name: str,
                         source_type: str, default_ddl: str) -> str:
        """Apply template overrides to produce final DDL type.
        Priority: column override > global override > default DDL."""
        col_override = MappingTemplate.get_override(template, table_name, column_name)
        if col_override:
            return col_override.get("target_type", default_ddl)
        global_override = MappingTemplate.get_global_override(template, source_type)
        if global_override:
            return global_override
        return default_ddl
