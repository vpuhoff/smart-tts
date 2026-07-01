from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from smart_tts.templates._core import (
    BUILTIN_TEMPLATE_DESCRIPTIONS,
    BUILTIN_TEMPLATES,
    GenerationTemplate,
    get_template,
)


@dataclass(frozen=True)
class TemplateRegistryInfo:
    """Summary entry returned by template registries."""

    name: str
    template: GenerationTemplate
    description: str | None = None


@runtime_checkable
class TemplateRegistry(Protocol):
    """Pluggable source for generation templates."""

    def get(self, name: str) -> GenerationTemplate: ...

    def list_info(self) -> list[TemplateRegistryInfo]: ...


class BuiltinTemplateRegistry:
    """Built-in presets from ``BUILTIN_TEMPLATES``."""

    def get(self, name: str) -> GenerationTemplate:
        return get_template(name)

    def list_info(self) -> list[TemplateRegistryInfo]:
        items: list[TemplateRegistryInfo] = []
        for name, template in sorted(BUILTIN_TEMPLATES.items()):
            items.append(
                TemplateRegistryInfo(
                    name=name,
                    template=template,
                    description=BUILTIN_TEMPLATE_DESCRIPTIONS.get(name),
                )
            )
        return items


class JsonFileTemplateRegistry:
    """Resolve templates from local ``.json`` file paths."""

    def get(self, name: str) -> GenerationTemplate:
        path = Path(name)
        if path.suffix == ".json" and path.exists():
            return GenerationTemplate.from_json_file(path)
        raise KeyError(f"Template JSON file not found: {name!r}")

    def list_info(self) -> list[TemplateRegistryInfo]:
        return []


class ChainedTemplateRegistry:
    """Try registries in order; first match wins."""

    def __init__(self, *registries: TemplateRegistry) -> None:
        self._registries = registries

    def get(self, name: str) -> GenerationTemplate:
        errors: list[str] = []
        for registry in self._registries:
            try:
                return registry.get(name)
            except KeyError as exc:
                errors.append(str(exc))
        raise KeyError(f"Unknown template {name!r}. {'; '.join(errors)}")

    def list_info(self) -> list[TemplateRegistryInfo]:
        seen: set[str] = set()
        items: list[TemplateRegistryInfo] = []
        for registry in self._registries:
            for entry in registry.list_info():
                if entry.name in seen:
                    continue
                seen.add(entry.name)
                items.append(entry)
        return sorted(items, key=lambda item: item.name)


def default_template_registry() -> TemplateRegistry:
    """Default chain: JSON file path, then built-in presets."""
    return ChainedTemplateRegistry(JsonFileTemplateRegistry(), BuiltinTemplateRegistry())


def resolve_template(name: str, registry: TemplateRegistry | None = None) -> GenerationTemplate:
    """Resolve a template slug or JSON path via *registry* (default chain)."""
    return (registry or default_template_registry()).get(name)
