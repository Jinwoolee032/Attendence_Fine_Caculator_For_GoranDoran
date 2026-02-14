from src.main_window import MainWindow
from PyQt6.QtWidgets import QApplication
import sys

def main():
    app = QApplication(sys.argv)    
    
    # Set global font or style if needed
    # app.setStyle("Fusion") 
    
    from src.data_manager import DataManager
    
    # Load data first
    data_manager = DataManager()
    
    # Create Main Window with loaded data
    window = MainWindow(data_manager)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()