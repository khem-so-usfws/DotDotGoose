"""Native non-count annotation support for DotDotGoose."""

from .labelme_io import (
    LabelMeDocument,
    annotation_to_labelme_shape,
    append_labelme_annotation,
    labelme_path_for_image,
    load_labelme_document,
)
from .model import Annotation, AnnotationShape, Point

__all__: list[str] = [
    "Annotation",
    "AnnotationShape",
    "annotation_to_labelme_shape",
    "append_labelme_annotation",
    "LabelMeDocument",
    "Point",
    "labelme_path_for_image",
    "load_labelme_document",
]
