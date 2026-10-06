"""Native non-count annotation support for DotDotGoose."""

from .labelme_io import (
    LabelMeDocument,
    annotation_to_labelme_shape,
    append_labelme_annotation,
    delete_labelme_annotation,
    labelme_path_for_image,
    load_labelme_document,
    load_labelme_raw_document,
    replace_labelme_annotations_by_label,
    update_labelme_annotation,
    write_labelme_raw_document,
)
from .geometry import (
    count_region_polygons,
    point_in_count_regions,
    point_in_polygon,
)
from .model import Annotation, AnnotationShape, Point
from .style import (
    AnnotationStyle,
    DEFAULT_ANNOTATION_STYLES,
    annotation_visibility_enabled,
    load_annotation_style,
    save_annotation_style,
    save_annotation_visibility,
)

__all__: list[str] = [
    "Annotation",
    "AnnotationShape",
    "AnnotationStyle",
    "DEFAULT_ANNOTATION_STYLES",
    "annotation_to_labelme_shape",
    "annotation_visibility_enabled",
    "append_labelme_annotation",
    "delete_labelme_annotation",
    "LabelMeDocument",
    "Point",
    "count_region_polygons",
    "labelme_path_for_image",
    "load_annotation_style",
    "load_labelme_document",
    "load_labelme_raw_document",
    "point_in_count_regions",
    "point_in_polygon",
    "replace_labelme_annotations_by_label",
    "update_labelme_annotation",
    "write_labelme_raw_document",
    "save_annotation_style",
    "save_annotation_visibility",
]
