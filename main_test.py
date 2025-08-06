# main_test.py
import sys
from PySide6.QtWidgets import QApplication, QWidget, QPushButton

app = QApplication(sys.argv)
window = QWidget()
button = QPushButton("Click Me", window)
window.show()
sys.exit(app.exec())
