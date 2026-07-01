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

HARD_TEMPLATE_FALLBACK = "investigation"


@dataclass(frozen=True)
class TemplateRegistryInfo:
    """Summary entry returned by template registries."""

    name: str
    template: GenerationTemplate
    description: str | None = None
    is_default: bool = False


@runtime_checkable
class TemplateRegistry(Protocol):
    """Pluggable source for generation templates."""

    def get(self, name: str) -> GenerationTemplate: ...

    def list_info(self) -> list[TemplateRegistryInfo]: ...

    def get_default(self) -> str | None:
        """Slug used when request.template is omitted or empty."""
        ...


def _registry_get_default(registry: TemplateRegistry) -> str | None:
    get_default = getattr(registry, "get_default", None)
    if get_default is None:
        return None
    return get_default()


class BuiltinTemplateRegistry:
    """Built-in presets from ``BUILTIN_TEMPLATES``."""

    def get(self, name: str) -> GenerationTemplate:
        return get_template(name)

    def get_default(self) -> str | None:
        return "default"

    def list_info(self) -> list[TemplateRegistryInfo]:
        default_slug = self.get_default()
        items: list[TemplateRegistryInfo] = []
        for name, template in sorted(BUILTIN_TEMPLATES.items()):
            items.append(
                TemplateRegistryInfo(
                    name=name,
                    template=template,
                    description=BUILTIN_TEMPLATE_DESCRIPTIONS.get(name),
                    is_default=name == default_slug,
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

    def get_default(self) -> str | None:
        return None

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

    def get_default(self) -> str | None:
        for registry in self._registries:
            slug = _registry_get_default(registry)
            if slug:
                return slug
        return None

    def list_info(self) -> list[TemplateRegistryInfo]:
        default_slug = self.get_default()
        seen: set[str] = set()
        items: list[TemplateRegistryInfo] = []
        for registry in self._registries:
            for entry in registry.list_info():
                if entry.name in seen:
                    continue
                seen.add(entry.name)
                items.append(
                    TemplateRegistryInfo(
                        name=entry.name,
                        template=entry.template,
                        description=entry.description,
                        is_default=entry.name == default_slug,
                    )
                )
        return sorted(items, key=lambda item: item.name)


def default_template_registry() -> TemplateRegistry:
    """Default chain: JSON file path, then built-in presets."""
    return ChainedTemplateRegistry(JsonFileTemplateRegistry(), BuiltinTemplateRegistry())


def resolve_template(name: str, registry: TemplateRegistry | None = None) -> GenerationTemplate:
    """Resolve a template slug or JSON path via *registry* (default chain)."""
    return (registry or default_template_registry()).get(name)


def resolve_request_template(
    template: str | None,
    registry: TemplateRegistry | None = None,
) -> tuple[str, GenerationTemplate]:
    """Resolve template slug from explicit value or registry default chain.

    Fallback order: non-empty *template* → ``registry.get_default()`` →
    :data:`HARD_TEMPLATE_FALLBACK`.
    """
    active = registry or default_template_registry()
    slug = (template or "").strip()
    if not slug:
        slug = _registry_get_default(active) or HARD_TEMPLATE_FALLBACK
    return slug, active.get(slug)
