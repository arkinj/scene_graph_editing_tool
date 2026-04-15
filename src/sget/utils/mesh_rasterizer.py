"""
Rasterize a 2D-projected mesh into a QImage for display as a background layer.

The mesh is projected to scene coordinates (x * scale, -y * scale) by the
model during load.  This module takes the projected vertices, vertex colors,
and face indices and produces a QImage that can be displayed as a
QGraphicsPixmapItem in the graph view.

Uses QPainter to draw filled triangles — simpler than a custom scanline
rasterizer and sufficient for one-time rendering on load.
"""

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage, QPainter, QPolygonF

MAX_DIM = 16384


def rasterize_mesh(vertices_2d, colors, faces, pixels_per_unit=1.0):
    """Render mesh triangles to a QImage.

    The image is rendered at 1 pixel per scene unit by default, so that
    ``QGraphicsPixmapItem.setPos(origin_x, origin_y)`` is all that's needed
    to align it with the scene — no scaling required.

    Parameters
    ----------
    vertices_2d : ndarray (N, 2)
        Vertex positions in scene coordinates.
    colors : ndarray (N, 3)
        Vertex RGB colors in [0, 1].
    faces : ndarray (3, M)
        Triangle vertex indices.
    pixels_per_unit : float
        Pixels per scene unit. 1.0 = one pixel per scene unit (aligned
        with QGraphicsScene coordinates). Higher = sharper but larger image.

    Returns
    -------
    (QImage, float, float, float)
        The rendered image, the (min_x, min_y) scene coordinates of
        the image's top-left corner, and the actual pixels_per_unit used
        (may be reduced if the image would exceed MAX_DIM).
    """
    # Compute the bounding box in scene coordinates.
    min_x = vertices_2d[:, 0].min()
    max_x = vertices_2d[:, 0].max()
    min_y = vertices_2d[:, 1].min()
    max_y = vertices_2d[:, 1].max()

    width_scene = max_x - min_x
    height_scene = max_y - min_y

    # Image dimensions in pixels.
    img_w = max(1, int(width_scene * pixels_per_unit))
    img_h = max(1, int(height_scene * pixels_per_unit))

    # Cap image size to prevent memory issues on huge meshes.
    if img_w > MAX_DIM or img_h > MAX_DIM:
        scale_down = MAX_DIM / max(img_w, img_h)
        img_w = int(img_w * scale_down)
        img_h = int(img_h * scale_down)
        pixels_per_unit *= scale_down

    image = QImage(img_w, img_h, QImage.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))  # Transparent background.

    painter = QPainter(image)
    painter.setPen(QColor(0, 0, 0, 0))  # No outline — just filled triangles.

    num_faces = faces.shape[1]
    for fi in range(num_faces):
        i0, i1, i2 = faces[0, fi], faces[1, fi], faces[2, fi]

        # Average vertex colors for the triangle fill.
        r = int((colors[i0, 0] + colors[i1, 0] + colors[i2, 0]) / 3 * 255)
        g = int((colors[i0, 1] + colors[i1, 1] + colors[i2, 1]) / 3 * 255)
        b = int((colors[i0, 2] + colors[i1, 2] + colors[i2, 2]) / 3 * 255)
        painter.setBrush(QColor(r, g, b))

        # Convert scene coords to pixel coords.
        x0 = (vertices_2d[i0, 0] - min_x) * pixels_per_unit
        y0 = (vertices_2d[i0, 1] - min_y) * pixels_per_unit
        x1 = (vertices_2d[i1, 0] - min_x) * pixels_per_unit
        y1 = (vertices_2d[i1, 1] - min_y) * pixels_per_unit
        x2 = (vertices_2d[i2, 0] - min_x) * pixels_per_unit
        y2 = (vertices_2d[i2, 1] - min_y) * pixels_per_unit

        tri = QPolygonF([QPointF(x0, y0), QPointF(x1, y1), QPointF(x2, y2)])
        painter.drawPolygon(tri)

    painter.end()
    return image, min_x, min_y, pixels_per_unit
