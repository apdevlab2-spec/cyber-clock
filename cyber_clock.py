import csv
import math
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import serial
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from serial.tools import list_ports


class CyberClock:

    def __init__(self, root):
        self.root = root
        self.root.title("CYBER PUNK CLOCK v1.8")
        self.window_width = 550
        self.window_height = 430
        self.root.configure(bg="#0b0c10")  # 純黑背景
        self.always_on_top = True
        self.root.attributes("-topmost", True)
        self.flip_expanded = False
        self.hide_after_id = None
        self.compact_mode = True
        self.tab_hide_after_id = None
        self.window_anim_id = None
        self.settings_path = self._get_settings_path()
        self.settings = self.load_settings()
        self.cmd_csv_path = os.path.join(os.path.dirname(self.settings_path), "CMD.csv")
        self.cmd_presets = self.load_cmd_presets()
        self.cmd_preset_index = -1
        self.com_serial = None
        self.com_data_queue = queue.Queue()
        self.com_restore_geometry = None
        self.renter_active = False
        self.renter_after_id = None
        self.renter_cmd_bytes = None
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.screen_resolution = (screen_w, screen_h)
        startup_x = int(self.settings.get("startup_x", 100))
        startup_y = int(self.settings.get("startup_y", 100))
        self.root.geometry(f"{self.window_width}x{self.window_height}+{startup_x}+{startup_y}")

        # --- 科技風色彩設定 (Cyberpunk Style) ---
        self.bg_dark = "#0b0c10"
        self.bg_card = "#1f2833"
        self.cyan_neon = "#66fcf1"
        self.text_gray = "#c5c6c7"
        self.orange_neon = "#ff4500"

        # 鬧鐘與碼錶變數
        self.alarm_time = None
        self.stopwatch_running = False
        self.stopwatch_start_time = 0
        self.stopwatch_elapsed = 0
        self.countdown_running = False
        self.countdown_total = 0.0
        self.countdown_remaining = 0.0
        self.countdown_start_time = 0.0

        # --- 【核心黑科技】拔掉作業系統預設標題列，改用自訂全黑標題列 ---
        self.root.overrideredirect(True)  # 拔掉 Windows 內建白邊框

        # 手工客製化全黑標題列
        self.title_bar = tk.Frame(root, bg="#000000", height=30, bd=0)
        self.title_bar.pack(fill="x", side="top")

        # 標題文字
        self.title_label = tk.Label(
            self.title_bar,
            text="  CYBER PUNK CLOCK v1.8",
            fg="#66fcf1",
            bg="#000000",
            font=("Consolas", 10, "bold"),
        )
        self.title_label.pack(side="left", padx=6)

        # 置頂切換按鈕 [📌]
        self.pin_button = tk.Button(
            self.title_bar,
            text=" 📌 ",
            fg=self.cyan_neon,
            bg="#000000",
            activebackground=self.cyan_neon,
            activeforeground="#000000",
            bd=0,
            font=("Consolas", 11, "bold"),
            command=self.toggle_topmost,
            cursor="hand2",
        )
        self.pin_button.pack(side="right", fill="y", padx=5)

        # 仿科技感關閉按鈕 [X]
        self.close_button = tk.Button(
            self.title_bar,
            text=" ✕ ",
            fg=self.orange_neon,
            bg="#000000",
            activebackground=self.orange_neon,
            activeforeground="#000000",
            bd=0,
            font=("Consolas", 12, "bold"),
            command=self.close_app,
            cursor="hand2",
        )
        self.close_button.pack(side="right", fill="y", padx=5)

        # 讓無邊框視窗也能用滑鼠拖曳移動位置
        self.title_bar.bind("<Button-1>", self.get_pos)
        self.title_bar.bind("<B1-Motion>", self.move_window)
        self.title_label.bind("<Button-1>", self.get_pos)
        self.title_label.bind("<B1-Motion>", self.move_window)

        # --- 1. 置頂大時鐘 ---
        self.time_label = tk.Label(
            root,
            text="00:00:00",
            font=("Consolas", 42, "bold"),
            fg=self.cyan_neon,
            bg=self.bg_dark,
        )
        self.time_label.pack(pady=(20, 0))

        self.date_label = tk.Label(
            root,
            text="2026-09-11",
            font=("Consolas", 14, "bold"),
            fg=self.text_gray,
            bg=self.bg_dark,
            anchor="e",
        )
        self.date_label.pack(anchor="e", padx=42, pady=(0, 10))

        # --- 2. 科技風分頁控制 ---
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "TNotebook", background=self.bg_dark, borderwidth=0, padding=0
        )
        style.configure(
            "TNotebook.Tab",
            background=self.bg_card,
            foreground=self.text_gray,
            font=("Microsoft JhengHei", 11, "bold"),
            padding=[10, 5],
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", self.cyan_neon)],
            foreground=[("selected", self.bg_dark)],
        )

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=15, ipadx=15, pady=(38, 10))
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        self.tab_alarm = tk.Frame(self.notebook, bg=self.bg_card)
        self.tab_stopwatch = tk.Frame(self.notebook, bg=self.bg_card)
        self.tab_note = tk.Frame(self.notebook, bg=self.bg_card)
        self.tab_settings = tk.Frame(self.notebook, bg=self.bg_card)
        self.tab_com = tk.Frame(self.notebook, bg=self.bg_card)

        self.notebook.add(self.tab_alarm, text=" 🔔 系統鬧鐘 ")
        self.notebook.add(self.tab_stopwatch, text=" ⏱️ 量子碼錶 ")
        self.notebook.add(self.tab_note, text=" 📝 Note ")
        self.notebook.add(self.tab_com, text=" 🔌 COM ")
        self.notebook.add(self.tab_settings, text=" ⚙️ 設定 ")

        # 佈局分頁
        self.setup_alarm_ui()
        self.setup_stopwatch_ui()
        self.setup_note_ui()
        self.setup_settings_ui()
        self.setup_com_ui()

        # 啟動後依設定時間淡入收合；其餘情況在鬧鐘 tab 會依設定時間自動收起
        startup_delay = int(self.settings.get("startup_delay_ms", 100))
        self.root.after(startup_delay, self.set_compact_view)

        # 啟動系統即時更新
        self.update_system()

    def _get_settings_path(self):
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, "set.csv")

    def _get_note_path(self):
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, "Note.txt")

    def load_cmd_presets(self):
        defaults = ["?", "16K_adc 3", "16K_fft"]
        if not os.path.exists(self.cmd_csv_path):
            try:
                with open(self.cmd_csv_path, "w", encoding="utf-8", newline="") as cmd_file:
                    cmd_file.write("\n".join(defaults) + "\n")
            except OSError:
                return defaults

        try:
            with open(self.cmd_csv_path, "r", encoding="utf-8-sig", newline="") as cmd_file:
                return [
                    line.rstrip("\r\n")
                    for line in cmd_file
                    if line.rstrip("\r\n").strip()
                ]
        except OSError:
            return defaults

    def load_settings(self):
        defaults = {
            "startup_delay_ms": 100,
            "alarm_hide_ms": 10000,
            "startup_x": 100,
            "startup_y": 100,
            "com_port": "",
        }
        if not os.path.exists(self.settings_path):
            self.save_settings(defaults)
            return defaults

        try:
            with open(self.settings_path, "r", newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)
                if not rows:
                    return defaults
                values = rows[0]
                return {
                    "startup_delay_ms": int(float(values.get("startup_delay_ms", defaults["startup_delay_ms"]))),
                    "alarm_hide_ms": int(float(values.get("alarm_hide_ms", defaults["alarm_hide_ms"]))),
                    "startup_x": int(float(values.get("startup_x", defaults["startup_x"]))),
                    "startup_y": int(float(values.get("startup_y", defaults["startup_y"]))),
                    "com_port": values.get("com_port") or defaults["com_port"],
                }
        except Exception:
            return defaults

    def save_settings(self, values=None):
        if values is None:
            values = self.settings
        data = {
            "startup_delay_ms": int(values.get("startup_delay_ms", 100)),
            "alarm_hide_ms": int(values.get("alarm_hide_ms", 10000)),
            "startup_x": int(values.get("startup_x", 100)),
            "startup_y": int(values.get("startup_y", 100)),
            "com_port": str(
                values.get("com_port", getattr(self, "settings", {}).get("com_port", ""))
            ),
        }
        with open(self.settings_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(
                csvfile,
                fieldnames=[
                    "startup_delay_ms",
                    "alarm_hide_ms",
                    "startup_x",
                    "startup_y",
                    "com_port",
                ],
            )
            writer.writeheader()
            writer.writerow(data)
        self.settings = data
        return data


    # --- 拖曳無邊框視窗的邏輯功能 ---
    def get_pos(self, event):
        self.xwin = event.x
        self.ywin = event.y

    def move_window(self, event):
        x = event.x_root - self.xwin
        y = event.y_root - self.ywin
        self.root.geometry(f"+{x}+{y}")

    def toggle_topmost(self):
        self.always_on_top = not self.always_on_top
        self.root.attributes("-topmost", self.always_on_top)

        if self.always_on_top:
            self.pin_button.config(fg=self.cyan_neon, activeforeground="#000000")
        else:
            self.pin_button.config(fg=self.text_gray, activeforeground="#000000")

    def _cancel_window_animation(self):
        if self.window_anim_id is not None:
            self.root.after_cancel(self.window_anim_id)
            self.window_anim_id = None

    def _animate_window(self, target_height, target_notebook_height, step=10, delay=15):
        current_height = self.root.winfo_height()
        current_tab_height = self.notebook.winfo_height()

        if current_height != target_height:
            if target_height > current_height:
                next_height = min(current_height + step, target_height)
            else:
                next_height = max(current_height - step, target_height)
            self.root.geometry(f"{self.window_width}x{next_height}")

        if current_tab_height != target_notebook_height:
            if target_notebook_height > current_tab_height:
                next_tab_height = min(current_tab_height + step * 2, target_notebook_height)
            else:
                next_tab_height = max(current_tab_height - step * 2, target_notebook_height)
            self.notebook.configure(height=next_tab_height)

        if current_height != target_height or current_tab_height != target_notebook_height:
            self.window_anim_id = self.root.after(
                delay,
                lambda: self._animate_window(
                    target_height, target_notebook_height, step, delay
                ),
            )

    def set_compact_view(self):
        self.compact_mode = True
        self._cancel_window_animation()
        self.notebook.pack_forget()
        self.notebook.pack(fill="x", padx=15, pady=(0, 0))
        self._animate_window(195, 1, step=12, delay=15)

    def set_expanded_view(self, target_height=520):
        self.compact_mode = False
        self._cancel_window_animation()
        self.notebook.pack_forget()
        self.notebook.pack(fill="both", expand=True, padx=15, ipadx=15, pady=10)
        self._animate_window(target_height, target_height - 260, step=12, delay=15)

    def on_tab_changed(self, event=None):
        selected = self.notebook.index(self.notebook.select())
        com_tab_index = self.notebook.index(self.tab_com)
        if selected != com_tab_index and self.com_restore_geometry is not None:
            width, x, y = self.com_restore_geometry
            self.window_width = width
            self.root.geometry(f"{width}x{self.root.winfo_height()}+{x}+{y}")
            self.com_restore_geometry = None

        if selected == 0:
            self.set_expanded_view()
            self.start_tab_hide_timer(self.settings.get("alarm_hide_ms", 10000))
        else:
            if selected == com_tab_index:
                target_height = 1020
                current_x, current_y = self.root.winfo_x(), self.root.winfo_y()
                if self.com_restore_geometry is None:
                    self.com_restore_geometry = (
                        self.window_width,
                        current_x,
                        current_y,
                    )
                    self.window_width += 800
                    target_x = max(0, current_x - 800)
                    target_y = (
                        0
                        if current_y + target_height > self.screen_resolution[1]
                        else current_y
                    )
                    self.root.geometry(
                        f"{self.window_width}x{self.root.winfo_height()}+{target_x}+{target_y}"
                    )
                self.set_expanded_view(target_height)
            else:
                self.set_expanded_view()
            if self.tab_hide_after_id is not None:
                self.root.after_cancel(self.tab_hide_after_id)
                self.tab_hide_after_id = None

    def setup_note_ui(self):
        note_frame = tk.Frame(self.tab_note, bg=self.bg_card)
        note_frame.pack(fill="both", expand=True, padx=12, pady=(16, 12))

        self.note_text = tk.Text(
            note_frame,
            wrap="none",
            bg="#2d2d2d",
            fg=self.text_gray,
            insertbackground=self.cyan_neon,
            selectbackground=self.cyan_neon,
            selectforeground=self.bg_dark,
            font=("Microsoft JhengHei", 11),
            undo=True,
        )
        self.note_text.pack(side="left", fill="both", expand=True)

        self.note_v_scroll = tk.Scrollbar(note_frame, orient="vertical", command=self.note_text.yview)
        self.note_v_scroll.pack(side="right", fill="y")
        self.note_h_scroll = tk.Scrollbar(note_frame, orient="horizontal", command=self.note_text.xview)
        self.note_h_scroll.pack(side="bottom", fill="x")
        self.note_text.configure(yscrollcommand=self.note_v_scroll.set, xscrollcommand=self.note_h_scroll.set)

        self.note_save_btn = tk.Button(
            self.tab_note,
            text="SAVE NOTE",
            font=("Consolas", 10, "bold"),
            bg=self.bg_dark,
            fg=self.cyan_neon,
            activebackground=self.cyan_neon,
            activeforeground=self.bg_dark,
            bd=1,
            relief="solid",
            command=self.save_note,
        )
        self.note_save_btn.pack(pady=(0, 10))

        self.note_text.bind("<FocusOut>", lambda event: self.save_note())
        self.load_note()

    def setup_com_ui(self):
        style = ttk.Style(self.root)
        style.element_create("COM.border", "from", "clam", "Labelframe.border")
        style.layout("COM.TLabelframe", [("COM.border", {"sticky": "nswe"})])
        style.configure(
            "COM.TLabelframe",
            background=self.bg_card,
            bordercolor="#ffff00",
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "COM.TLabelframe.Label",
            background=self.bg_card,
            foreground=self.cyan_neon,
            font=("Consolas", 10, "bold"),
        )

        self.com_group = ttk.LabelFrame(
            self.tab_com,
            text="COM",
            labelanchor="nw",
            style="COM.TLabelframe",
        )
        self.com_group.place(x=12, y=12, width=260, height=360)

        self.com_port_frame = tk.Frame(self.com_group, bg=self.bg_card)
        self.com_port_frame.pack(side="left", anchor="nw", padx=(12, 4), pady=8)

        tk.Label(
            self.com_port_frame,
            text="COM 埠",
            font=("Consolas", 11, "bold"),
            fg=self.cyan_neon,
            bg=self.bg_card,
        ).grid(row=0, column=0, sticky="w")

        self.com_port_combo = ttk.Combobox(
            self.com_port_frame,
            state="readonly",
            width=24,
            postcommand=self.refresh_com_ports,
        )
        self.com_port_combo.grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.com_port_combo.bind("<<ComboboxSelected>>", self.save_com_port_selection)

        self.com_connect_button = tk.Button(
            self.com_port_frame,
            text="連線",
            font=("Microsoft JhengHei", 9, "bold"),
            bg=self.bg_dark,
            fg=self.cyan_neon,
            activebackground=self.cyan_neon,
            activeforeground=self.bg_dark,
            command=self.connect_com,
        )
        self.com_connect_button.grid(row=3, column=0, sticky="w", pady=(4, 0))

        self.com_status_label = tk.Label(
            self.com_port_frame,
            text="",
            font=("Microsoft JhengHei", 9),
            fg=self.text_gray,
            bg=self.bg_card,
        )
        self.com_status_label.grid(row=2, column=0, sticky="w", pady=(2, 0))

        self.com_receive_group = ttk.LabelFrame(
            self.tab_com,
            text="Edit1 400x300",
            labelanchor="nw",
            style="COM.TLabelframe",
        )
        self.com_receive_group.place(x=282, y=12, width=444, height=360)
        self.com_receive_text = tk.Text(
            self.com_receive_group,
            width=1,
            height=1,
            bg="#101820",
            fg=self.cyan_neon,
            insertbackground=self.cyan_neon,
            font=("Consolas", 9),
            wrap="none",
        )
        self.com_receive_text.place(x=8, y=20, width=400, height=300)

        self.com_receive_v_scroll = tk.Scrollbar(
            self.com_receive_group,
            orient="vertical",
            bg="#424242",
            activebackground="#606060",
            troughcolor="#202020",
            bd=0,
            highlightthickness=0,
            relief="flat",
            command=self.com_receive_text.yview,
        )
        self.com_receive_v_scroll.place(x=410, y=20, width=16, height=300)

        self.com_receive_h_scroll = tk.Scrollbar(
            self.com_receive_group,
            orient="horizontal",
            bg="#424242",
            activebackground="#606060",
            troughcolor="#202020",
            bd=0,
            highlightthickness=0,
            relief="flat",
            command=self.com_receive_text.xview,
        )
        self.com_receive_h_scroll.place(x=8, y=320, width=400, height=16)

        self.com_receive_text.configure(
            xscrollcommand=self.com_receive_h_scroll.set,
            yscrollcommand=self.com_receive_v_scroll.set,
        )

        self.cmd_group = ttk.LabelFrame(
            self.tab_com,
            text="CMD",
            labelanchor="nw",
            style="COM.TLabelframe",
        )
        self.cmd_group.place(x=736, y=12, width=240, height=360)
        self.cmd_text = tk.Text(
            self.cmd_group,
            width=1,
            height=1,
            bg="#101820",
            fg=self.cyan_neon,
            insertbackground=self.cyan_neon,
            font=("Consolas", 9),
            wrap="none",
        )
        self.cmd_text.place(x=8, y=20, width=200, height=100)
        self.cmd_enter_button = tk.Button(
            self.cmd_group,
            text="ENTER",
            underline=0,
            font=("Consolas", 9, "bold"),
            bg=self.bg_dark,
            fg=self.cyan_neon,
            activebackground=self.cyan_neon,
            activeforeground=self.bg_dark,
            command=self.send_cmd,
            state="disabled",
        )
        self.cmd_enter_button.place(x=8, y=128, width=84, height=28)
        self.renter_button = tk.Button(
            self.cmd_group,
            text="RENTER OFF",
            font=("Consolas", 8, "bold"),
            bg=self.bg_dark,
            fg=self.text_gray,
            activebackground=self.cyan_neon,
            activeforeground=self.bg_dark,
            command=self.toggle_renter,
            state="disabled",
        )
        self.renter_button.place(x=8, y=164, width=112, height=28)
        self.cmd_clear_button = tk.Button(
            self.cmd_group,
            text="C",
            font=("Consolas", 9, "bold"),
            bg=self.bg_dark,
            fg=self.cyan_neon,
            activebackground=self.cyan_neon,
            activeforeground=self.bg_dark,
            command=self.clear_receive_text,
        )
        self.cmd_clear_button.place(x=100, y=128, width=28, height=28)
        self.cmd_q_button = tk.Button(
            self.cmd_group,
            text="Q",
            font=("Consolas", 9, "bold"),
            bg=self.bg_dark,
            fg=self.cyan_neon,
            activebackground=self.cyan_neon,
            activeforeground=self.bg_dark,
            command=self.cycle_cmd_preset,
        )
        self.cmd_q_button.place(x=136, y=128, width=28, height=28)
        self.cmd_text_bottom_label = tk.Label(
            self.cmd_group,
            text="Edit2",
            font=("Consolas", 9, "bold"),
            fg="#00ff00",
            bg=self.bg_card,
        )
        self.cmd_text_bottom_label.place(x=8, y=196)
        self.cmd_text_bottom = tk.Text(
            self.cmd_group,
            width=1,
            height=1,
            bg="#101820",
            fg="#ffff00",
            insertbackground=self.cyan_neon,
            font=("Consolas", 9),
            wrap="none",
        )
        self.cmd_text_bottom.place(x=8, y=218, width=200, height=100)

        self.draw_group = ttk.LabelFrame(
            self.tab_com,
            text="Draw 1200x400",
            labelanchor="nw",
            style="COM.TLabelframe",
        )
        self.draw_group.place(x=12, y=390, width=1200, height=400)
        self.draw_rx_buffer = ""
        self.draw_collecting = False
        self.draw_values = []
        self.draw_mode = "adc"
        self.draw_expected_count = 1024
        self.draw_figure = Figure(figsize=(11.8, 3.46), dpi=100, facecolor=self.bg_dark)
        self.draw_axes = self.draw_figure.add_subplot(111)
        self.draw_axes.set_facecolor(self.bg_dark)
        self.draw_axes.set_xlim(1, 1024)
        self.draw_axes.set_ylim(0, 4096)
        self.draw_axes.set_xlabel("X", color=self.text_gray, fontsize=7)
        self.draw_axes.set_ylabel("ADC", color=self.text_gray, fontsize=7)
        self.draw_axes.tick_params(colors=self.text_gray, labelsize=6)
        self.draw_axes.grid(color="#34404a", linewidth=0.5)
        self.draw_line, = self.draw_axes.plot([], [], color=self.cyan_neon, linewidth=0.8)
        self.draw_peak_marker, = self.draw_axes.plot(
            [], [], marker="o", color=self.orange_neon, markersize=5, linestyle="None"
        )
        self.draw_major_peak = None
        self.draw_peak_x_label = None
        self.draw_peak_annotation = self.draw_axes.annotate(
            "",
            xy=(0, 0),
            xytext=(12, -32),
            textcoords="offset points",
            color=self.cyan_neon,
            fontsize=8,
            bbox={"boxstyle": "round,pad=0.25", "fc": self.bg_dark, "ec": self.orange_neon},
            arrowprops={"arrowstyle": "->", "color": self.orange_neon},
        )
        self.draw_peak_annotation.set_visible(False)
        self.draw_figure.tight_layout(pad=1.1)
        self.draw_canvas = FigureCanvasTkAgg(self.draw_figure, master=self.draw_group)
        self.draw_canvas.get_tk_widget().place(x=8, y=20, width=1180, height=346)
        self.draw_canvas.mpl_connect("motion_notify_event", self.on_draw_hover)
        self.update_draw_plot([0] * 1024, "adc")

        self.root.bind_all("<Alt-e>", self.send_cmd)

        self.root.after(50, self.poll_com_data)
        self.refresh_com_ports()

    def connect_com(self):
        port_name = self.com_port_combo.get()
        if not port_name:
            self.com_status_label.config(text="請先選擇 COM 埠")
            return

        try:
            connection = serial.Serial(port_name, 115200, timeout=0.1)
        except serial.SerialException as error:
            self.com_status_label.config(text=f"連線失敗：{error}")
            return

        stop_event = threading.Event()
        self.com_serial = connection
        self.com_stop_event = stop_event
        self.com_port_combo.configure(state="disabled")
        self.com_connect_button.configure(text="中斷連線", command=self.disconnect_com)
        self.cmd_enter_button.configure(state="normal")
        self.renter_button.configure(state="normal")
        self.com_status_label.config(text=f"已連線 {port_name}，baudrate 115200")
        threading.Thread(
            target=self.read_com_data,
            args=(connection, stop_event),
            daemon=True,
        ).start()

    def read_com_data(self, connection, stop_event):
        while not stop_event.is_set():
            try:
                data = connection.read(256)
            except serial.SerialException as error:
                if not stop_event.is_set():
                    self.com_data_queue.put(("error", str(error)))
                return
            if data:
                self.com_data_queue.put(("data", data.decode("utf-8", errors="replace")))

    def poll_com_data(self):
        try:
            while True:
                message_type, content = self.com_data_queue.get_nowait()
                if message_type == "data":
                    self.com_receive_text.insert(tk.END, content)
                    self.com_receive_text.see(tk.END)
                    self.process_draw_data(content)
                else:
                    self.disconnect_com(status=f"接收錯誤：{content}")
        except queue.Empty:
            pass
        self.root.after(50, self.poll_com_data)

    def process_draw_data(self, content):
        self.draw_rx_buffer += content.replace("\r\n", "\n")
        while "\n" in self.draw_rx_buffer:
            line, self.draw_rx_buffer = self.draw_rx_buffer.split("\n", 1)
            line = line.strip()

            marker = line.upper()
            if marker == "250 FFT":
                self.draw_values = []
                self.draw_collecting = True
                self.draw_mode = "250 fft"
                self.draw_expected_count = 128
                continue

            if marker in ("16K ADC", "16K FFT", "128K FFT"):
                self.draw_values = []
                self.draw_collecting = True
                self.draw_mode = (
                    "128k fft"
                    if marker == "128K FFT"
                    else "fft" if marker == "16K FFT" else "adc"
                )
                self.draw_expected_count = (
                    64 if self.draw_mode == "128k fft" else 512 if self.draw_mode == "fft" else 1024
                )
                continue

            marker_parts = marker.split()
            if len(marker_parts) == 2 and marker_parts[0] in ("16K", "128K") and marker_parts[1] in (
                "X1",
                "X10",
                "X100",
            ):
                self.draw_values = []
                self.draw_collecting = True
                self.draw_mode = f"16k {marker_parts[1].lower()}"
                if marker_parts[0] == "128K":
                    self.draw_mode = f"128k {marker_parts[1].lower()}"
                    self.draw_expected_count = 128
                else:
                    self.draw_expected_count = 1024
                continue

            if len(marker_parts) == 2 and marker_parts[0] == "250" and marker_parts[1] in (
                "X1",
                "X10",
                "X100",
            ):
                self.draw_values = []
                self.draw_collecting = True
                self.draw_mode = f"250 {marker_parts[1].lower()}"
                self.draw_expected_count = 256
                continue

            if not self.draw_collecting or not line:
                continue

            try:
                value = float(line)
            except ValueError:
                self.draw_values = []
                self.draw_collecting = False
                continue

            if not math.isfinite(value):
                self.draw_values = []
                self.draw_collecting = False
                continue

            self.draw_values.append(value)
            if len(self.draw_values) == self.draw_expected_count:
                self.update_draw_plot(self.draw_values, self.draw_mode)
                self.draw_values = []
                self.draw_collecting = False

    def update_draw_plot(self, values, mode="adc"):
        if mode in ("fft", "128k fft"):
            frequency_max = 64000 if mode == "128k fft" else 8000
            x_values = [frequency_max * index / (len(values) - 1) for index in range(len(values))]
            y_max = max(values) * 1.1
            self.draw_axes.set_xlim(0, frequency_max)
            self.draw_axes.set_ylim(0, y_max if y_max > 0 else 1)
            self.draw_axes.set_xlabel("Frequency (Hz)", color=self.text_gray, fontsize=7)
            self.draw_axes.set_ylabel("FFT", color=self.text_gray, fontsize=7)
            peak_index = max(range(len(values)), key=values.__getitem__)
            peak_x = x_values[peak_index]
            peak_y = values[peak_index]
            self.draw_major_peak = (peak_x, peak_y)
            self.draw_peak_x_label = "Frequency"
            self.draw_peak_marker.set_data([peak_x], [peak_y])
            self.draw_peak_marker.set_visible(False)
            self.draw_peak_annotation.set_visible(False)
            self.display_mic_sensitivity(peak_y, peak_x)
        elif mode == "250 fft":
            x_values = [125 * index / (len(values) - 1) for index in range(len(values))]
            y_max = max(values) * 1.1
            self.draw_axes.set_xlim(0, 125)
            self.draw_axes.set_ylim(0, y_max if y_max > 0 else 1)
            self.draw_axes.set_xlabel("Frequency (Hz)", color=self.text_gray, fontsize=7)
            self.draw_axes.set_ylabel("FFT", color=self.text_gray, fontsize=7)
            peak_index = max(range(len(values)), key=values.__getitem__)
            peak_x = x_values[peak_index]
            peak_y = values[peak_index]
            self.draw_major_peak = (peak_x, peak_y)
            self.draw_peak_x_label = "Frequency"
            self.draw_peak_marker.set_data([peak_x], [peak_y])
            self.draw_peak_marker.set_visible(False)
            self.draw_peak_annotation.set_visible(False)
        elif mode.startswith(("16k ", "128k ")):
            if mode.startswith("128k "):
                x_values = range(len(values))
                self.draw_axes.set_xlim(0, 128)
            else:
                x_values = range(1, len(values) + 1)
                self.draw_axes.set_xlim(1, 1024)
            self.draw_axes.set_ylim(0, 4096)
            self.draw_axes.set_xlabel("X", color=self.text_gray, fontsize=7)
            self.draw_axes.set_ylabel(f"ADC ({mode})", color=self.text_gray, fontsize=7)
            self.draw_major_peak = None
            self.draw_peak_x_label = None
            self.draw_peak_marker.set_data([], [])
            self.draw_peak_marker.set_visible(False)
            self.draw_peak_annotation.set_visible(False)
        elif mode.startswith("250 "):
            x_values = range(len(values))
            self.draw_axes.set_xlim(0, 256)
            self.draw_axes.set_ylim(0, 4095)
            self.draw_axes.set_xlabel("X", color=self.text_gray, fontsize=7)
            self.draw_axes.set_ylabel(f"ADC ({mode})", color=self.text_gray, fontsize=7)
            peak_index = max(range(len(values)), key=values.__getitem__)
            peak_x = x_values[peak_index]
            peak_y = values[peak_index]
            self.draw_major_peak = (peak_x, peak_y)
            self.draw_peak_x_label = "Sample"
            self.draw_peak_marker.set_data([peak_x], [peak_y])
            self.draw_peak_marker.set_visible(False)
            self.draw_peak_annotation.set_visible(False)
        else:
            x_values = range(1, len(values) + 1)
            self.draw_axes.set_xlim(1, 1024)
            self.draw_axes.set_ylim(0, 4096)
            self.draw_axes.set_xlabel("X", color=self.text_gray, fontsize=7)
            self.draw_axes.set_ylabel("ADC", color=self.text_gray, fontsize=7)
            self.draw_major_peak = None
            self.draw_peak_x_label = None
            self.draw_peak_marker.set_data([], [])
            self.draw_peak_marker.set_visible(False)
            self.draw_peak_annotation.set_visible(False)

        self.draw_line.set_data(x_values, values)
        self.draw_canvas.draw_idle()

    def display_mic_sensitivity(self, voltage_rms, frequency_hz):
        if voltage_rms <= 0:
            result = "MIC sensitivity unavailable: FFT peak is 0 Vrms"
        else:
            reference_pressure_pa = 20e-6 * 10 ** (94 / 20)
            sensitivity_v_per_pa = voltage_rms / reference_pressure_pa
            sensitivity_mv_per_pa = sensitivity_v_per_pa * 1000
            sensitivity_dbv_per_pa = 20 * math.log10(sensitivity_v_per_pa)
            result = (
                f"MIC sensitivity @ {frequency_hz:.2f} Hz, 94 dB SPL: "
                f"{sensitivity_mv_per_pa:.4f} mV/Pa "
                f"({sensitivity_dbv_per_pa:.2f} dBV/Pa)"
            )

        self.com_receive_text.insert(tk.END, f"\n{result}\n")
        self.com_receive_text.see(tk.END)

    def on_draw_hover(self, event):
        if self.draw_major_peak is None or event.inaxes is not self.draw_axes:
            if (
                self.draw_peak_marker.get_visible()
                or self.draw_peak_annotation.get_visible()
            ):
                self.draw_peak_marker.set_visible(False)
                self.draw_peak_annotation.set_visible(False)
                self.draw_canvas.draw_idle()
            return

        peak_x, peak_y = self.draw_major_peak
        peak_pixel_x, peak_pixel_y = self.draw_axes.transData.transform((peak_x, peak_y))
        if math.hypot(event.x - peak_pixel_x, event.y - peak_pixel_y) <= 14:
            self.draw_peak_annotation.xy = (peak_x, peak_y)
            if self.draw_peak_x_label == "Frequency":
                x_description = f"Frequency: {peak_x:.2f} Hz"
            else:
                x_description = f"Sample: {peak_x:g}"
            self.draw_peak_annotation.set_text(
                f"Peak: {peak_y:g}\n{x_description}"
            )
            self.draw_peak_marker.set_visible(True)
            self.draw_peak_annotation.set_visible(True)
        else:
            self.draw_peak_marker.set_visible(False)
            self.draw_peak_annotation.set_visible(False)
        self.draw_canvas.draw_idle()

    def send_cmd(self, event=None):
        if self.notebook.index(self.notebook.select()) != self.notebook.index(self.tab_com):
            return "break"

        connection = self.com_serial
        if connection is None or not connection.is_open:
            self.com_status_label.config(text="尚未連線，CMD 未送出")
            return "break"

        command = self.cmd_text.get("1.0", "end-1c").encode("utf-8") + b"\r\n"
        self.write_com_async(connection, command)
        return "break"

    def toggle_renter(self):
        if self.renter_active:
            self.stop_renter()
            return

        connection = self.com_serial
        if connection is None or not connection.is_open:
            self.com_status_label.config(text="尚未連線，RENTER 未啟動")
            return

        self.renter_cmd_bytes = self.cmd_text.get("1.0", "end-1c").encode("utf-8") + b"\r\n"
        self.renter_active = True
        self.renter_button.configure(text="RENTER ON", fg=self.orange_neon)
        self.write_com_async(connection, self.renter_cmd_bytes)
        self.renter_after_id = self.root.after(1000, self.repeat_renter_command)

    def repeat_renter_command(self):
        self.renter_after_id = None
        connection = self.com_serial
        if (
            not self.renter_active
            or self.renter_cmd_bytes is None
            or connection is None
            or not connection.is_open
        ):
            return

        self.write_com_async(connection, self.renter_cmd_bytes)
        self.renter_after_id = self.root.after(1000, self.repeat_renter_command)

    def stop_renter(self):
        self.renter_active = False
        if self.renter_after_id is not None:
            self.root.after_cancel(self.renter_after_id)
            self.renter_after_id = None
        self.renter_cmd_bytes = None
        self.renter_button.configure(text="RENTER OFF", fg=self.text_gray)

    def write_com_async(self, connection, data):
        threading.Thread(
            target=self.write_com_data,
            args=(connection, data),
            daemon=True,
        ).start()

    def clear_receive_text(self):
        self.com_receive_text.delete("1.0", tk.END)

    def cycle_cmd_preset(self):
        if not self.cmd_presets:
            self.com_status_label.config(text="CMD.csv 沒有可用字串")
            return

        self.cmd_preset_index = (self.cmd_preset_index + 1) % len(self.cmd_presets)
        self.cmd_text.delete("1.0", tk.END)
        self.cmd_text.insert("1.0", self.cmd_presets[self.cmd_preset_index])
        self.cmd_text.mark_set("insert", tk.END)
        self.cmd_text.focus_set()

    def write_com_data(self, connection, data):
        try:
            connection.write(data)
        except serial.SerialException as error:
            if connection is self.com_serial:
                self.com_data_queue.put(("error", str(error)))

    def disconnect_com(self, status="未連線"):
        connection = self.com_serial
        self.com_serial = None
        if connection is not None:
            self.com_stop_event.set()
            connection.close()
        self.com_port_combo.configure(state="readonly")
        self.com_connect_button.configure(text="連線", command=self.connect_com)
        self.cmd_enter_button.configure(state="disabled")
        self.renter_active = False
        if self.renter_after_id is not None:
            self.root.after_cancel(self.renter_after_id)
            self.renter_after_id = None
        self.renter_cmd_bytes = None
        self.renter_button.configure(text="RENTER OFF", fg=self.text_gray, state="disabled")
        self.com_status_label.config(text=status)

    def close_app(self):
        self.disconnect_com()
        self.root.destroy()

    def refresh_com_ports(self):
        ports = [port.device for port in list_ports.comports()]
        selected_port = self.settings.get("com_port") or self.com_port_combo.get()
        self.com_port_combo["values"] = ports

        if selected_port in ports:
            self.com_port_combo.set(selected_port)
        elif ports:
            self.com_port_combo.current(0)
        else:
            self.com_port_combo.set("")

        status = f"找到 {len(ports)} 個可用 COM 埠" if ports else "未找到可用 COM 埠"
        self.com_status_label.config(text=status)

    def save_com_port_selection(self, event=None):
        selected_port = self.com_port_combo.get()
        if selected_port == self.settings.get("com_port", ""):
            return

        values = dict(self.settings)
        values["com_port"] = selected_port
        self.save_settings(values)

    def load_note(self):
        note_path = self._get_note_path()
        if os.path.exists(note_path):
            try:
                with open(note_path, "r", encoding="utf-8-sig") as f:
                    content = f.read()
                self.note_text.delete("1.0", tk.END)
                self.note_text.insert("1.0", content)
            except Exception:
                self.note_text.delete("1.0", tk.END)
        else:
            self.note_text.delete("1.0", tk.END)
            self.save_note()

    def save_note(self):
        note_path = self._get_note_path()
        content = self.note_text.get("1.0", tk.END)
        try:
            with open(note_path, "w", encoding="utf-8") as f:
                f.write(content)
            alt_path = os.path.join(os.path.dirname(note_path), "Note.ap")
            with open(alt_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            messagebox.showerror("ERROR", "Note 儲存失敗，請確認資料夾權限。")

    def setup_settings_ui(self):
        tk.Label(
            self.tab_settings,
            text="[ 系統設定 ]",
            font=("Consolas", 11, "bold"),
            fg=self.cyan_neon,
            bg=self.bg_card,
        ).pack(pady=(20, 10))

        form = tk.Frame(self.tab_settings, bg=self.bg_card)
        form.pack(padx=20, pady=10, fill="x")

        tk.Label(
            form,
            text="啟動後收合 (ms):",
            font=("Consolas", 10),
            fg=self.text_gray,
            bg=self.bg_card,
        ).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=8)
        self.startup_delay_entry = tk.Entry(
            form,
            width=8,
            font=("Consolas", 10, "bold"),
            bg=self.bg_dark,
            fg=self.cyan_neon,
            justify="center",
        )
        self.startup_delay_entry.grid(row=0, column=1, sticky="w")
        self.startup_delay_entry.insert(0, str(self.settings.get("startup_delay_ms", 100)))

        tk.Label(
            form,
            text="鬧鐘自動收合 (ms):",
            font=("Consolas", 10),
            fg=self.text_gray,
            bg=self.bg_card,
        ).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=8)
        self.alarm_hide_entry = tk.Entry(
            form,
            width=8,
            font=("Consolas", 10, "bold"),
            bg=self.bg_dark,
            fg=self.cyan_neon,
            justify="center",
        )
        self.alarm_hide_entry.grid(row=1, column=1, sticky="w")
        self.alarm_hide_entry.insert(0, str(self.settings.get("alarm_hide_ms", 10000)))

        tk.Label(
            form,
            text="開啟位置 X:",
            font=("Consolas", 10),
            fg=self.text_gray,
            bg=self.bg_card,
        ).grid(row=2, column=0, sticky="w", padx=(0, 10), pady=8)
        self.startup_x_entry = tk.Entry(
            form,
            width=8,
            font=("Consolas", 10, "bold"),
            bg=self.bg_dark,
            fg=self.cyan_neon,
            justify="center",
        )
        self.startup_x_entry.grid(row=2, column=1, sticky="w")
        self.startup_x_entry.insert(0, str(self.settings.get("startup_x", 100)))

        tk.Label(
            form,
            text="開啟位置 Y:",
            font=("Consolas", 10),
            fg=self.text_gray,
            bg=self.bg_card,
        ).grid(row=3, column=0, sticky="w", padx=(0, 10), pady=8)
        self.startup_y_entry = tk.Entry(
            form,
            width=8,
            font=("Consolas", 10, "bold"),
            bg=self.bg_dark,
            fg=self.cyan_neon,
            justify="center",
        )
        self.startup_y_entry.grid(row=3, column=1, sticky="w")
        self.startup_y_entry.insert(0, str(self.settings.get("startup_y", 100)))

        self.screen_info_label = tk.Label(
            self.tab_settings,
            text=f"畫面解析度: {self.screen_resolution[0]} x {self.screen_resolution[1]}",
            font=("Consolas", 9, "bold"),
            fg=self.cyan_neon,
            bg=self.bg_card,
        )
        self.screen_info_label.pack(pady=(8, 0))

        self.save_settings_btn = tk.Button(
            self.tab_settings,
            text="SAVE SETTINGS",
            font=("Consolas", 10, "bold"),
            bg=self.bg_dark,
            fg=self.cyan_neon,
            activebackground=self.cyan_neon,
            activeforeground=self.bg_dark,
            bd=1,
            relief="solid",
            command=self.apply_settings,
        )
        self.save_settings_btn.pack(pady=(8, 8))

        self.settings_info_label = tk.Label(
            self.tab_settings,
            text=f"設定檔: {self.settings_path}",
            font=("Consolas", 8),
            fg=self.text_gray,
            bg=self.bg_card,
            justify="left",
            wraplength=350,
        )
        self.settings_info_label.pack(padx=20, pady=(5, 0))

    def apply_settings(self):
        try:
            startup_ms = int(self.startup_delay_entry.get().strip())
            alarm_ms = int(self.alarm_hide_entry.get().strip())
            startup_x = int(self.startup_x_entry.get().strip())
            startup_y = int(self.startup_y_entry.get().strip())
            if startup_ms <= 0 or alarm_ms <= 0:
                raise ValueError
            values = {
                "startup_delay_ms": startup_ms,
                "alarm_hide_ms": alarm_ms,
                "startup_x": startup_x,
                "startup_y": startup_y,
            }
            self.save_settings(values)
            current_width = self.root.winfo_width() or self.window_width
            current_height = self.root.winfo_height() or self.window_height
            self.root.geometry(f"{current_width}x{current_height}+{startup_x}+{startup_y}")
            self.settings_info_label.config(text=f"設定已儲存: {self.settings_path}", fg=self.cyan_neon)
            self.root.after(startup_ms, self.set_compact_view)
            if self.tab_hide_after_id is not None:
                self.root.after_cancel(self.tab_hide_after_id)
            if self.notebook.index(self.notebook.select()) == 0:
                self.start_tab_hide_timer(alarm_ms)
        except Exception:
            messagebox.showerror("ERROR", "請輸入正整數，時間單位為毫秒，X/Y 位置也請輸入整數。")

    def start_tab_hide_timer(self, delay_ms):
        if self.tab_hide_after_id is not None:
            self.root.after_cancel(self.tab_hide_after_id)
        self.tab_hide_after_id = self.root.after(delay_ms, self.auto_hide_tab_panel)

    def auto_hide_tab_panel(self):
        self.set_compact_view()

    def setup_alarm_ui(self):
        tk.Label(
            self.tab_alarm,
            text="[ 輸入指定時間啟動攔截器 ]",
            font=("Consolas", 10),
            fg=self.text_gray,
            bg=self.bg_card,
        ).pack(pady=15)

        input_frame = tk.Frame(self.tab_alarm, bg=self.bg_card)
        input_frame.pack(pady=5)

        self.hour_entry = tk.Entry(
            input_frame,
            width=3,
            font=("Consolas", 18, "bold"),
            justify="center",
            bg=self.bg_dark,
            fg=self.cyan_neon,
            insertbackground=self.cyan_neon,
            bd=1,
        )
        self.hour_entry.grid(row=0, column=0)

        tk.Label(
            input_frame,
            text=":",
            font=("Consolas", 18),
            fg=self.cyan_neon,
            bg=self.bg_card,
        ).grid(row=0, column=1, padx=5)

        self.minute_entry = tk.Entry(
            input_frame,
            width=3,
            font=("Consolas", 18, "bold"),
            justify="center",
            bg=self.bg_dark,
            fg=self.cyan_neon,
            insertbackground=self.cyan_neon,
            bd=1,
        )
        self.minute_entry.grid(row=0, column=2)

        self.alarm_value_label = tk.Label(
            self.tab_alarm,
            text="設定時間: 尚未設定",
            font=("Consolas", 10, "bold"),
            fg=self.text_gray,
            bg=self.bg_card,
        )
        self.alarm_value_label.pack(pady=(8, 0))

        self.btn_set = tk.Button(
            self.tab_alarm,
            text="INITIALIZE ALARM",
            font=("Consolas", 11, "bold"),
            bg=self.bg_dark,
            fg=self.cyan_neon,
            activebackground=self.cyan_neon,
            activeforeground=self.bg_dark,
            bd=1,
            relief="solid",
            command=self.set_alarm,
        )
        self.btn_set.pack(pady=15)

        self.status_label = tk.Label(
            self.tab_alarm,
            text="STATUS: STANDBY",
            font=("Consolas", 10),
            fg=self.text_gray,
            bg=self.bg_card,
        )
        self.status_label.pack(pady=(0, 10))

    def setup_stopwatch_ui(self):
        self.sw_label = tk.Label(
            self.tab_stopwatch,
            text="00:00.00",
            font=("Consolas", 36, "bold"),
            fg=self.text_gray,
            bg=self.bg_card,
        )
        self.sw_label.pack(pady=(20, 8))

        btn_frame = tk.Frame(self.tab_stopwatch, bg=self.bg_card)
        btn_frame.pack(pady=0)

        self.btn_sw_start = tk.Button(
            btn_frame,
            text="START / PAUSE",
            font=("Consolas", 10, "bold"),
            bg=self.bg_dark,
            fg=self.cyan_neon,
            bd=1,
            relief="solid",
            command=self.toggle_stopwatch,
        )
        self.btn_sw_start.grid(row=0, column=0, padx=10, pady=(0, 0))

        self.btn_sw_reset = tk.Button(
            btn_frame,
            text="RESET",
            font=("Consolas", 10, "bold"),
            bg=self.bg_dark,
            fg=self.orange_neon,
            bd=1,
            relief="solid",
            command=self.reset_stopwatch,
        )
        self.btn_sw_reset.grid(row=0, column=1, padx=10, pady=(0, 0))

        self.countdown_label = tk.Label(
            self.tab_stopwatch,
            text="倒數: 00:00.00",
            font=("Consolas", 24, "bold"),
            fg=self.cyan_neon,
            bg=self.bg_card,
        )
        self.countdown_label.pack(pady=(18, 6))

        countdown_frame = tk.Frame(self.tab_stopwatch, bg=self.bg_card)
        countdown_frame.pack(pady=(0, 10))

        self.cd_min_entry = tk.Entry(
            countdown_frame,
            width=3,
            font=("Consolas", 16, "bold"),
            justify="center",
            bg=self.bg_dark,
            fg=self.cyan_neon,
            insertbackground=self.cyan_neon,
        )
        self.cd_min_entry.grid(row=0, column=0, padx=(0, 4))
        self.cd_min_entry.insert(0, "00")

        tk.Label(
            countdown_frame,
            text=":",
            font=("Consolas", 18, "bold"),
            fg=self.cyan_neon,
            bg=self.bg_card,
        ).grid(row=0, column=1, padx=2)

        self.cd_sec_entry = tk.Entry(
            countdown_frame,
            width=3,
            font=("Consolas", 16, "bold"),
            justify="center",
            bg=self.bg_dark,
            fg=self.cyan_neon,
            insertbackground=self.cyan_neon,
        )
        self.cd_sec_entry.grid(row=0, column=2, padx=(2, 8))
        self.cd_sec_entry.insert(0, "10")

        self.btn_cd_set = tk.Button(
            countdown_frame,
            text="SET COUNTDOWN",
            font=("Consolas", 10, "bold"),
            bg=self.bg_dark,
            fg=self.cyan_neon,
            bd=1,
            relief="solid",
            command=self.set_countdown,
        )
        self.btn_cd_set.grid(row=0, column=3, padx=(0, 4))

        self.btn_cd_toggle = tk.Button(
            countdown_frame,
            text="START / PAUSE",
            font=("Consolas", 10, "bold"),
            bg=self.bg_dark,
            fg=self.orange_neon,
            bd=1,
            relief="solid",
            command=self.toggle_countdown,
        )
        self.btn_cd_toggle.grid(row=0, column=4, padx=(4, 0))

    def update_system(self):
        current_time = time.strftime("%H:%M:%S")
        current_date = time.strftime("%Y-%m-%d")
        self.time_label.config(text=current_time)
        self.date_label.config(text=current_date)

        if self.alarm_time:
            now_hm = time.strftime("%H:%M")
            if now_hm == self.alarm_time:
                self.alarm_time = None
                self.status_label.config(
                    text="STATUS: STANDBY", fg=self.text_gray
                )
                messagebox.showinfo("⚠️ SYSTEM ALERT", "時間核心已到達指定錨點！")

        if self.stopwatch_running:
            self.stopwatch_elapsed = time.time() - self.stopwatch_start_time
            self.update_stopwatch_display()

        if self.countdown_running:
            elapsed = time.time() - self.countdown_start_time
            self.countdown_remaining = max(0.0, self.countdown_total - elapsed)
            if self.countdown_remaining <= 0:
                self.countdown_running = False
                self.countdown_remaining = 0.0
                self.countdown_label.config(text="倒數: 00:00.00", fg=self.orange_neon)
                messagebox.showinfo("⚠️ COUNTDOWN ALERT", "倒數計時已完成！")
            else:
                self.update_countdown_display()

        self.root.after(50, self.update_system)

    def set_alarm(self):
        h = self.hour_entry.get().strip()
        m = self.minute_entry.get().strip()

        if (
            not h.isdigit()
            or not m.isdigit()
            or not (0 <= int(h) < 24)
            or not (0 <= int(m) < 60)
        ):
            messagebox.showerror("ERROR", "時間軌道參數錯誤，請輸入正確時分。")
            return

        self.alarm_time = f"{int(h):02d}:{int(m):02d}"
        self.hour_entry.delete(0, tk.END)
        self.minute_entry.delete(0, tk.END)
        self.hour_entry.insert(0, f"{int(h):02d}")
        self.minute_entry.insert(0, f"{int(m):02d}")
        self.alarm_value_label.config(
            text=f"設定時間: {self.alarm_time}", fg=self.cyan_neon
        )
        self.status_label.config(
            text=f"ALARM SET AT [{self.alarm_time}]", fg=self.cyan_neon
        )

    def toggle_stopwatch(self):
        if not self.stopwatch_running:
            self.stopwatch_running = True
            self.stopwatch_start_time = time.time() - self.stopwatch_elapsed
            self.sw_label.config(fg=self.cyan_neon)
        else:
            self.stopwatch_running = False
            self.sw_label.config(fg=self.orange_neon)

    def reset_stopwatch(self):
        self.stopwatch_running = False
        self.stopwatch_elapsed = 0
        self.sw_label.config(text="00:00.00", fg=self.text_gray)

    def update_stopwatch_display(self):
        minutes = int(self.stopwatch_elapsed // 60)
        seconds = int(self.stopwatch_elapsed % 60)
        centiseconds = int((self.stopwatch_elapsed * 100) % 100)
        self.sw_label.config(
            text=f"{minutes:02d}:{seconds:02d}.{centiseconds:02d}"
        )

    def set_countdown(self):
        try:
            minutes = int(self.cd_min_entry.get().strip())
            seconds = int(self.cd_sec_entry.get().strip())
            if minutes < 0 or seconds < 0 or seconds >= 60:
                raise ValueError
            total = minutes * 60 + seconds
            if total <= 0:
                raise ValueError
            self.countdown_total = float(total)
            self.countdown_remaining = float(total)
            self.countdown_running = False
            self.update_countdown_display()
        except Exception:
            messagebox.showerror("ERROR", "請輸入 0~59 秒，或分鐘數為非負整數。")

    def toggle_countdown(self):
        if self.countdown_total <= 0:
            self.set_countdown()
            if self.countdown_total <= 0:
                return
        if not self.countdown_running:
            self.countdown_running = True
            self.countdown_start_time = time.time() - (self.countdown_total - self.countdown_remaining)
            self.countdown_label.config(fg=self.cyan_neon)
        else:
            self.countdown_running = False
            self.countdown_label.config(fg=self.orange_neon)

    def update_countdown_display(self):
        total_ms = int(self.countdown_remaining * 100)
        total_seconds = total_ms // 100
        milliseconds = total_ms % 100
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        self.countdown_label.config(
            text=f"倒數: {minutes:02d}:{seconds:02d}.{milliseconds:02d}",
            fg=self.cyan_neon if self.countdown_running else self.orange_neon,
        )


if __name__ == "__main__":
    root = tk.Tk()
    app = CyberClock(root)
    root.mainloop()
