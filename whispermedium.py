import sys
import threading
import time
import numpy as np
import tempfile
import sounddevice as sd
import scipy.io.wavfile
from PIL import ImageGrab, ImageQt
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout, QTextEdit
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from pynput import keyboard
from faster_whisper import WhisperModel

# --- Configuration ---
HOTKEY = keyboard.Key.f9
SCREENSHOT_PATH = 'screenshot.png'
WHISPER_MODEL_SIZE = 'medium'  # Changed from 'small' to 'medium'
SAMPLERATE = 16000  # Standard for Whisper

# --- Global variables ---
is_listening = False
listener_thread = None

# --- Initialize Whisper ---
print("Loading Whisper model...")
model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu")  # Use 'cuda' if available for better performance
print("Whisper model loaded.")

# --- PyQt6 Application ---
class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Assistant Test GUI")
        self.layout = QVBoxLayout()

        self.image_label = QLabel("Screenshot will appear here.")
        self.text_edit = QTextEdit("Recognized text will appear here.")
        self.text_edit.setReadOnly(True)

        self.layout.addWidget(self.image_label)
        self.layout.addWidget(self.text_edit)

        self.setLayout(self.layout)
        self.setGeometry(100, 100, 600, 600)

    def show_screenshot(self):
        image = ImageGrab.grab()
        image.save(SCREENSHOT_PATH)
        qt_image = ImageQt.ImageQt(image)
        pixmap = QPixmap.fromImage(qt_image)
        self.image_label.setPixmap(pixmap.scaled(500, 300, Qt.AspectRatioMode.KeepAspectRatio))
        print("Screenshot displayed.")

    def show_text(self, text):
        self.text_edit.setText(text)
        print("Recognized text updated.")

app_instance = None

# --- Record and transcribe audio ---
def record_audio():
    global is_listening
    print("Recording audio...")

    recording = []
    stream = sd.InputStream(samplerate=SAMPLERATE, channels=1, dtype='int16')
    stream.start()

    try:
        while is_listening:
            data, overflowed = stream.read(1024)
            if overflowed:
                print("Overflow occurred.")
            recording.append(data)
    except Exception as e:
        print("Error during recording:", e)

    stream.stop()
    print("Recording stopped.")

    audio_data = np.concatenate(recording, axis=0)

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = f"{tmpdir}/recording.wav"
        scipy.io.wavfile.write(file_path, SAMPLERATE, audio_data)
        print(f"Saved audio at {file_path}, starting transcription...")
        segments, info = model.transcribe(file_path, beam_size=5, best_of=5)
        full_text = ""
        for segment in segments:
            print("Segment:", segment.text)
            full_text += segment.text + " "
        full_text = full_text.strip()
        app_instance.show_text(full_text)
        print("Transcription completed. Recognized text:", full_text)

# --- Hotkey press handler ---
def on_press(key):
    global is_listening, listener_thread
    if key == HOTKEY and not is_listening:
        is_listening = True
        print("F9 pressed – starting process.")
        app_instance.show_screenshot()
        listener_thread = threading.Thread(target=record_audio)
        listener_thread.start()

# --- Hotkey release handler ---
def on_release(key):
    global is_listening
    if key == HOTKEY and is_listening:
        is_listening = False
        print("F9 released – stopping recording.")

# --- Main ---
def main():
    global app_instance
    qt_app = QApplication(sys.argv)
    app_instance = App()
    app_instance.show()

    print("Hold F9 to take screenshot and record speech.")
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    qt_app.exec()  # Do not use sys.exit(), keep window open after process ends

if __name__ == "__main__":
    main()
