from PySide6 import QtWidgets
from PySide6.QtWidgets import QStyleFactory
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QPainter, QColor, QPolygon


class VolumeWidget(QtWidgets.QProgressBar):
    masterVolumeChanged = Signal(int)

    def __init__(self, parent):
        QtWidgets.QProgressBar.__init__(self, parent)

        # use fusion style on Windows 11 because the
        # default progress bar styling is awful.
        if self.style().name() == 'windows11':
            self.setStyle(QStyleFactory.create("Fusion"))
        
        self.master_volume = 0  # Red line for master volume setting
        self._dragging_master_volume = False
        self._marker_grab_distance_px = 10

    def set_value_and_tooltip(self, value: int, tooltip: str):
        self.setValue(value)
        self.setToolTip(tooltip)

    def set_master_volume_indicator(self, master_volume: int):
        """Set the red line position for master volume setting"""
        self.master_volume = max(0, min(100, int(master_volume)))
        self.update()  # Trigger repaint

    def _master_position_px(self) -> int:
        width = max(1, self.width() - 1)
        ratio = max(0.0, min(1.0, self.master_volume / 100.0))
        return int(ratio * width)

    def _master_volume_from_x(self, x: int) -> int:
        width = max(1, self.width() - 1)
        clamped_x = max(0, min(width, x))
        return int(round((clamped_x / width) * 100))

    def _is_near_master_marker(self, x: int) -> bool:
        return abs(x - self._master_position_px()) <= self._marker_grab_distance_px

    def _set_master_volume_from_mouse_x(self, x: int):
        new_master_volume = self._master_volume_from_x(x)
        self.set_master_volume_indicator(new_master_volume)
        self.masterVolumeChanged.emit(new_master_volume)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_near_master_marker(event.position().x()):
            self._dragging_master_volume = True
            self._set_master_volume_from_mouse_x(int(event.position().x()))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging_master_volume:
            self._set_master_volume_from_mouse_x(int(event.position().x()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._dragging_master_volume:
            self._dragging_master_volume = False
            self._set_master_volume_from_mouse_x(int(event.position().x()))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        # First paint the normal progress bar
        super().paintEvent(event)
        
        # Then paint the red line with notch for master volume
        if self.master_volume >= 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Calculate position for the red line
            width = max(1, self.width() - 1)
            height = self.height()
            master_pos = self._master_position_px()
            
            # Draw red vertical line
            painter.setPen(QColor(255, 0, 0, 200))  # Red line with transparency
            painter.drawLine(master_pos, 0, master_pos, height)
            
            # Draw notch at the top
            notch_size = 6
            painter.setBrush(QColor(255, 0, 0, 220))
            painter.setPen(QColor(180, 0, 0, 255))  # Darker red outline
            
            # Create triangular notch pointing down
            notch_points = [
                QPoint(master_pos - notch_size, 0),
                QPoint(master_pos + notch_size, 0),
                QPoint(master_pos, notch_size)
            ]
            notch = QPolygon(notch_points)
            painter.drawPolygon(notch)
            
            painter.end()
