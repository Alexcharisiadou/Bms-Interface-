import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont
import threading
import time
import serial
import serial.tools.list_ports
import queue
from statistics import mean
import os

class BMSApp:
    def __init__(self, root):
        self.root = root

        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(size=16)
        self.header_font = default_font.copy()
        self.header_font.configure(size=20, weight="bold")
        self.label_font = ("Arial", 14)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#2E3B4E")
        style.configure("TLabel", background="#2E3B4E", foreground="white", font=("Arial", 14))
        style.configure("TButton", background="#4CAF50", foreground="white", font=("Arial", 12, "bold"))
        style.map("TButton", background=[("active", "#45A049")])

        style.configure("Purple.TLabelframe", background="#e6ccff", borderwidth=2, relief="groove")
        style.configure("Purple.TLabelframe.Label", background="#e6ccff", foreground="#4b0082",
                        font=("Arial", 14, "bold"))
        style.configure("Purple.TLabel", background="#e6ccff", foreground="black", font=("Arial", 16), padding=3)
        style.configure("PurpleHeader.TLabel", background="#e6ccff", foreground="#4b0082", font=("Arial", 16, "bold"), padding=3)
        style.configure("Purple.Treeview", background="#e6ccff", fieldbackground="#e6ccff", foreground="black", font=("Arial", 12), rowheight=30)

        self.VoltageList = [[-1.0] * 12 for _ in range(12)]
        self.TempsList = [[-1] * 10 for _ in range(12)]
        self.serial_queue = queue.Queue()
        self.ser = None
        self.canDapterIsConnected = False
        self.ts_current = -1.0
        self.charging_current = -1.0
        self.pack_voltage = -1.0
        self.charger_connected = False

        self._create_main_layout()

        threading.Thread(target=self._serial_reader_loop, daemon=True).start()
        self.root.after(500, self._process_serial_queue)
        self.root.after(1000, self._update_gui)

    def _create_main_layout(self):
        notebook = ttk.Notebook(self.root)
        notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        tab1 = ttk.Frame(notebook)
        notebook.add(tab1, text="Temperatures and Voltages")

        left_frame = ttk.Frame(tab1)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        left_frame.grid_rowconfigure(0, weight=3)
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_columnconfigure(1, weight=1)

        temp_frame = ttk.LabelFrame(left_frame, text="Temperatures", style="Purple.TLabelframe", padding=5)
        temp_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        for col in range(10):
            temp_frame.columnconfigure(col, weight=1)
            ttk.Label(temp_frame, text=f"Cell {col + 1}", style="PurpleHeader.TLabel").grid(row=0, column=col, padx=1, pady=1, sticky="nsew")

        self.tab_temps = []
        for row in range(12):
            row_lbls = []
            for col in range(10):
                lbl = ttk.Label(temp_frame, text="-- °C", style="Purple.TLabel", relief="solid", borderwidth=1)
                lbl.grid(row=row + 1, column=col, padx=1, pady=1, sticky="nsew")
                row_lbls.append(lbl)
            self.tab_temps.append(row_lbls)

        volt_frame = ttk.LabelFrame(left_frame, text="Voltages", style="Purple.TLabelframe", padding=5)
        volt_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        for col in range(12):
            volt_frame.columnconfigure(col, weight=1)
            ttk.Label(volt_frame, text=f"Cell {col + 1}", style="PurpleHeader.TLabel").grid(row=0, column=col, padx=2, pady=2, sticky="nsew")

        self.tab_voltages = []
        for row in range(12):
            row_lbls = []
            for col in range(12):
                lbl = ttk.Label(volt_frame, text="-- V", style="Purple.TLabel", relief="solid", borderwidth=1)
                lbl.grid(row=row + 1, column=col, padx=2, pady=2, sticky="nsew")
                row_lbls.append(lbl)
            self.tab_voltages.append(row_lbls)

        controls_frame = ttk.LabelFrame(tab1, text="Controls", style="Purple.TLabelframe", padding=10)
        controls_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

        self.current_entry = ttk.Entry(controls_frame, width=10, font=self.label_font)
        self.current_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(controls_frame, text="Set Charging Current (A):", font=self.label_font).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(controls_frame, text="Start Charge", command=self._start_charge).grid(row=0, column=2, padx=5, pady=5)

        self.port_entry = ttk.Entry(controls_frame, width=15, font=self.label_font)
        self.port_entry.grid(row=1, column=1, padx=5, pady=5)
        self.port_entry.insert(0, "COM3")

        ttk.Label(controls_frame, text="Enter COM Port:", font=self.label_font).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(controls_frame, text="Connect", command=self._connect_manual).grid(row=1, column=2, padx=5, pady=5)

        self.status_lbl = ttk.Label(controls_frame, text="Status: Disconnected", foreground="#FF5733", font=self.label_font)
        self.status_lbl.grid(row=2, column=0, columnspan=3, pady=10)

        self.ts_current_label = ttk.Label(controls_frame, text="TS Current: -- A", font=self.label_font)
        self.ts_current_label.grid(row=3, column=0, columnspan=1, padx=5, pady=5)

        self.charge_current_label = ttk.Label(controls_frame, text="Charging Current : -- A", font=self.label_font)
        self.charge_current_label.grid(row=4, column=0, padx=5, pady=5)

        self.pack_voltage_label = ttk.Label(controls_frame, text="Pack Voltage : -- V", font=self.label_font)
        self.pack_voltage_label.grid(row=4, column=1, padx=5, pady=5)

        self.charger_status_label = ttk.Label(controls_frame, text="Charger not connected", font=self.label_font)
        self.charger_status_label.grid(row=4, column=2, padx=5, pady=5)

        logo_path = "DRT_Logo_Purple.png"
        if os.path.exists(logo_path):
            logo_img = tk.PhotoImage(file=logo_path)
            logo_label = ttk.Label(controls_frame, image=logo_img, background="#2E3B4E", borderwidth=0)
            logo_label.image = logo_img
            logo_label.grid(row=3, column=3, padx=10, pady=10)

        tab2 = ttk.Frame(notebook)
        notebook.add(tab2, text="Segments Summary")

        tree_frame = ttk.LabelFrame(tab2, text="Segments Summary", style="Purple.TLabelframe", padding=10)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=10)

        cols = ["Segment"] + [str(i) for i in range(1, 13)]
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", style="Purple.Treeview")
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=80, anchor="center")
        tree_scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=tree_scroll_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        notebook.grid_rowconfigure(0, weight=1)
        notebook.grid_columnconfigure(0, weight=1)
        tab1.grid_rowconfigure(0, weight=3)
        tab1.grid_rowconfigure(1, weight=1)
        tab1.grid_columnconfigure(0, weight=1)
        tab1.grid_columnconfigure(1, weight=1)
        tab2.grid_rowconfigure(0, weight=1)
        tab2.grid_columnconfigure(0, weight=1)

    def _connect_manual(self):
        port = self.port_entry.get().strip()
        try:
            self.ser = serial.Serial(port, 115200, timeout=0.1)
            if self.ser.is_open:
                self.status_lbl.config(text=f"Connected to {port}", foreground="limegreen")
                self.canDapterIsConnected = True
                self.ser.write(b"HELLO\n")
        except Exception as e:
            self.status_lbl.config(text="Connection Failed", foreground="red")
            messagebox.showerror("Serial Error", str(e))

    def _serial_reader_loop(self):
        while True:
            if self.canDapterIsConnected and self.ser and self.ser.in_waiting:
                try:
                    line = self.ser.readline().decode('ascii', errors='ignore').strip()
                    if line:
                        self.serial_queue.put(line)
                except Exception:
                    pass
            time.sleep(0.05)

    def _process_serial_queue(self):
        while not self.serial_queue.empty():
            line = self.serial_queue.get_nowait()
            parts = line.split(",")
            if len(parts) == 4:
                typ, seg_s, cell_s, val_s = parts
                try:
                    seg = int(seg_s) - 1
                    cell = int(cell_s) - 1
                    if typ == "V" and 0 <= seg < 12 and 0 <= cell < 12:
                        self.VoltageList[seg][cell] = float(val_s)
                    elif typ == "T" and 0 <= seg < 12 and 0 <= cell < 10:
                        self.TempsList[seg][cell] = int(val_s)
                    elif typ == "I":
                        self.ts_current = float(val_s)
                    elif typ == "C":
                        self.charging_current = float(val_s)
                    elif typ == "P":
                        self.pack_voltage = float(val_s)
                    elif typ == "S":
                        self.charger_connected = val_s == "1"
                except ValueError:
                    pass
        self.root.after(200, self._process_serial_queue)

    def _update_gui(self):
        for seg in range(12):
            volt_values = self.VoltageList[seg]
            avg_voltage = mean([v for v in volt_values if v >= 0]) if any(v >= 0 for v in volt_values) else None
            for cell in range(12):
                v = self.VoltageList[seg][cell]
                txt = f"{v:.3f} V" if v >= 0 else "-- V"
                color = "black"
                if v >= 0:
                    if avg_voltage and abs(v - avg_voltage) > 0.1:
                        color = "orange"
                    if v < 3.52 or v > 4.09:
                        color = "red"
                self.tab_voltages[seg][cell].config(text=txt, foreground=color)
            for cell in range(10):
                t = self.TempsList[seg][cell]
                txt = f"{t} °C" if t >= 0 else "-- °C"
                color = "red" if t >= 0 and t < 59 else "black"
                self.tab_temps[seg][cell].config(text=txt, foreground=color)

        self.tree.delete(*self.tree.get_children())
        for seg in range(12):
            row = [f"Segment {seg + 1}"] + [f"{self.VoltageList[seg][c]:.3f}V" if self.VoltageList[seg][c] >= 0 else "--V" for c in range(12)]
            self.tree.insert("", "end", values=row)

        if self.ts_current >= 0:
            color = "red" if self.ts_current > 225.0 else "black"
            self.ts_current_label.config(text=f"TS Current: {self.ts_current:.2f} A", foreground=color)

        if self.charging_current >= 0:
            self.charge_current_label.config(text=f"Charging Current : {self.charging_current:.1f} A")

        if self.pack_voltage >= 0:
            self.pack_voltage_label.config(text=f"Pack Voltage : {self.pack_voltage:.1f} V")

        self.charger_status_label.config(
            text="Charger connected" if self.charger_connected else "Charger not connected"
        )

        self.root.after(1000, self._update_gui)

    def _start_charge(self):
        if not self.ser or not self.ser.is_open:
            messagebox.showwarning("Not Connected", "Please connect first.")
            return
        try:
            c = float(self.current_entry.get())
            if not (0 <= c <= 10):
                raise ValueError
            cmd = f"C,{c:.2f}\n".encode()
            self.ser.write(cmd)
            messagebox.showinfo("Charging", f"Charging started with {c:.2f}A")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid current (0-10 A).")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("DRT BMS Interface")
    root.state('zoomed')
    root.configure(bg="#2E3B4E")
    app = BMSApp(root)
    root.mainloop()
