import sys, os, psutil, csv, time
from datetime import datetime
from PyQt5 import QtWidgets, QtGui, QtCore
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# ---------------------- Performance Graph Widget ----------------------
class PerfGraph(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure(figsize=(5,3))
        self.canvas = FigureCanvas(self.figure)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.canvas)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("CPU Usage (%)")
        self.ax.set_ylim(0,100)
        self.x_data = []
        self.y_data = []

    def update_graph(self):
        cpu = psutil.cpu_percent()
        t = datetime.now().strftime("%H:%M:%S")
        self.x_data.append(t)
        self.y_data.append(cpu)
        if len(self.x_data)>20:
            self.x_data.pop(0)
            self.y_data.pop(0)
        self.ax.clear()
        self.ax.plot(self.x_data,self.y_data, color='cyan', marker='o')
        self.ax.set_ylim(0,100)
        self.ax.set_title("CPU Usage (%)")
        self.canvas.draw()

# ---------------------- Main Window ----------------------
class TaskManager(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mini Task Manager - Pro")
        self.resize(1000,600)
        self.setWindowIcon(QtGui.QIcon("app_icon.ico"))

        self.central = QtWidgets.QWidget()
        self.setCentralWidget(self.central)
        layout = QtWidgets.QVBoxLayout(self.central)

        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)

        # ---------------------- Correct Tab Initialization Order ----------------------
        self.init_app_history_tab()   # Must come first, so history_table exists
        self.init_process_tab()       # Now safe to call refresh_processes()
        self.init_perf_tab()
        self.init_users_tab()
        self.init_details_tab()

        # Timer for auto-refresh
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.auto_refresh)
        self.timer.start(2000)  # refresh every 2 sec

    # ---------------------- Tabs ----------------------
    def init_process_tab(self):
        self.process_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.process_tab, "Processes")
        layout = QtWidgets.QVBoxLayout(self.process_tab)

        # Table
        self.proc_table = QtWidgets.QTableWidget(0,7)
        self.proc_table.setHorizontalHeaderLabels(['PID','Name','CPU%','Memory%','Disk Read','Disk Write','Status'])
        layout.addWidget(self.proc_table)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_processes)
        kill_btn = QtWidgets.QPushButton("Kill Task")
        kill_btn.clicked.connect(self.kill_task)
        export_btn = QtWidgets.QPushButton("Export CSV")
        export_btn.clicked.connect(self.export_process_csv)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(kill_btn)
        btn_layout.addWidget(export_btn)
        layout.addLayout(btn_layout)

        # Initial refresh (safe because history_table exists)
        self.refresh_processes()

    def init_perf_tab(self):
        self.perf_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.perf_tab, "Performance")
        layout = QtWidgets.QVBoxLayout(self.perf_tab)
        self.graph = PerfGraph()
        layout.addWidget(self.graph)
        self.perf_timer = QtCore.QTimer()
        self.perf_timer.timeout.connect(self.graph.update_graph)
        self.perf_timer.start(1000)

    def init_app_history_tab(self):
        self.history_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.history_tab, "App History")
        layout = QtWidgets.QVBoxLayout(self.history_tab)
        self.history_table = QtWidgets.QTableWidget(0,5)
        self.history_table.setHorizontalHeaderLabels(['Time','PID','Name','CPU%','Memory%'])
        layout.addWidget(self.history_table)

    def init_users_tab(self):
        self.users_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.users_tab,"Users")
        layout = QtWidgets.QVBoxLayout(self.users_tab)
        self.users_table = QtWidgets.QTableWidget(0,3)
        self.users_table.setHorizontalHeaderLabels(['User','Terminal','Started'])
        layout.addWidget(self.users_table)
        self.refresh_users()

    def init_details_tab(self):
        self.details_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.details_tab,"Details")
        layout = QtWidgets.QVBoxLayout(self.details_tab)
        self.details_text = QtWidgets.QTextEdit()
        self.details_text.setReadOnly(True)
        layout.addWidget(self.details_text)

    # ---------------------- Process Functions ----------------------
    def refresh_processes(self):
        self.proc_table.setRowCount(0)
        for proc in psutil.process_iter(['pid','name','cpu_percent','memory_percent','status','io_counters']):
            row = self.proc_table.rowCount()
            self.proc_table.insertRow(row)
            self.proc_table.setItem(row,0,QtWidgets.QTableWidgetItem(str(proc.info['pid'])))
            self.proc_table.setItem(row,1,QtWidgets.QTableWidgetItem(str(proc.info['name'])))
            self.proc_table.setItem(row,2,QtWidgets.QTableWidgetItem(str(proc.info['cpu_percent'])))
            self.proc_table.setItem(row,3,QtWidgets.QTableWidgetItem(str(proc.info['memory_percent'])))
            io = proc.info.get('io_counters')
            if io:
                self.proc_table.setItem(row,4,QtWidgets.QTableWidgetItem(str(io.read_bytes)))
                self.proc_table.setItem(row,5,QtWidgets.QTableWidgetItem(str(io.write_bytes)))
            else:
                self.proc_table.setItem(row,4,QtWidgets.QTableWidgetItem("0"))
                self.proc_table.setItem(row,5,QtWidgets.QTableWidgetItem("0"))
            self.proc_table.setItem(row,6,QtWidgets.QTableWidgetItem(str(proc.info['status'])))
        self.log_history()

    def kill_task(self):
        selected = self.proc_table.selectedItems()
        if selected:
            pid = int(selected[0].text())
            try:
                psutil.Process(pid).kill()
                QtWidgets.QMessageBox.information(self,"Success","Process killed successfully")
                self.refresh_processes()
            except Exception as e:
                QtWidgets.QMessageBox.warning(self,"Error",str(e))

    def export_process_csv(self):
        filename = os.path.join(LOG_DIR,f"processes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        with open(filename,'w',newline='') as f:
            writer = csv.writer(f)
            header = [self.proc_table.horizontalHeaderItem(i).text() for i in range(self.proc_table.columnCount())]
            writer.writerow(header)
            for row in range(self.proc_table.rowCount()):
                writer.writerow([self.proc_table.item(row,col).text() for col in range(self.proc_table.columnCount())])
        QtWidgets.QMessageBox.information(self,"Exported",f"CSV saved as {filename}")

    def refresh_users(self):
        self.users_table.setRowCount(0)
        for user in psutil.users():
            row = self.users_table.rowCount()
            self.users_table.insertRow(row)
            self.users_table.setItem(row,0,QtWidgets.QTableWidgetItem(str(user.name)))
            self.users_table.setItem(row,1,QtWidgets.QTableWidgetItem(str(user.terminal)))
            self.users_table.setItem(row,2,QtWidgets.QTableWidgetItem(str(user.started)))

    def log_history(self):
        for proc in psutil.process_iter(['pid','name','cpu_percent','memory_percent']):
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            self.history_table.setItem(row,0,QtWidgets.QTableWidgetItem(datetime.now().strftime("%H:%M:%S")))
            self.history_table.setItem(row,1,QtWidgets.QTableWidgetItem(str(proc.info['pid'])))
            self.history_table.setItem(row,2,QtWidgets.QTableWidgetItem(str(proc.info['name'])))
            self.history_table.setItem(row,3,QtWidgets.QTableWidgetItem(str(proc.info['cpu_percent'])))
            self.history_table.setItem(row,4,QtWidgets.QTableWidgetItem(str(proc.info['memory_percent'])))

    def auto_refresh(self):
        self.refresh_processes()
        self.refresh_users()

# ---------------------- Run App ----------------------
if __name__=="__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = TaskManager()
    window.show()
    sys.exit(app.exec_())
