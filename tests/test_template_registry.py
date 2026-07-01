from __future__ import annotations

import json
from pathlib import Path

import pytest

from smart_tts.templates import (
    BuiltinTemplateRegistry,
    ChainedTemplateRegistry,
    GenerationTemplate,
    INVESTIGATION,
    JsonFileTemplateRegistry,
    TemplateRegistryInfo,
    default_template_registry,
    get_template,
    resolve_template,
)


def test_builtin_registry_get() -> None:
    registry = BuiltinTemplateRegistry()
    assert registry.get("investigation") is INVESTIGATION


def test_builtin_registry_list_info() -> None:
    registry = BuiltinTemplateRegistry()
    items = registry.list_info()
    names = {item.name for item in items}
    assert names == {"default", "investigation"}

    investigation = next(item for item in items if item.name == "investigation")
    assert investigation.description
    assert investigation.template.mix_default is True


def test_json_file_registry(tmp_path: Path) -> None:
    path = tmp_path / "custom.json"
    template = GenerationTemplate(name="custom", language="ru", mix_default=False)
    path.write_text(json.dumps(template.to_dict()), encoding="utf-8")

    registry = JsonFileTemplateRegistry()
    loaded = registry.get(str(path))
    assert loaded.name == "custom"
    assert loaded.language == "ru"

    with pytest.raises(KeyError, match="not found"):
        registry.get("missing.json")


def test_chained_registry_custom_then_builtin() -> None:
    class CustomRegistry:
        def get(self, name: str) -> GenerationTemplate:
            if name == "podcast":
                return GenerationTemplate(name="podcast", language="ru")
            raise KeyError(name)

        def list_info(self) -> list[TemplateRegistryInfo]:
            return [
                TemplateRegistryInfo(
                    name="podcast",
                    template=GenerationTemplate(name="podcast"),
                    description="From DB",
                )
            ]

    registry = ChainedTemplateRegistry(CustomRegistry(), BuiltinTemplateRegistry())
    assert registry.get("podcast").name == "podcast"
    assert registry.get("investigation") is INVESTIGATION

    names = {item.name for item in registry.list_info()}
    assert "podcast" in names
    assert "investigation" in names


def test_resolve_template_default_chain(tmp_path: Path) -> None:
    assert resolve_template("investigation") is INVESTIGATION

    path = tmp_path / "file.json"
    template = GenerationTemplate(name="from_file")
    path.write_text(json.dumps(template.to_dict()), encoding="utf-8")
    assert resolve_template(str(path)).name == "from_file"


def test_default_template_registry_matches_get_template() -> None:
    registry = default_template_registry()
    assert registry.get("investigation") is get_template("investigation")
