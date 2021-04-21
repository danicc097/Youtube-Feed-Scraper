# Copyright (C) 2021 Daniel Castro

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import (
    QByteArray, QEasingCurve, QObject, QPoint, QPointF, QPropertyAnimation, QRect, QRectF, QSequentialAnimationGroup,
    QSize, QTimer, QVariantAnimation, Qt, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
)
from PyQt5.QtGui import (QBrush, QColor, QFont, QIcon, QImage, QPainter, QPainterPath, QPaintEvent, QPen, QPixmap)
from PyQt5.QtNetwork import (QNetworkAccessManager, QNetworkReply, QNetworkRequest)
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel, QLayout,
    QListWidgetItem, QMainWindow, QPushButton, QScrollArea, QSizePolicy, QSystemTrayIcon, QToolButton, QVBoxLayout,
    QWidget
)


class Spoiler(QWidget):
    def __init__(self, parent=None, title='', animationDuration=300, ref_parent=None, font=None):
        """
        Collapsable and expandable section.
        Based on:
        http://stackoverflow.com/questions/32476006/how-to-make-an-expandable-collapsable-section-widget-in-qt
        """
        super(Spoiler, self).__init__(parent=parent)
        self.ref_parent = ref_parent
        self.animationDuration = animationDuration
        self.toggleAnimation = QtCore.QParallelAnimationGroup()
        self.contentArea = QScrollArea()
        self.already_filtered = True
        if font is not None: self.setFont(font)
        mainLayout = QGridLayout()

        self.toggleButton = QToolButton()
        self.toggleButton.setStyleSheet("QToolButton { border: none; }")
        self.toggleButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggleButton.setArrowType(Qt.RightArrow)
        self.toggleButton.setText(str(title))
        self.toggleButton.setCheckable(True)
        self.toggleButton.setChecked(False)

        self.headerLine = QFrame()
        self.headerLine.setFrameShape(QFrame.HLine)
        self.headerLine.setFrameShadow(QFrame.Sunken)
        self.headerLine.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        self.contentArea.setStyleSheet("QScrollArea { background-color: white; border: none; }")
        self.contentArea.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # start out collapsed
        self.contentArea.setMaximumHeight(0)
        self.contentArea.setMinimumHeight(0)
        # let the entire widget grow and shrink with its content
        toggleAnimation = self.toggleAnimation
        toggleAnimation.addAnimation(QtCore.QPropertyAnimation(self, b"minimumHeight"))
        toggleAnimation.addAnimation(QtCore.QPropertyAnimation(self, b"maximumHeight"))
        toggleAnimation.addAnimation(QtCore.QPropertyAnimation(self.contentArea, b"maximumHeight"))
        # don't waste space
        mainLayout.setVerticalSpacing(0)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        row = 0
        mainLayout.addWidget(self.toggleButton, row, 0, 1, 1, Qt.AlignLeft)
        mainLayout.addWidget(self.headerLine, row, 2, 1, 1)
        row += 1
        mainLayout.addWidget(self.contentArea, row, 0, 1, 3)
        self.setLayout(mainLayout)

        def start_animation(checked):
            arrow_type = Qt.DownArrow if checked else Qt.RightArrow
            direction = QtCore.QAbstractAnimation.Forward if checked else QtCore.QAbstractAnimation.Backward
            self.toggleButton.setArrowType(arrow_type)
            self.toggleAnimation.setDirection(direction)
            self.toggleAnimation.start()
            self.apply_shadow_effect()

        self.toggleButton.clicked.connect(start_animation)

            
        
    def apply_shadow_effect(self, color=QColor(50, 50, 50), blur_radius=10, offset=2):
        effect = QGraphicsDropShadowEffect(self)
        effect.setBlurRadius(blur_radius)
        effect.setColor(color)
        effect.setOffset(offset)
        if self.already_filtered:
            self.removeEventFilter(self.ref_parent)
            self.already_filtered = False
        else:
            self.installEventFilter(self.ref_parent)
            self.already_filtered = True

        self.setGraphicsEffect(effect)

    def set_content_layout(self, contentLayout: QLayout):
        """
        Adds a layout ``contentLayout`` to the spoiler area.
        """
        # Not sure if this is equivalent to self.contentArea.destroy()
        self.contentArea.destroy()
        self.contentArea.setLayout(contentLayout)
        collapsedHeight = self.sizeHint().height() - self.contentArea.maximumHeight()
        contentHeight = contentLayout.sizeHint().height()
        for i in range(self.toggleAnimation.animationCount() - 1):
            spoilerAnimation = self.toggleAnimation.animationAt(i)
            spoilerAnimation.setDuration(self.animationDuration)
            spoilerAnimation.setStartValue(collapsedHeight)
            spoilerAnimation.setEndValue(collapsedHeight + contentHeight)
        contentAnimation = self.toggleAnimation.animationAt(self.toggleAnimation.animationCount() - 1)
        contentAnimation.setDuration(self.animationDuration)
        contentAnimation.setStartValue(0)
        contentAnimation.setEndValue(contentHeight)


class CustomFrame(QFrame):
    def __init__(self, parent=None, ref_parent=None, **kwargs):
        super(QFrame, self).__init__(parent, **kwargs)
        self.border_radius = 6
        self.setStyleSheet(
            "color: rgb(0, 0, 0);"  #text color
            "background-color: rgb(237, 237, 237);"
            "text-align: center;"
            f"border-radius: {self.border_radius}px {self.border_radius}px {self.border_radius}px {self.border_radius}px;"
            "padding: 0px;"
        )
        #! CRUCIAL setFixed or setMaximum also breaks the alignment we set
        self.setMinimumWidth(150)

    def paintEvent(self, event):
        #* draw decorative line between border radius centers
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.HighQualityAntialiasing, True)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        brush_width = 3
        # account for decorative line overlap
        self.setContentsMargins(self.border_radius, 0, 0, 0)
        height_offset = self.border_radius
        pen = QtGui.QPen(QColor(67, 142, 200), brush_width)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(
            self.border_radius,
            height_offset,
            self.border_radius,
            self.height() - height_offset,
        )


class CustomVerticalFrame(QFrame):
    def __init__(self, parent=None, ref_parent=None, **kwargs):
        super(QFrame, self).__init__(parent, **kwargs)

        self.border_radius = 15
        self.setStyleSheet(
            "color: rgb(0, 0, 0);"  #text color
            "background-color: rgb(245, 245, 245);"
            "text-align: center;"
            # "border-style: solid;"
            # "border-width: 0px 0px 0px 2px;"
            "border-color: white white white rgb(67, 142, 200);"
            f"border-radius: {self.border_radius}px {self.border_radius}px {self.border_radius}px {self.border_radius}px;"
            "padding: 0px;"
        )

    def paintEvent(self, event):
        #* draw decorative line between border radius centers
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.HighQualityAntialiasing, True)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        brush_width = 8
        # account for decorative line overlap
        self.setContentsMargins(0, self.border_radius, 0, 0)
        width_offset = 4
        height_offset = self.border_radius
        pen = QtGui.QPen(QColor(67, 142, 200), brush_width)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(
            height_offset,
            height_offset,
            self.width() - height_offset,
            height_offset,
        )


# class Message(QWidget):
#     def __init__(self, title, message, parent=None):
#         QWidget.__init__(self, parent)
#         self.vLayout = QVBoxLayout()
#         self.titleLabel = QLabel(title, self)
#         self.titleLabel.setStyleSheet("font-size: 18px; font-weight: bold; padding: 0;")
#         self.frame = CustomVerticalFrame()
#         self.vLayout.addWidget(self.titleLabel)
#         self.vLayout.addWidget(self.frame)
#         # self.setAttribute(QtCore.Qt.WA_TranslucentBackground)


class Notification(QWidget):
    def __init__(self, parent=None, ref_parent=None, **kwargs):
        super(QWidget, self).__init__(parent=None, **kwargs)
        self.ref_parent = ref_parent
        # popup will hide when clicked outside
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.frame = CustomVerticalFrame(self)
        # self.setMinimumWidth(650) #? DON'T. use frame's minimumwidth instead
        self.frame.setSizePolicy(QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Ignored))
        self.frame.setMinimumWidth(600)
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.addWidget(self.frame, alignment=Qt.AlignCenter)
        self.finalHeight = 150.0
        self.center(self) 
        # self.center(self.frame) #? do not apply to inner widget!
        self.show()

    def center(self, widget):
        qr = widget.frameGeometry()
        #? the widget is centered based on the window, not `primaryScreen`
        #? as with the window itself
        cp = QApplication.activeWindow().geometry().center()
        cp.setY(cp.y() + self.finalHeight)  # offset
        qr.moveCenter(cp)
        widget.move(qr.topLeft())

    def animate_opening(self):
        self._animation = QtCore.QVariantAnimation(
            self,
            startValue=0.0,
            endValue=self.finalHeight,
            duration=500,
            valueChanged=self.on_valueChanged,
        )
        self._animation.setEasingCurve(QEasingCurve.InCubic)
        self.start_animation()

    def start_animation(self):
        if self._animation.state() != QtCore.QAbstractAnimation.Running:
            self._animation.start()

    @QtCore.pyqtSlot(QtCore.QVariant)
    def on_valueChanged(self, value):
        self.frame.setFixedSize(self.frame.width(), value)


class CustomQWidget(QWidget):
    """QWidget to be added as an item's widget."""
    def __init__(self, parent=None, ref_parent=None, base_color=QtGui.QColor(235, 235, 235), **kwargs):
        super().__init__(parent, **kwargs)
        self.ref_parent = ref_parent
        self.shadow_effects = {}
        self.shadow_effects_counter = 0

        self.textUpQLabel = QLabel()
        font = QFont()
        font.setFamily("Fira Sans")
        font.setPointSize(12)
        self.textUpQLabel.setFont(font)

        base_size = 40
        border_width = 0
        self.authorQLabel = RoundLabelImage(
            size=base_size, border_width=border_width, border_color=QtGui.QColor(20, 60, 186)
        )

        self.frame = CustomFrame()

        self.textQVBoxLayout = QVBoxLayout()
        self.textQVBoxLayout.addWidget(self.textUpQLabel)
        self.textQVBoxLayout.addWidget(self.authorQLabel)

        self.allQGrid = QGridLayout()
        # icon will be set later, if a reply is received
        self.thumbnailQLabel = QLabel()
        self.thumbnailQLabel.setFixedWidth(140)
        self.allQGrid.addWidget(self.thumbnailQLabel, 0, 0, 2, 1)
        self.allQGrid.addLayout(self.textQVBoxLayout, 0, 1, 2, 1, Qt.AlignLeft)
        self.allQGrid.addWidget(self.frame, 1, 2, 1, 1, Qt.AlignRight)
        self.setLayout(self.allQGrid)
        self.textUpQLabel.setStyleSheet("""
            color: rgb(70,130,180);
        """)

        self.apply_shadow_effect(self.authorQLabel)
        self.apply_shadow_effect(self.frame)
        self.apply_shadow_effect(self.thumbnailQLabel)

        self._color = base_color

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, color):
        if self.color == color:
            return
        self._color = color
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.HighQualityAntialiasing, True)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        rect = QtCore.QRectF(self.rect())
        painter_path = QtGui.QPainterPath()
        border_radius = 20
        painter_path.addRoundedRect(rect, border_radius, border_radius)
        painter.setOpacity(0.4)  # before filling
        painter.fillPath(painter_path, QtGui.QBrush(self.color))
        painter.setPen(Qt.NoPen)
        painter.drawPath(painter_path)
        painter.setClipPath(painter_path)

    def apply_shadow_effect(self, widget: QWidget):
        """Same widget graphic effect instance can't be used more than once
        else it's removed from the first widget. Workaround using a dict:"""
        self.shadow_effects[self.shadow_effects_counter] = QGraphicsDropShadowEffect(self)
        self.shadow_effects[self.shadow_effects_counter].setBlurRadius(10)
        self.shadow_effects[self.shadow_effects_counter].setColor(QtGui.QColor(50, 50, 50))
        self.shadow_effects[self.shadow_effects_counter].setOffset(2)
        widget.setGraphicsEffect(self.shadow_effects[self.shadow_effects_counter])
        self.shadow_effects_counter += 1

    def setTextUp(self, text):
        self.textUpQLabel.setText(text)
        self.textUpQLabel.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, QSizePolicy.MinimumExpanding))

    def set_thumbnail(self, img: QPixmap):
        # img = QPixmap(img)
        # important to use a SmoothTransformation
        thumbnail_width = self.thumbnailQLabel.width()
        img = img.scaledToWidth(thumbnail_width, Qt.SmoothTransformation)
        self.thumbnailQLabel.setPixmap(img)
        self.thumbnailQLabel.setAlignment(Qt.AlignTop)
        self.thumbnailQLabel.setContentsMargins(0, 0, 20, 0)
        #! CRUCIAL TO ADD Ignored VERTICAL FLAG -> breaks qframe alignment
        self.thumbnailQLabel.setSizePolicy(QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Ignored))
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setColor(QtGui.QColor(50, 50, 50))
        shadow.setOffset(2)
        self.thumbnailQLabel.setGraphicsEffect(shadow)


class RoundLabelImage(QLabel):
    """Based on:
    https://stackoverflow.com/questions/50819033/qlabel-with-image-in-round-shape/50821539"""
    def __init__(
        self,
        path="",
        size=50,
        border_width=0,
        border_color=None,
        antialiasing=True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._size = size
        self._border_width = border_width
        self._border_color = border_color
        self._antialiasing = antialiasing
        self.setFixedSize(size, size)
        self._path = path
        if path != "":
            self.set_round_label(from_local_path=True)

    def set_round_label(self, data: QByteArray = None, from_local_path=False):
        if from_local_path:
            self.source = QPixmap(self._path)
        else:
            self.source = QPixmap()
            self.source.loadFromData(data)
        pixmap_size = self._size - self._border_width * 2
        p = self.source.scaled(pixmap_size, pixmap_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self.target = QPixmap(self.size())
        self.target.fill(Qt.transparent)

        painter = QPainter(self.target)
        if self._antialiasing:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        rect = QtCore.QRectF(self.rect())
        if self._border_width:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QtGui.QColor(self._border_color))
            painter.drawEllipse(rect)
            rect.adjust(self._border_width, self._border_width, -self._border_width, -self._border_width)

        painter_path = QPainterPath()
        painter_path.addEllipse(rect)
        painter.setClipPath(painter_path)

        painter.drawPixmap(self._border_width, self._border_width, p)
        painter.end()  # must be called if there are multiple painters
        painter = None
        self.setPixmap(self.target)


class AnimatedToggle(QCheckBox):
    """Based on https://www.learnpyqt.com/tutorials/qpropertyanimation/"""
    _transparent_pen = QPen(Qt.transparent)
    _light_grey_pen = QPen(Qt.lightGray)

    def __init__(
        self,
        parent=None,
        bar_color=Qt.gray,
        checked_color="#00B0FF",
        handle_color=Qt.white,
        pulse_unchecked_color="#44999999",
        pulse_checked_color="#4400B0EE"
    ):
        super().__init__(parent)

        self._bar_brush = QBrush(bar_color)
        self._bar_checked_brush = QBrush(QColor(checked_color).lighter())

        self._handle_brush = QBrush(handle_color)
        self._handle_checked_brush = QBrush(QColor(checked_color))

        self._pulse_unchecked_animation = QBrush(QColor(pulse_unchecked_color))
        self._pulse_checked_animation = QBrush(QColor(pulse_checked_color))

        # Setup the rest of the widget.
        self.setContentsMargins(8, 0, 8, 0)
        self._handle_position = 0

        self._pulse_radius = 0

        self.animation = QPropertyAnimation(self, b"handle_position", self)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.setDuration(200)  # time in ms

        self.pulse_anim = QPropertyAnimation(self, b"pulse_radius", self)
        self.pulse_anim.setDuration(350)  # time in ms
        self.pulse_anim.setStartValue(10)
        self.pulse_anim.setEndValue(20)

        self.animations_group = QSequentialAnimationGroup()
        self.animations_group.addAnimation(self.animation)
        self.animations_group.addAnimation(self.pulse_anim)

        self.stateChanged.connect(self.setup_animation)

    def sizeHint(self):
        return QSize(58, 45)

    def hitButton(self, pos: QPoint):
        return self.contentsRect().contains(pos)

    @pyqtSlot(int)
    def setup_animation(self, value):
        self.animations_group.stop()
        if value:
            self.animation.setEndValue(1)
        else:
            self.animation.setEndValue(0)
        self.animations_group.start()

    def paintEvent(self, e: QPaintEvent):

        contRect = self.contentsRect()
        handleRadius = round(0.24 * contRect.height())

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        p.setPen(self._transparent_pen)
        barRect = QRectF(0, 0, contRect.width() - handleRadius, 0.40 * contRect.height())
        barRect.moveCenter(contRect.center())
        rounding = barRect.height() / 2

        # the handle will move along this line
        trailLength = contRect.width() - 2 * handleRadius

        xPos = contRect.x() + handleRadius + trailLength * self._handle_position

        if self.pulse_anim.state() == QPropertyAnimation.Running:
            p.setBrush(self._pulse_checked_animation if self.isChecked() else self._pulse_unchecked_animation)
            p.drawEllipse(QPointF(xPos, barRect.center().y()), self._pulse_radius, self._pulse_radius)

        if self.isChecked():
            p.setBrush(self._bar_checked_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            p.setBrush(self._handle_checked_brush)

        else:
            p.setBrush(self._bar_brush)
            p.drawRoundedRect(barRect, rounding, rounding)
            p.setPen(self._light_grey_pen)
            p.setBrush(self._handle_brush)

        p.drawEllipse(QPointF(xPos, barRect.center().y()), handleRadius, handleRadius)

        p.end()

    @pyqtProperty(float)
    def handle_position(self):
        return self._handle_position

    @handle_position.setter
    def handle_position(self, pos):
        """change the property
        we need to trigger QWidget.update() method, either by:
            1- calling it here [ what we doing ].
            2- connecting the QPropertyAnimation.valueChanged() signal to it.
        """
        self._handle_position = pos
        self.update()

    @pyqtProperty(float)
    def pulse_radius(self):
        return self._pulse_radius

    @pulse_radius.setter
    def pulse_radius(self, pos):
        self._pulse_radius = pos
        self.update()


class CustomImageButton(QPushButton):
    """Replaces the button frame with an image and custom animation. 
    Same principle applies to ``QLabel``, etc.\n
    Parameters
    ----------
    ``icon_size`` : in pixels.
    ``icon_max_size`` : in pixels.
    ``icon`` : path to default icon.
    ``icon_on_click`` : path to icon for ``mousePress`` event.
    """
    def __init__(
        self,
        parent=None,
        icon_size: int = 30,
        icon_max_size: int = None,
        icon: str = None,
        icon_on_click: str = None,
        custom_icons=None,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)

        self._ICONS=custom_icons
        self._size = icon_size
        self._max_size = icon_max_size if icon_max_size is not None else icon_size
        self._icon = QtGui.QIcon(icon)
        self._icon_on_click = QtGui.QIcon(icon_on_click)

        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setSizePolicy(sizePolicy)

        self.setStyleSheet("border: none;" "margin: 0px;" "padding: 0px;")

        self.setIcon(self._icon)
        self.setIconSize(QSize(self._size, self._size))
        self.setFixedSize(self._max_size, self._max_size)  # png size -> max size possible

        self._animation = QtCore.QVariantAnimation(
            self,
            startValue=1.0,
            endValue=1.07,
            duration=600,
            valueChanged=self.on_valueChanged,
        )

    @property
    def icon(self):
        return self._icon

    @icon.setter
    def icon(self, icon):
        if self.icon == icon:
            return
        elif icon == "download_success" and self._ICONS is not None:
            self._icon = QIcon(self._ICONS.cloud_download_green)
        elif icon == "download_fail" and self._ICONS is not None:
            self._icon = QIcon(self._ICONS.cloud_download_red)
        elif icon == "conversion_finished" and self._ICONS is not None:
            self._icon = QIcon(self._ICONS.file_download_done_green)
        else:
            self._icon = icon
        self.setIcon(self._icon)
        self.update()

    def start_animation(self):
        if self._animation.state() != QtCore.QAbstractAnimation.Running:
            self._animation.start()

    def stop_animation(self):
        if self._animation.state() == QtCore.QAbstractAnimation.Running:
            self._animation.stop()

    @QtCore.pyqtSlot(QtCore.QVariant)
    def on_valueChanged(self, value):
        icon_size = self.iconSize().width()
        if icon_size < self._max_size:
            self.setIconSize(self.iconSize() * value)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.setIcon(self._icon_on_click)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.setIcon(self._icon)

    def enterEvent(self, event):
        self.start_animation()

    def leaveEvent(self, event):
        self.stop_animation()
        self.setIconSize(QSize(self._size, self._size))

class CustomDateEdit(QtWidgets.QDateEdit):
    def __init__(self, parent=None,**kwargs):
        super().__init__(parent, calendarPopup=True,**kwargs)
        today = QtCore.QDate.currentDate()
        self.setDate(today)
        
        
class CustomListWidget(QtWidgets.QListWidget):
    def __init__(self, parent=None,**kwargs):
        super().__init__(parent,**kwargs)  
        
    # def event(self, event):
    #     if (event.type() == QtCore.QEvent.KeyPress) and (
    #         event.key() == Qt.Key_Up or
    #         event.key() == Qt.Key_Down
    #         ):
    #         print('Parent handling Up')
    #         return True
    #     return QWidget.event(self, event)

    def eventFilter(self, widget, event):
        if (event.type() == QtCore.QEvent.KeyPress) and (
            event.key() == Qt.Key_Up or
            event.key() == Qt.Key_Down
            ):
            print('Sending space event to parent...')
            self.event(event)
            return True
        return super().eventFilter(widget, event)