import sys
import matplotlib
matplotlib.use('qt5agg')

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import QMainWindow, QApplication, QPushButton, QWidget, QTabWidget, QVBoxLayout, QFileDialog
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot, Qt

class CustomNavigationToolbar(NavigationToolbar):
    def save_figure(self, *args):
        """Override save figure to set default filename"""
        canvas = self.canvas
        initial_filename = self.parent().windowTitle()  # Get tab title as filename
        
        file_types = self.canvas.get_supported_filetypes_grouped()
        sorted_filetypes = sorted(file_types.items())
        default_filetype = self.canvas.get_default_filetype()

        start = f"{initial_filename}.{default_filetype}"
        
        filters = []
        selected_filter = None
        
        for name, exts in sorted_filetypes:
            exts_list = " ".join(['*.%s' % ext for ext in exts])
            filter_ = f'{name} ({exts_list})'
            if default_filetype in exts:
                selected_filter = filter_
            filters.append(filter_)
            
        filters = ';;'.join(filters)
        
        fname, filter_selected = QFileDialog.getSaveFileName(
            self.parent(), "Choose a filename to save to",
            start, filters, selected_filter)
            
        if fname:
            try:
                self.canvas.figure.savefig(fname)
            except Exception as e:
                print(f"Failed to save figure: {str(e)}")

class plotWindow():
    def __init__(self, parent=None):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.MainWindow = QMainWindow()
        self.MainWindow.setWindowTitle("VZ Spectral Analyzer Plot Window")
        self.MainWindow.setAttribute(Qt.WA_DeleteOnClose)
        self.MainWindow.closeEvent = self.handle_close
        
        self.canvases = []
        self.figure_handles = []
        self.toolbar_handles = []
        self.tab_handles = []
        self.current_window = -1
        self.tabs = QTabWidget()
        self.MainWindow.setCentralWidget(self.tabs)
        self.MainWindow.resize(1280, 900)
        
    def handle_close(self, event):
        """Handle window close event"""
        # Only reset reference, don't clear plots
        self.MainWindow.parent_analyzer.plot_window = None
        event.accept()

    def addPlot(self, title, figure):
        new_tab = QWidget()
        layout = QVBoxLayout()
        new_tab.setLayout(layout)

        figure.subplots_adjust(left=0.05, right=0.99, bottom=0.05, top=0.91, wspace=0.2, hspace=0.2)
        new_canvas = FigureCanvas(figure)
        new_toolbar = CustomNavigationToolbar(new_canvas, new_tab)

        layout.addWidget(new_canvas)
        layout.addWidget(new_toolbar)
        self.tabs.addTab(new_tab, title)
        
        new_tab.setWindowTitle(title)  # Set window title for filename lookup

        self.toolbar_handles.append(new_toolbar)
        self.canvases.append(new_canvas)
        self.figure_handles.append(figure)
        self.tab_handles.append(new_tab)

    def show(self):
        self.app.exec_()
