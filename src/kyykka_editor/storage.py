"""Versioned project files, written atomically to protect the previous save."""

import json
import os
import re
import tempfile
from dataclasses import asdict, fields
from pathlib import Path

from .model import CardStyle, EditorProject, Impact


def project_data(project: EditorProject) -> dict:
    return {"version": 2, "project": asdict(project)}


def write_project(path: Path, project: EditorProject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(project_data(project), stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_project(path: Path) -> EditorProject:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document["version"] not in (1, 2):
            raise ValueError("Unsupported project version")
        data = document["project"]
        defaults = asdict(EditorProject())
        if document["version"] == 1 and isinstance(data, dict):
            for key in ("title_style", "round_style", "final_style"):
                data.setdefault(key, asdict(CardStyle()))
        if not isinstance(data, dict) or set(data) != set(defaults):
            raise ValueError("Invalid project fields")
        for key, default in defaults.items():
            value = data[key]
            if key in ("title_style", "round_style", "final_style"):
                if (
                    not isinstance(value, dict)
                    or set(value) != set(asdict(CardStyle()))
                    or not all(isinstance(item, str) for item in value.values())
                ):
                    raise ValueError("Invalid card style")
                for color in ("background_color", "text_color"):
                    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value[color]):
                        raise ValueError("Invalid card color")
                data[key] = CardStyle(**value)
            elif key == "impacts":
                if not isinstance(value, list):
                    raise ValueError("Invalid impacts")
                for impact in value:
                    if not isinstance(impact, dict) or set(impact) != {
                        f.name for f in fields(Impact)
                    }:
                        raise ValueError("Invalid impact fields")
                    if type(impact["timestamp_ms"]) is not int or not isinstance(
                        impact["thrower"], str
                    ):
                        raise ValueError("Invalid impact")
                    for timing in ("pre_roll_ms", "post_roll_ms"):
                        if impact[timing] is not None and (
                            type(impact[timing]) is not int or not 0 <= impact[timing] <= 30000
                        ):
                            raise ValueError("Invalid timing override")
            elif default is None:
                if value is not None and (type(value) is not int or value < 0):
                    raise ValueError("Invalid end marker")
            elif type(value) is not type(default):
                raise ValueError("Invalid project value")
            elif isinstance(default, list) and not all(isinstance(item, str) for item in value):
                raise ValueError("Invalid players")
        for timing in ("pre_roll_ms", "post_roll_ms"):
            if not 0 <= data[timing] <= 30000 or data[timing] % 1000:
                raise ValueError("Invalid default timing")
        data["impacts"] = sorted(Impact(**item) for item in data["impacts"])
        project = EditorProject(**data)
        for key in ("title_style", "round_style", "final_style"):
            style = getattr(project, key)
            if style.background_image and not Path(style.background_image).is_absolute():
                style.background_image = str((path.parent / style.background_image).resolve())
        if project.video_path and not Path(project.video_path).is_absolute():
            project.video_path = str((path.parent / project.video_path).resolve())
        return project
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Invalid project file") from error
