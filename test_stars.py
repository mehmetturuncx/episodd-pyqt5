import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5.QtCore import Qt, pyqtSignal, QRect

class StarRatingWidget(QWidget):
    ratingChanged = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._rating = 0.0
        self._hover_rating = 0.0
        self.setFixedSize(200, 40)
        self.setCursor(Qt.PointingHandCursor)

    def value(self):
        return self._rating

    def setValue(self, val):
        self._rating = val
        self.update()

    def mouseMoveEvent(self, e):
        x = e.x()
        star_width = self.width() / 5
        val = (x / star_width)
        rounded = round(val * 2) / 2
        if rounded < 0.5: rounded = 0.5
        if rounded > 5.0: rounded = 5.0
        self._hover_rating = rounded
        self.update()

    def leaveEvent(self, e):
        self._hover_rating = 0.0
        self.update()

    def mousePressEvent(self, e):
        self._rating = self._hover_rating
        self.ratingChanged.emit(self._rating)
        self.update()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        val = self._hover_rating if self._hover_rating > 0 else self._rating
        
        font = QFont("Segoe UI", 28)
        painter.setFont(font)
        
        star_width = self.width() / 5
        for i in range(5):
            rect = QRect(int(i * star_width), 0, int(star_width), self.height())
            
            if val >= i + 1:
                painter.setPen(QColor("#f5c518"))
                painter.drawText(rect, Qt.AlignCenter, "★")
            elif val >= i + 0.5:
                painter.setPen(QColor("#555555"))
                painter.drawText(rect, Qt.AlignCenter, "★")
                
                painter.save()
                clip_rect = QRect(rect.left(), rect.top(), int(rect.width() / 2), rect.height())
                painter.setClipRect(clip_rect)
                painter.setPen(QColor("#f5c518"))
                painter.drawText(rect, Qt.AlignCenter, "★")
                painter.restore()
            else:
                painter.setPen(QColor("#555555"))
                painter.drawText(rect, Qt.AlignCenter, "★")

app = QApplication(sys.argv)
w = QWidget()
l = QVBoxLayout(w)
s = StarRatingWidget()
s.setValue(2.5)
l.addWidget(s)
w.show()
# sys.exit(app.exec_())
