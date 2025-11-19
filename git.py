#!/usr/bin/env python3
"""
Enhanced Mini Task Manager - Pro (extended features)
Requirements:
  - PyQt5
  - psutil
  - matplotlib
  - (optional) GPUtil for NVIDIA GPU info

Run:
  python task_manager_pro_extended.py
"""

import sys
import os
import csv
import platform
import shutil
import subprocess
from datetime import datetime
from functools import partial

from PyQt5 import QtWidgets, QtGui, QtCore
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import psutil

# optional GPU support
try:
    import GPUtil
    GPU_AVAILABLE = True
except Exception:
    GPU_AVAILABLE = False

LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# ---------------------- Small helper functions ----------------------
def human_bytes(n):
    """Convert bytes to human readable string."""
    try:
        n = float(n)
    except Exception:
        return "0 B"
    step = 1024.0
    units = ['B','KB','MB','GB','TB']
    i = 0
    while n >= step and i < len(units)-1:
        n /= step
        i += 1
    return f"{n:.2f} {units[i]}"

def open_file_location(path):
    """Open file explorer at path (OS-specific)."""
    if not path:
        return
    try:
        if platform.system() == "Windows":
            if os.path.isdir(path):
                os.startfile(path)
            else:
                os.startfile(os.path.dirname(path))
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path if os.path.isdir(path) else os.path.dirname(path)])
        else:
            # linux
            opener = shutil.which("xdg-open") or shutil.which("gio") or shutil.which("gnome-open")
            if opener:
                subprocess.Popen([opener, path if os.path.isdir(path) else os.path.dirname(path)])
    except Exception as e:
        QtWidgets.QMessageBox.warning(None, "Open Folder", f"Could not open folder: {e}")

def safe_process(proc):
    """Return safe psutil.Process wrapper or None."""
    try:
        return psutil.Process(proc.pid) if isinstance(proc, psutil.Process) else psutil.Process(int(proc))
    except Exception:
        return None

# ---------------------- Process mini-chart widget ----------------------
class MiniProcChart(QtWidgets.QWidget):
    def __init__(self, parent=None, maxlen=30):
        super().__init__(parent)
        self.figure = Figure(figsize=(4,1.4))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_ylim(0,100)
        self.cpu_data = []
        self.mem_data = []
        self.times = []
        self.maxlen = maxlen
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.canvas)

    def push(self, cpu, mem, t):
        self.cpu_data.append(cpu)
        self.mem_data.append(mem)
        self.times.append(t)
        if len(self.times) > self.maxlen:
            self.times.pop(0); self.cpu_data.pop(0); self.mem_data.pop(0)
        self.redraw()

    def clear(self):
        self.cpu_data=[]; self.mem_data=[]; self.times=[]
        self.redraw()

    def redraw(self):
        self.ax.clear()
        self.ax.set_ylim(0,100)
        if self.times:
            self.ax.plot(self.times, self.cpu_data, label="CPU%")
            self.ax.plot(self.times, self.mem_data, label="Mem%")
            self.ax.legend(fontsize='small')
            self.ax.tick_params(axis='x', labelrotation=30)
        self.canvas.draw_idle()

# ---------------------- Performance Graph Widget (system) ----------------------
class PerfGraph(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure(figsize=(6,3))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("CPU & Memory Usage (%)")
        self.ax.set_ylim(0,100)
        self.x_data = []
        self.cpu_data = []
        self.mem_data = []
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.canvas)
        self.canvas.draw()

    def update_graph(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        t = datetime.now().strftime("%H:%M:%S")
        self.x_data.append(t)
        self.cpu_data.append(cpu)
        self.mem_data.append(mem)
        if len(self.x_data) > 40:
            self.x_data.pop(0); self.cpu_data.pop(0); self.mem_data.pop(0)
        self.ax.clear()
        self.ax.plot(self.x_data, self.cpu_data, marker='o', label='CPU')
        self.ax.plot(self.x_data, self.mem_data, marker='x', label='Memory')
        self.ax.set_ylim(0,100)
        self.ax.set_title("CPU & Memory Usage (%)")
        self.ax.legend()
        self.ax.tick_params(axis='x', labelrotation=30)
        self.canvas.draw_idle()

# ---------------------- Main Window ----------------------
class TaskManager(QtWidgets.QMainWindow):
    REFRESH_INTERVAL_MS = 2000
    PERF_INTERVAL_MS = 1000
    PROC_DETAILS_INTERVAL_MS = 1000

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mini Task Manager - Pro (Extended)")
        self.resize(1300,800)
        self.setWindowIcon(QtGui.QIcon("app_icon.ico") if os.path.exists("app_icon.ico") else QtGui.QIcon())

        self.central = QtWidgets.QWidget()
        self.setCentralWidget(self.central)
        main_layout = QtWidgets.QVBoxLayout(self.central)

        # Top controls: search + refresh + export
        top_bar = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search by name / PID / user / cmdline...")
        self.search_edit.textChanged.connect(self.refresh_processes)
        top_bar.addWidget(self.search_edit)
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_processes)
        top_bar.addWidget(refresh_btn)
        export_btn = QtWidgets.QPushButton("Export Processes CSV")
        export_btn.clicked.connect(self.export_process_csv)
        top_bar.addWidget(export_btn)
        main_layout.addLayout(top_bar)

        self.tabs = QtWidgets.QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tabs: App History, Performance, Processes, Network, Services, Users, Details
        self.init_app_history_tab()
        self.init_perf_tab()
        self.init_process_tab()
        self.init_network_tab()
        self.init_services_tab()
        self.init_users_tab()
        self.init_details_tab()

        # Timers
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.auto_refresh)
        self.timer.start(self.REFRESH_INTERVAL_MS)

    # ---------------------- Tab initializers ----------------------
    def init_process_tab(self):
        self.process_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.process_tab, "Processes")
        layout = QtWidgets.QHBoxLayout(self.process_tab)

        # Left: process table
        left = QtWidgets.QVBoxLayout()
        self.proc_table = QtWidgets.QTableWidget(0,14)
        headers = ['PID','Name','User','CPU%','Memory%','Threads','Start','Status','Disk Read','Disk Write','GPU%','Path','Cmdline','Nice']
        self.proc_table.setHorizontalHeaderLabels(headers)
        self.proc_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.proc_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.proc_table.itemSelectionChanged.connect(self.on_proc_selected)
        self.proc_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.proc_table.customContextMenuRequested.connect(self.process_context_menu)
        self.proc_table.horizontalHeader().setStretchLastSection(False)
        self.proc_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        left.addWidget(self.proc_table)

        btn_layout = QtWidgets.QHBoxLayout()
        kill_btn = QtWidgets.QPushButton("Terminate")
        kill_btn.clicked.connect(self.terminate_selected)
        kill_btn.setToolTip("Graceful terminate")
        force_kill_btn = QtWidgets.QPushButton("Kill")
        force_kill_btn.clicked.connect(self.kill_selected)
        suspend_btn = QtWidgets.QPushButton("Suspend")
        suspend_btn.clicked.connect(self.suspend_selected)
        resume_btn = QtWidgets.QPushButton("Resume")
        resume_btn.clicked.connect(self.resume_selected)
        btn_layout.addWidget(kill_btn); btn_layout.addWidget(force_kill_btn); btn_layout.addWidget(suspend_btn); btn_layout.addWidget(resume_btn)
        left.addLayout(btn_layout)
        layout.addLayout(left, 3)

        # Right: details / chart for selected process
        right = QtWidgets.QVBoxLayout()
        self.details_text = QtWidgets.QTextEdit()
        self.details_text.setReadOnly(True)
        right.addWidget(self.details_text, 2)
        self.proc_chart = MiniProcChart()
        right.addWidget(self.proc_chart, 1)
        layout.addLayout(right, 2)

        # initial load
        self.refresh_processes()

    def init_perf_tab(self):
        self.perf_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.perf_tab, "Performance")
        layout = QtWidgets.QVBoxLayout(self.perf_tab)
        self.gpu_label = QtWidgets.QLabel()
        layout.addWidget(self.gpu_label)
        self.graph = PerfGraph()
        layout.addWidget(self.graph)
        # perf timer
        self.perf_timer = QtCore.QTimer(self)
        self.perf_timer.timeout.connect(self.graph.update_graph)
        self.perf_timer.start(self.PERF_INTERVAL_MS)
        self.update_gpu_label()

    def init_app_history_tab(self):
        self.history_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.history_tab, "App History")
        layout = QtWidgets.QVBoxLayout(self.history_tab)
        self.history_table = QtWidgets.QTableWidget(0,6)
        self.history_table.setHorizontalHeaderLabels(['Time','PID','Name','CPU%','Memory%','GPU%'])
        layout.addWidget(self.history_table)

    def init_network_tab(self):
        self.net_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.net_tab, "Network")
        layout = QtWidgets.QVBoxLayout(self.net_tab)
        self.net_table = QtWidgets.QTableWidget(0,6)
        self.net_table.setHorizontalHeaderLabels(['Proto','Local Address','Remote Address','Status','PID','Process'])
        layout.addWidget(self.net_table)
        refresh_net_btn = QtWidgets.QPushButton("Refresh Network")
        refresh_net_btn.clicked.connect(self.refresh_network)
        layout.addWidget(refresh_net_btn)
        self.refresh_network()

    def init_services_tab(self):
        self.services_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.services_tab, "Services")
        layout = QtWidgets.QVBoxLayout(self.services_tab)
        self.services_table = QtWidgets.QTableWidget(0,4)
        self.services_table.setHorizontalHeaderLabels(['Name','Display Name','Status','PID'])
        layout.addWidget(self.services_table)
        btn_layout = QtWidgets.QHBoxLayout()
        export_sv_btn = QtWidgets.QPushButton("Export Services CSV")
        export_sv_btn.clicked.connect(self.export_services_csv)
        btn_layout.addWidget(export_sv_btn)
        layout.addLayout(btn_layout)
        self.refresh_services()

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
        self.tabs.addTab(self.details_tab,"System Details")
        layout = QtWidgets.QVBoxLayout(self.details_tab)
        self.sys_text = QtWidgets.QTextEdit()
        self.sys_text.setReadOnly(True)
        layout.addWidget(self.sys_text)
        self.refresh_system_details()

    # ---------------------- Refresh / auto functions ----------------------
    def auto_refresh(self):
        # Keep light: refresh processes & users & system summary
        self.refresh_processes()
        self.refresh_users()
        self.update_gpu_label()
        self.refresh_history_log()

    def refresh_processes(self):
        # preserve selection
        selected_pid = None
        sel_items = self.proc_table.selectedItems()
        if sel_items:
            try:
                selected_pid = int(sel_items[0].text())
            except:
                selected_pid = None

        # collect GPU usage mapping by pid if possible
        gpu_dict = {}
        if GPU_AVAILABLE:
            try:
                for gpu in GPUtil.getGPUs():
                    # GPUtil doesn't directly expose process list reliably across platforms; skip if not present
                    procs = getattr(gpu, 'processes', None) or []
                    for pid in procs:
                        gpu_dict[pid] = gpu.load * 100
                # fallback: use gpu.load as overall
            except Exception:
                gpu_dict = {}

        # The attributes we want from psutil; using process_iter is efficient
        procs = []
        try:
            for p in psutil.process_iter(['pid','name','username','cpu_percent','memory_percent','num_threads','create_time','status','io_counters','exe','cmdline','nice']):
                procs.append(p)
        except Exception:
            procs = []

        # filter by search
        q = self.search_edit.text().lower().strip()
        filtered = []
        for p in procs:
            try:
                name = (p.info.get('name') or "").lower()
                pidstr = str(p.info.get('pid',''))
                user = str(p.info.get('username') or "").lower()
                cmdline = " ".join(p.info.get('cmdline') or []).lower()
                if not q or q in name or q in pidstr or q in user or q in cmdline:
                    filtered.append(p)
            except Exception:
                continue

        # sort by CPU% desc
        filtered.sort(key=lambda x: x.info.get('cpu_percent') or 0, reverse=True)

        self.proc_table.setRowCount(0)
        for p in filtered:
            row = self.proc_table.rowCount()
            self.proc_table.insertRow(row)
            pid = p.info.get('pid')
            name = p.info.get('name') or ""
            user = p.info.get('username') or ""
            cpu = p.info.get('cpu_percent') or 0.0
            mem = round(p.info.get('memory_percent') or 0.0, 2)
            threads = p.info.get('num_threads') or 0
            start = ""
            try:
                start = datetime.fromtimestamp(p.info.get('create_time')).strftime("%Y-%m-%d %H:%M:%S") if p.info.get('create_time') else ""
            except Exception:
                start = ""
            status = str(p.info.get('status') or "")
            io = p.info.get('io_counters')
            read_b = human_bytes(io.read_bytes) if io else "0 B"
            write_b = human_bytes(io.write_bytes) if io else "0 B"
            gpu_percent = round(gpu_dict.get(pid, 0), 2) if gpu_dict else 0.0
            path = p.info.get('exe') or ""
            cmdline = " ".join(p.info.get('cmdline') or [])
            nice = str(p.info.get('nice') or "")

            # Fill table items
            items = [
                QtWidgets.QTableWidgetItem(str(pid)),
                QtWidgets.QTableWidgetItem(name),
                QtWidgets.QTableWidgetItem(str(user)),
                QtWidgets.QTableWidgetItem(str(cpu)),
                QtWidgets.QTableWidgetItem(str(mem)),
                QtWidgets.QTableWidgetItem(str(threads)),
                QtWidgets.QTableWidgetItem(start),
                QtWidgets.QTableWidgetItem(status),
                QtWidgets.QTableWidgetItem(read_b),
                QtWidgets.QTableWidgetItem(write_b),
                QtWidgets.QTableWidgetItem(str(gpu_percent)),
                QtWidgets.QTableWidgetItem(path),
                QtWidgets.QTableWidgetItem(cmdline),
                QtWidgets.QTableWidgetItem(nice),
            ]
            for col, it in enumerate(items):
                # align numeric columns
                if col in (0,3,4,5,8,9,10):
                    it.setTextAlignment(QtCore.Qt.AlignCenter)
                self.proc_table.setItem(row, col, it)

        # restore selection if possible
        if selected_pid is not None:
            matching = self.proc_table.findItems(str(selected_pid), QtCore.Qt.MatchExactly)
            if matching:
                r = matching[0].row()
                self.proc_table.selectRow(r)

        # update details for selected
        self.update_selected_details()

    def refresh_users(self):
        self.users_table.setRowCount(0)
        for u in psutil.users():
            row = self.users_table.rowCount()
            self.users_table.insertRow(row)
            self.users_table.setItem(row,0,QtWidgets.QTableWidgetItem(str(u.name)))
            self.users_table.setItem(row,1,QtWidgets.QTableWidgetItem(str(u.terminal)))
            self.users_table.setItem(row,2,QtWidgets.QTableWidgetItem(str(datetime.fromtimestamp(u.started) if isinstance(u.started, (int,float)) else str(u.started))))

    def refresh_network(self):
        self.net_table.setRowCount(0)
        try:
            conns = psutil.net_connections(kind='inet')
            for c in conns:
                laddr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else ""
                raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else ""
                proto = "TCP" if c.type == psutil.SOCK_STREAM else "UDP"
                pid = c.pid if c.pid else ""
                proc_name = ""
                if pid:
                    try:
                        proc_name = psutil.Process(pid).name()
                    except Exception:
                        proc_name = ""
                row = self.net_table.rowCount()
                self.net_table.insertRow(row)
                self.net_table.setItem(row,0,QtWidgets.QTableWidgetItem(proto))
                self.net_table.setItem(row,1,QtWidgets.QTableWidgetItem(laddr))
                self.net_table.setItem(row,2,QtWidgets.QTableWidgetItem(raddr))
                self.net_table.setItem(row,3,QtWidgets.QTableWidgetItem(str(c.status)))
                self.net_table.setItem(row,4,QtWidgets.QTableWidgetItem(str(pid)))
                self.net_table.setItem(row,5,QtWidgets.QTableWidgetItem(proc_name))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Network", f"Failed to list connections: {e}")

    def refresh_services(self):
        self.services_table.setRowCount(0)
        if platform.system() == "Windows":
            try:
                for s in psutil.win_service_iter():
                    row = self.services_table.rowCount()
                    self.services_table.insertRow(row)
                    self.services_table.setItem(row,0,QtWidgets.QTableWidgetItem(s.name()))
                    self.services_table.setItem(row,1,QtWidgets.QTableWidgetItem(s.display_name()))
                    self.services_table.setItem(row,2,QtWidgets.QTableWidgetItem(s.status()))
                    try:
                        pid = s.pid()
                    except Exception:
                        pid = ""
                    self.services_table.setItem(row,3,QtWidgets.QTableWidgetItem(str(pid)))
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Services", f"Could not enumerate services: {e}")
        else:
            self.services_table.insertRow(0)
            self.services_table.setItem(0,0,QtWidgets.QTableWidgetItem("Services listing not available on this platform"))
            self.services_table.setSpan(0,0,1,4)

    def refresh_system_details(self):
        info = []
        info.append(f"Platform: {platform.platform()}")
        info.append(f"CPU Count (logical): {psutil.cpu_count(logical=True)}")
        info.append(f"CPU Count (physical): {psutil.cpu_count(logical=False)}")
        info.append(f"Memory: {human_bytes(psutil.virtual_memory().total)} total, {psutil.virtual_memory().percent}% used")
        info.append(f"Disk usage: {human_bytes(psutil.disk_usage('/').total)} total, {psutil.disk_usage('/').percent}% used")
        info.append(f"Boot time: {datetime.fromtimestamp(psutil.boot_time()).strftime('%Y-%m-%d %H:%M:%S')}")
        self.sys_text.setPlainText("\n".join(info))

    # ---------------------- Selected process details & actions ----------------------
    def on_proc_selected(self):
        self.update_selected_details()

    def update_selected_details(self):
        sel = self.proc_table.selectedItems()
        if not sel:
            self.details_text.setPlainText("No process selected.")
            self.proc_chart.clear()
            return
        pid = int(sel[0].text())
        try:
            p = psutil.Process(pid)
        except Exception:
            self.details_text.setPlainText("Process ended or not accessible.")
            self.proc_chart.clear()
            return

        # gather details
        details = []
        details.append(f"PID: {pid}")
        details.append(f"Name: {p.name()}")
        details.append(f"User: {p.username() if hasattr(p,'username') else ''}")
        details.append(f"Status: {p.status()}")
        details.append(f"Started: {datetime.fromtimestamp(p.create_time()).strftime('%Y-%m-%d %H:%M:%S') if p.create_time() else ''}")
        details.append(f"Threads: {p.num_threads()}")
        try:
            details.append(f"CPU% (last): {p.cpu_percent(interval=None)}")
        except Exception:
            details.append("CPU% (last): N/A")
        try:
            details.append(f"Memory%: {p.memory_percent():.2f}")
        except Exception:
            details.append("Memory%: N/A")
        try:
            io = p.io_counters()
            details.append(f"IO Read: {human_bytes(io.read_bytes)}, IO Write: {human_bytes(io.write_bytes)}")
        except Exception:
            details.append("IO: N/A")
        try:
            details.append(f"Executable: {p.exe()}")
        except Exception:
            details.append("Executable: N/A")
        try:
            details.append(f"Cmdline: {' '.join(p.cmdline())}")
        except Exception:
            details.append("Cmdline: N/A")
        try:
            details.append(f"Open files: {len(p.open_files())}")
        except Exception:
            details.append("Open files: N/A")
        try:
            details.append(f"Connections: {len(p.connections())}")
        except Exception:
            details.append("Connections: N/A")
        try:
            details.append(f"Nice/Priority: {p.nice()}")
        except Exception:
            details.append("Nice/Priority: N/A")

        self.details_text.setPlainText("\n".join(details))

        # update chart with latest values
        try:
            cpu = p.cpu_percent(interval=None)
            mem = round(p.memory_percent(),2)
            t = datetime.now().strftime("%H:%M:%S")
            self.proc_chart.push(cpu, mem, t)
        except Exception:
            self.proc_chart.clear()

    def process_context_menu(self, pos):
        item = self.proc_table.itemAt(pos)
        if not item:
            return
        row = item.row()
        pid_item = self.proc_table.item(row,0)
        if not pid_item:
            return
        pid = int(pid_item.text())
        menu = QtWidgets.QMenu()
        action_terminate = menu.addAction("Terminate")
        action_kill = menu.addAction("Kill")
        action_suspend = menu.addAction("Suspend")
        action_resume = menu.addAction("Resume")
        action_priority = menu.addMenu("Set Priority")
        for label, val in [("Low", psutil.IDLE_PRIORITY_CLASS if hasattr(psutil,'IDLE_PRIORITY_CLASS') else 19),
                           ("Normal", psutil.NORMAL_PRIORITY_CLASS if hasattr(psutil,'NORMAL_PRIORITY_CLASS') else 0),
                           ("High", psutil.HIGH_PRIORITY_CLASS if hasattr(psutil,'HIGH_PRIORITY_CLASS') else -5),
                           ("Realtime", psutil.REALTIME_PRIORITY_CLASS if hasattr(psutil,'REALTIME_PRIORITY_CLASS') else -20)]:
            a = action_priority.addAction(label)
            a.triggered.connect(partial(self.set_priority_by_value, pid, label))
        action_open = menu.addAction("Open File Location")
        action_copy = menu.addAction("Copy PID")

        action = menu.exec_(self.proc_table.viewport().mapToGlobal(pos))
        if action == action_terminate:
            self.terminate_pid(pid)
        elif action == action_kill:
            self.kill_pid(pid)
        elif action == action_suspend:
            self.suspend_pid(pid)
        elif action == action_resume:
            self.resume_pid(pid)
        elif action == action_open:
            # try to get exe from table
            path_item = self.proc_table.item(row,11)
            path = path_item.text() if path_item else ""
            open_file_location(path)
        elif action == action_copy:
            QtWidgets.QApplication.clipboard().setText(str(pid))

    # CRUD-like operations
    def terminate_selected(self):
        sel = self.proc_table.selectedItems()
        if not sel:
            return
        pid = int(sel[0].text())
        self.terminate_pid(pid)

    def kill_selected(self):
        sel = self.proc_table.selectedItems()
        if not sel:
            return
        pid = int(sel[0].text())
        self.kill_pid(pid)

    def suspend_selected(self):
        sel = self.proc_table.selectedItems()
        if not sel:
            return
        pid = int(sel[0].text())
        self.suspend_pid(pid)

    def resume_selected(self):
        sel = self.proc_table.selectedItems()
        if not sel:
            return
        pid = int(sel[0].text())
        self.resume_pid(pid)

    def terminate_pid(self, pid):
        try:
            p = psutil.Process(pid)
            p.terminate()
            p.wait(timeout=3)
            QtWidgets.QMessageBox.information(self,"Terminate","Process terminated.")
        except psutil.NoSuchProcess:
            QtWidgets.QMessageBox.information(self,"Terminate","Process does not exist.")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self,"Terminate",f"Error: {e}")
        finally:
            self.refresh_processes()

    def kill_pid(self, pid):
        try:
            p = psutil.Process(pid)
            p.kill()
            p.wait(timeout=3)
            QtWidgets.QMessageBox.information(self,"Kill","Process killed.")
        except psutil.NoSuchProcess:
            QtWidgets.QMessageBox.information(self,"Kill","Process does not exist.")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self,"Kill",f"Error: {e}")
        finally:
            self.refresh_processes()

    def suspend_pid(self, pid):
        try:
            p = psutil.Process(pid)
            p.suspend()
            QtWidgets.QMessageBox.information(self,"Suspend","Process suspended.")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self,"Suspend",f"Error: {e}")
        finally:
            self.refresh_processes()

    def resume_pid(self, pid):
        try:
            p = psutil.Process(pid)
            p.resume()
            QtWidgets.QMessageBox.information(self,"Resume","Process resumed.")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self,"Resume",f"Error: {e}")
        finally:
            self.refresh_processes()

    def set_priority_by_value(self, pid, label):
        """Set priority using label friendly names. On Windows uses psutil constants if available."""
        try:
            p = psutil.Process(pid)
            if platform.system() == "Windows":
                mapping = {
                    "Low": getattr(psutil, "IDLE_PRIORITY_CLASS", 64),
                    "Normal": getattr(psutil, "NORMAL_PRIORITY_CLASS", 32),
                    "High": getattr(psutil, "HIGH_PRIORITY_CLASS", 128),
                    "Realtime": getattr(psutil, "REALTIME_PRIORITY_CLASS", 256),
                }
                val = mapping.get(label, getattr(psutil, "NORMAL_PRIORITY_CLASS", 32))
                p.nice(val)
            else:
                # Unix-like: nice values -20..19 (lower is higher priority)
                if label == "Low":
                    p.nice(19)
                elif label == "Normal":
                    p.nice(0)
                elif label == "High":
                    p.nice(-5)
                else:
                    p.nice(-20)
            QtWidgets.QMessageBox.information(self,"Priority",f"Set priority {label} for PID {pid}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self,"Priority",f"Could not set priority: {e}")
        finally:
            self.refresh_processes()

    # ---------------------- Export / Logging ----------------------
    def export_process_csv(self):
        filename = os.path.join(LOG_DIR, f"processes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        try:
            with open(filename,'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                header = [self.proc_table.horizontalHeaderItem(i).text() for i in range(self.proc_table.columnCount())]
                writer.writerow(header)
                for row in range(self.proc_table.rowCount()):
                    rowvals = []
                    for col in range(self.proc_table.columnCount()):
                        item = self.proc_table.item(row,col)
                        rowvals.append(item.text() if item else "")
                    writer.writerow(rowvals)
            QtWidgets.QMessageBox.information(self,"Exported",f"CSV saved as {filename}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self,"Export",f"Failed to save CSV: {e}")

    def export_services_csv(self):
        filename = os.path.join(LOG_DIR, f"services_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        try:
            with open(filename,'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                header = [self.services_table.horizontalHeaderItem(i).text() for i in range(self.services_table.columnCount())]
                writer.writerow(header)
                for row in range(self.services_table.rowCount()):
                    rowvals = []
                    for col in range(self.services_table.columnCount()):
                        item = self.services_table.item(row,col)
                        rowvals.append(item.text() if item else "")
                    writer.writerow(rowvals)
            QtWidgets.QMessageBox.information(self,"Exported",f"CSV saved as {filename}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self,"Export",f"Failed to save CSV: {e}")

    def refresh_history_log(self):
        # Keep history light: add top-5 CPU processes snapshot
        try:
            procs = sorted(psutil.process_iter(['pid','name','cpu_percent','memory_percent']),
                           key=lambda p: p.info.get('cpu_percent') or 0, reverse=True)[:5]
            for p in procs:
                row = self.history_table.rowCount()
                self.history_table.insertRow(row)
                self.history_table.setItem(row,0,QtWidgets.QTableWidgetItem(datetime.now().strftime("%H:%M:%S")))
                self.history_table.setItem(row,1,QtWidgets.QTableWidgetItem(str(p.info.get('pid'))))
                self.history_table.setItem(row,2,QtWidgets.QTableWidgetItem(str(p.info.get('name'))))
                self.history_table.setItem(row,3,QtWidgets.QTableWidgetItem(str(p.info.get('cpu_percent'))))
                self.history_table.setItem(row,4,QtWidgets.QTableWidgetItem(str(p.info.get('memory_percent'))))
                self.history_table.setItem(row,5,QtWidgets.QTableWidgetItem("0"))
            # Keep history table to a reasonable length
            if self.history_table.rowCount() > 500:
                self.history_table.removeRow(0)
        except Exception:
            pass

    def update_gpu_label(self):
        if not GPU_AVAILABLE:
            self.gpu_label.setText("GPU info not available")
            return
        gpu_info = []
        try:
            for gpu in GPUtil.getGPUs():
                gpu_info.append(f"GPU {gpu.id} ({gpu.name}): {gpu.load*100:.2f}% | VRAM used: {gpu.memoryUsed:.0f}/{gpu.memoryTotal:.0f} MB")
        except Exception:
            gpu_info = ["GPU info not available"]
        self.gpu_label.setText("\n".join(gpu_info))

# ---------------------- Run App ----------------------
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = TaskManager()
    window.show()
    sys.exit(app.exec_())
