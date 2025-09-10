import sys
import os
import threading
import atexit  # Import atexit for cleanup
import keyboard  # pip install keyboard
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QTextEdit, QPushButton,
    QFileDialog, QLabel, QSizePolicy, QGraphicsDropShadowEffect
)
# --- CHANGE: Import QObject and pyqtSignal for thread-safe communication
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, pyqtProperty, QTimer, QObject, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap

TEMP_SCREENSHOT = os.path.join(os.path.expanduser("~"), "screenshot_temp.png")


# --- Screen Flash Effect (No changes needed) ---
class ScreenFlash(QWidget):
    def __init__(self, duration=400, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: white;")
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(duration)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.finished.connect(self.close)

    def start(self):
        self.show()
        self.anim.start()


# --- Pop-out Screenshot Preview ---
class ThumbnailPopup(QWidget):
    def __init__(self, pixmap: QPixmap, duration=5000):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.label = QLabel(self)
        self.label.setPixmap(
            pixmap.scaled(700, 400, Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
        )
        self.resize(self.label.sizeHint())
        self.label.setStyleSheet("""
            border: 2px solid #666;
            border-radius: 10px;
            background-color: rgba(30, 30, 30, 220);
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setOffset(0, 0)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.setGraphicsEffect(shadow)

        # --- CHANGE: Use availableGeometry to avoid taskbars/docks
        screen = QApplication.primaryScreen().availableGeometry()
        margin = 20
        self.move(screen.width() - self.width() - margin,
                  screen.height() - self.height() - margin)

        self._drag_pos = None
        self.show()
        QTimer.singleShot(duration, self.fade_out)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def fade_out(self):
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(1000)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.finished.connect(self.close)
        anim.start()
        self._anim = anim


# --- Hover Icon Widget (No changes needed) ---
class IconWithHoverLabel(QWidget):
    def __init__(self, icon_text, label_text, click_handler=None):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.button = QPushButton(icon_text)
        self.button.setFixedSize(48, 48)
        self.button.setStyleSheet("border: none; font-size: 22px; color: #cccccc;")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        if click_handler:
            self.button.clicked.connect(click_handler)

        self.label = QLabel(label_text)
        self.label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        self.label.hide()

        layout.addWidget(self.button, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.setLayout(layout)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def enterEvent(self, event):
        self.label.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.label.hide()
        super().leaveEvent(event)


# --- Main Input Widget (No changes needed) ---
class AnimatedBorderWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(75)
        self.setMinimumWidth(1000)
        self.border_color = QColor(255, 179, 186)
        self.border_width = 3
        self.radius = 40
        self.user_prompt = ""
        self.inner_bg_color = QColor(32, 33, 36)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(30, 10, 30, 10)
        main_layout.setSpacing(8)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(20)

        plus_widget = IconWithHoverLabel("+", "Attach", self.open_file_explorer)
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("How can I help you today?")
        self.text_input.setStyleSheet("""
            QTextEdit { border: none; background: transparent; color: white; font-size: 20px; }
            QTextEdit:!focus { color: #cccccc; }
        """)
        self.text_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.text_input.installEventFilter(self)
        self.text_input.textChanged.connect(self.adjust_height)

        mic_widget = IconWithHoverLabel("🎤", "Voice", self.empty_voice_function)
        screenshot_widget = IconWithHoverLabel("📸", "Screenshot", self.take_screenshot)
        
        self.ai_label = QLabel("✨ ISO")
        self.ai_label.setStyleSheet("color: #ffffff; font-size: 22px;")
        self.ai_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        top_layout.addWidget(plus_widget)
        top_layout.addWidget(self.text_input)
        top_layout.addWidget(mic_widget)
        top_layout.addWidget(screenshot_widget)
        top_layout.addWidget(self.ai_label)

        main_layout.addLayout(top_layout)
        self.setLayout(main_layout)

        self.popup = None

    def empty_voice_function(self):
        print("Voice function triggered")

    def adjust_height(self):
        doc_height = self.text_input.document().size().height()
        new_height = max(75, int(doc_height) + 40)
        self.setFixedHeight(new_height)

    def eventFilter(self, source, event):
        if source == self.text_input and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.text_input.insertPlainText("\n")
                else:
                    self.save_user_prompt()
                return True
        return super().eventFilter(source, event)

    def save_user_prompt(self):
        self.user_prompt = self.text_input.toPlainText().strip()
        if self.user_prompt:
            print("User prompt saved:", self.user_prompt)
        self.text_input.clear()

    def open_file_explorer(self):
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_dialog.setNameFilter("Images and Documents (*.png *.jpg *.jpeg *.pdf *.docx *.txt)")
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            print("Selected:", selected_files)

    def take_screenshot(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        pixmap = screen.grabWindow(0)
        pixmap.save(TEMP_SCREENSHOT, "png")
        flash = ScreenFlash()
        flash.start()
        if self.popup and self.popup.isVisible():
            self.popup.close()
        self.popup = ThumbnailPopup(pixmap)

    def setBorderColor(self, color: QColor):
        self.border_color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.border_color, self.border_width)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        rect = self.rect().adjusted(self.border_width // 2, self.border_width // 2, -self.border_width // 2, -self.border_width // 2)
        painter.drawRoundedRect(rect, self.radius, self.radius)
        inner_rect = self.rect().adjusted(self.border_width, self.border_width, -self.border_width, -self.border_width)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.inner_bg_color)
        painter.drawRoundedRect(inner_rect, self.radius - self.border_width, self.radius - self.border_width)
        super().paintEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            QApplication.quit()
        else:
            super().keyPressEvent(event)


# --- Property for rainbow border animation (No changes needed) ---
def get_border_color(self):
    return self.border_color
def set_border_color(self, color):
    self.setBorderColor(color)
AnimatedBorderWidget.borderColor = pyqtProperty(QColor, fget=get_border_color, fset=set_border_color)


# --- CHANGE: Create a dedicated QObject for emitting signals from the worker thread ---
class HotkeyEmitter(QObject):
    show_widget_signal = pyqtSignal()

# --- Main program ---
def main():
    app = QApplication(sys.argv)

    # --- CHANGE: Register a function to clean up the temp file on exit
    atexit.register(lambda: os.remove(TEMP_SCREENSHOT) if os.path.exists(TEMP_SCREENSHOT) else None)

    widget = AnimatedBorderWidget()
    widget.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    screen = app.primaryScreen().geometry()
    x = (screen.width() - widget.width()) // 2
    final_y = 50
    start_y = -widget.height()
    widget.move(x, start_y)

    # Rainbow border animation logic (unchanged)
    rainbow_colors = [
        QColor(255, 179, 186), QColor(255, 223, 186), QColor(255, 255, 186),
        QColor(186, 255, 201), QColor(186, 225, 255), QColor(201, 186, 255),
        QColor(255, 186, 255),
    ]
    widget._color_index = 0

    def animate():
        start = rainbow_colors[widget._color_index]
        end = rainbow_colors[(widget._color_index + 1) % len(rainbow_colors)]
        anim = QPropertyAnimation(widget, b"borderColor")
        anim.setDuration(3000)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        def on_finished():
            widget._color_index = (widget._color_index + 1) % len(rainbow_colors)
            animate()
        
        anim.finished.connect(on_finished)
        anim.start()
        widget._anim = anim
    
    animate()

    # Function to show widget (unchanged)
    def show_widget():
        if widget.isVisible():
            return
        widget.show()
        slide_anim = QPropertyAnimation(widget, b"pos")
        slide_anim.setDuration(800)
        slide_anim.setStartValue(QPoint(x, start_y))
        slide_anim.setEndValue(QPoint(x, final_y))
        slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        slide_anim.start()
        widget._slide_anim = slide_anim

        fade_anim = QPropertyAnimation(widget, b"windowOpacity")
        fade_anim.setDuration(800)
        fade_anim.setStartValue(0.0)
        fade_anim.setEndValue(1.0)
        fade_anim.start()
        widget._fade_anim = fade_anim

    # --- CHANGE: Refactored hotkey listener to use signals and slots ---
    # 1. The listener function now takes an emitter object
    def hotkey_listener(emitter: HotkeyEmitter):
        # When hotkey is pressed, emit the signal instead of calling the function directly
        keyboard.add_hotkey('`', lambda: emitter.show_widget_signal.emit())
        keyboard.wait()

    # 2. Create an instance of our emitter
    emitter = HotkeyEmitter()
    # 3. Connect the signal from the emitter to the show_widget slot (function)
    emitter.show_widget_signal.connect(show_widget)

    # 4. Start the thread, passing the emitter instance to it
    thread = threading.Thread(target=hotkey_listener, args=(emitter,), daemon=True)
    thread.start()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()