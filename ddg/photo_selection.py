"""Read the image subsets produced by the Auto-DDG Cutline companion."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PhotoSelection:
    """A filename-ordered subset and its source for display in DotDotGoose.

    Args:
        names: Selected original image basenames.
        source: JSON file opened by the analyst.
        description: Label distinguishing recommendations from checked inputs.
    """

    names: tuple[str, ...]
    source: Path
    description: str


def read_photo_selection(path: Path) -> PhotoSelection:
    """Read a companion selection plan or refinement input snapshot.

    Args:
        path: Path to the companion JSON file.

    Returns:
        A normalized selection in filename order.

    Raises:
        OSError: If the file cannot be opened.
        ValueError: If the JSON or its photo selection is invalid.
    """
    with path.open(encoding="utf-8-sig") as stream:
        document: Any = json.load(stream)
    if not isinstance(document, dict):
        raise ValueError("Choose a selection-plan.json or tier2-selection.json file.")
    version: Any = document.get("schema_version", 1)
    if type(version) is not int or version != 1:
        raise ValueError("This photo selection uses an unsupported schema version.")
    photos: Any = document.get("photos")
    if not isinstance(photos, list):
        raise ValueError("The selection JSON has no photo list.")

    selected: list[Any]
    description: str
    if "counting_set" in document:
        indices: Any = document["counting_set"]
        if not isinstance(indices, list) or any(
            type(index) is not int or not 0 <= index < len(photos) for index in indices
        ):
            raise ValueError("The counting set contains an invalid photo index.")
        selected = [photos[index] for index in indices]
        description = (
            "Refined counting set"
            if document.get("refinement") is True
            else "Tier 1 recommendation"
        )
    elif "photo_indices" in document:
        indices = document["photo_indices"]
        if (
            not isinstance(indices, list)
            or len(indices) != len(photos)
            or any(type(index) is not int or index < 0 for index in indices)
            or len(set(indices)) != len(indices)
        ):
            raise ValueError("The refinement selection has invalid photo indices.")
        # The Tier 2 indices refer to the original Tier 1 plan. This snapshot
        # already contains exactly the checked photo records in its own list.
        selected = photos
        description = "Tier 2 checked photos"
    else:
        raise ValueError("Choose a selection-plan.json or tier2-selection.json file.")

    names: list[str] = []
    for record in selected:
        name: Any = record.get("name") if isinstance(record, dict) else None
        if (
            not isinstance(name, str)
            or not name.strip()
            or name in {".", ".."}
            or any(character in name for character in "/\\:\x00")
        ):
            raise ValueError("Selected photos must use original image filenames.")
        names.append(name)
    if not names:
        raise ValueError("The JSON file does not select any photos.")
    if len(set(names)) != len(names):
        raise ValueError("The JSON file selects the same photo more than once.")
    return PhotoSelection(tuple(sorted(names)), path, description)
