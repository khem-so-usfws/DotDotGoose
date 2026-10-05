"""Native non-count annotation support for DotDotGoose."""

from .labelme_io import (
    LabelMeDocument,
    annotation_to_labelme_shape,
    append_labelme_annotation,
    delete_labelme_annotation,
    labelme_path_for_image,
    load_labelme_document,
    update_labelme_annotation,
)
from .model import Annotation, AnnotationShape, Point
from .style import (
    AnnotationStyle,
    DEFAULT_ANNOTATION_STYLES,
    load_annotation_style,
    save_annotation_style,
)

__all__: list[str] = [
    "Annotation",
    "AnnotationShape",
    "AnnotationStyle",
    "DEFAULT_ANNOTATION_STYLES",
    "annotation_to_labelme_shape",
    "append_labelme_annotation",
    "delete_labelme_annotation",
    "LabelMeDocument",
    "Point",
    "labelme_path_for_image",
    "load_annotation_style",
    "load_labelme_document",
    "update_labelme_annotation",
    "save_annotation_style",
]
