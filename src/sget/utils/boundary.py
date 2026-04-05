"""
Boundary overlay rendering helpers for the 2D graph view.

Creates QGraphicsItems for different boundary representations:
- Polygon from flat x/y coordinate lists (Room Draw Region tool)
- Bounding box rectangle from center + dimensions (Objects, Rooms)
- Polar polygon from radii at evenly-spaced angles (TravNode)
- Rectangle from max_radius (TravNode alternative)
- Polygon from Point3D list (Place2d)

All helpers return styled QGraphicsItems with semi-transparent fill
and dashed border. They take a color and scale factor as input and
are independent of the model or view — pure rendering functions.
"""

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsPolygonItem, QGraphicsRectItem


def style_overlay(item, color):
    """Apply consistent semi-transparent styling to a boundary overlay."""
    fill = QColor(color)
    fill.setAlpha(30)
    item.setBrush(QBrush(fill))
    item.setPen(QPen(color, 1.5, Qt.DashLine))
    return item


def make_polygon_overlay(bx, by, color, scale):
    """Polygon from flat x/y lists (Room Draw Region)."""
    points = [QPointF(x * scale, -y * scale) for x, y in zip(bx, by)]
    item = QGraphicsPolygonItem(QPolygonF(points))
    return style_overlay(item, color)


def make_bbox_overlay(props, color, scale):
    """Rectangle from bbox center + dimensions."""
    cx = float(props["bbox_x"]) * scale
    cy = -float(props["bbox_y"]) * scale
    w = float(props["bbox_l"]) * scale
    h = float(props["bbox_w"]) * scale
    item = QGraphicsRectItem(cx - w / 2, cy - h / 2, w, h)
    return style_overlay(item, color)


def make_radii_polygon_overlay(props, color, scale):
    """Polar polygon from TravNode radii (N rays at equal angles)."""
    cx = float(props["center"][0]) * scale
    cy = -float(props["center"][1]) * scale
    radii = props["radii"]
    n = len(radii)
    points = []
    for i, r in enumerate(radii):
        angle = 2 * math.pi * i / n
        points.append(
            QPointF(
                cx + r * scale * math.cos(angle),
                cy - r * scale * math.sin(angle),
            )
        )
    item = QGraphicsPolygonItem(QPolygonF(points))
    return style_overlay(item, color)


def make_radii_rect_overlay(props, color, scale):
    """Rectangle from TravNode max_radius."""
    cx = float(props["center"][0]) * scale
    cy = -float(props["center"][1]) * scale
    r = float(props.get("max_radius", 1.0)) * scale
    item = QGraphicsRectItem(cx - r, cy - r, 2 * r, 2 * r)
    return style_overlay(item, color)


def make_point3d_polygon_overlay(boundary_points, color, scale):
    """Polygon from Neo4j Point3D list (Place2d boundary)."""
    points = [QPointF(float(pt[0]) * scale, -float(pt[1]) * scale) for pt in boundary_points]
    item = QGraphicsPolygonItem(QPolygonF(points))
    return style_overlay(item, color)
