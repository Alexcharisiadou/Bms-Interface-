import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont
import threading
import serial
import serial.tools.list_ports
import queue

class BMSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DRT BMS Interface")
        self.root.geometry("1200x700")
        self.root.configure(bg="#2E3B4E")

        # ─── Fonts ─────────────────────────────────────
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(size=16)
        self.label_font = default_font
        self.header_font = default_font.copy()
        self.header_font.configure(size=20, weight="bold")

        # ─── Styles ────────────────────────────────────
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#2E3B4E")
        style.configure("TButton", background="#4CAF50", foreground="white")
        style.map("TButton", background=[("active", "#45A049")])

        style.configure("Purple.TLabelframe", background="#e6ccff",
                        borderwidth=2, relief="groove")
        style.configure("Purple.TLabelframe.Label",
                        background="#e6ccff", foreground="#4b0082")
        style.configure("Purple.TLabel", background="#e6ccff",
                        foreground="black", padding=5)
        style.configure("PurpleHeader.TLabel", background="#e6ccff",
                        foreground="#4b0082", padding=5)

        # ─── Data storage ──────────────────────────────
        # -1 = invalid / no reading yet
        self.VoltageList = [[-1.0]*12 for _ in range(12)]
        self.TempsList   = [[-1]*10   for _ in range(12)]

        # thread-safe queue for incoming serial lines
        self.serial_queue = queue.Queue()

        self.ser = None

        # ─── Notebook & tabs ──────────────────────────
        nb = ttk.Notebook(self.root)
        nb.pack(expand=True, fill="both", padx=20, pady=20)

        self.tab1 = ttk.Frame(nb); nb.add(self.tab1, text="Cell Details")
        self.tab2 = ttk.Frame(nb); nb.add(self.tab2, text="Summary & Control")

        self._create_tab1()
        self._create_tab2()

        # ─── Serial reader thread ──────────────────────
        self.serial_thread = threading.Thread(
            target=self._serial_reader_loop, daemon=True)
        self.serial_thread.start()

        # ─── Start periodic GUI update ────────────────
        self.root.after(500, self._process_serial_queue)
        self.root.after(1000, self._update_gui)

    def _create_tab1(self):
        # Temperatures grid
        tf = ttk.LabelFrame(self.tab1, text="Temperatures",
                            style="Purple.TLabelframe", padding=10)
        tf.pack(side=tk.TOP, fill="both", expand=True, padx=10, pady=10)

        self.tab1_temps = []
        # headers
        for col in range(10):
            hdr = ttk.Label(tf, text=f"Cell {col+1}",
                            style="PurpleHeader.TLabel", font=self.header_font)
            hdr.grid(row=0, column=col, padx=5, pady=5)
        # value labels
        for row in range(12):
            row_lbls = []
            for col in range(10):
                lbl = ttk.Label(tf, text="-1 °C",
                                style="Purple.TLabel", font=self.label_font)
                lbl.grid(row=row+1, column=col, padx=5, pady=5)
                row_lbls.append(lbl)
            self.tab1_temps.append(row_lbls)

        # Voltages grid
        vf = ttk.LabelFrame(self.tab1, text="Voltages",
                            style="Purple.TLabelframe", padding=10)
        vf.pack(side=tk.TOP, fill="both", expand=True, padx=10, pady=10)

        self.tab1_voltages = []
        for col in range(12):
            hdr = ttk.Label(vf, text=f"Cell {col+1}",
                            style="PurpleHeader.TLabel", font=self.header_font)
            hdr.grid(row=0, column=col, padx=5, pady=5)
        for row in range(12):
            row_lbls = []
            for col in range(12):
                lbl = ttk.Label(vf, text="-1 V",
                                style="Purple.TLabel", font=self.label_font)
                lbl.grid(row=row+1, column=col, padx=5, pady=5)
                row_lbls.append(lbl)
            self.tab1_voltages.append(row_lbls)

    def _create_tab2(self):
        # Treeview
        tf = ttk.Frame(self.tab2)
        tf.pack(side=tk.TOP, fill="both", expand=True, padx=10, pady=10)

        cols = ["Segment"] + [str(i) for i in range(1,13)]
        self.tree = ttk.Treeview(tf, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=80, anchor="center")
        self.tree.pack(expand=True, fill="both", pady=10)

        # Controls
        cf = ttk.Frame(self.tab2)
        cf.pack(side=tk.TOP, pady=10)

        lbl = ttk.Label(cf, text="Set Charging Current (A):", font=self.label_font)
        lbl.grid(row=0, column=0, padx=10, pady=5)
        self.current_entry = ttk.Entry(cf, width=10, font=self.label_font)
        self.current_entry.grid(row=0, column=1, padx=10, pady=5)

        self.charge_btn = ttk.Button(cf, text="Start Charge",
                                     command=self._start_charge)
        self.charge_btn.grid(row=0, column=2, padx=10, pady=5)

        # Port selection
        self.port_var = tk.StringVar()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        if not ports: ports = ["<no ports>"]
        self.port_cb = ttk.Combobox(cf, textvariable=self.port_var,
                                    values=ports, state="readonly",
                                    font=self.label_font)
        self.port_cb.grid(row=0, column=3, padx=10, pady=5)

        self.connect_btn = ttk.Button(cf, text="Connect to BMS",
                                      command=self._connect_to_bms)
        self.connect_btn.grid(row=0, column=4, padx=10, pady=5)

        self.status_lbl = ttk.Label(cf, text="Status: Disconnected",
                                    foreground="#FF5733", font=self.label_font)
        self.status_lbl.grid(row=1, column=0, columnspan=5, pady=10)

    def _connect_to_bms(self):
        port = self.port_var.get()
        if port == "<no ports>":
            messagebox.showwarning("No Port", "No serial ports available!")
            return
        try:
            self.ser = serial.Serial(port, baudrate=115200, timeout=0.1)
            # handshake
            self.ser.write(b"HELLO\n")
            self.status_lbl.config(text="Status: Connecting...", foreground="#FFA500")
        except serial.SerialException as e:
            messagebox.showerror("Serial Error", str(e))
            return

    def _start_charge(self):
        if not self.ser or not self.ser.is_open:
            messagebox.showwarning("Not Connected", "Please connect first.")
            return
        try:
            c = float(self.current_entry.get())
            cmd = f"C,{c:.2f}\n".encode()
            self.ser.write(cmd)
        except ValueError:
            messagebox.showerror("Invalid", "Enter a numeric current.")

    def _serial_reader_loop(self):
        """Continuously read lines and enqueue them."""
        while True:
            if self.ser and self.ser.in_waiting:
                try:
                    line = self.ser.readline().decode('ascii', errors='ignore').strip()
                    if line:
                        self.serial_queue.put(line)
                except Exception:
                    pass

    def _process_serial_queue(self):
        """Handle all queued serial lines."""
        while not self.serial_queue.empty():
            line = self.serial_queue.get_nowait()
            # handshake ack?
            if line == "HELLO_ACK":
                self.status_lbl.config(text="Status: Connected", foreground="#4CAF50")
                continue
            # parse telemetry
            parts = line.split(",")
            if len(parts) == 4:
                typ, seg_s, cell_s, val_s = parts
                try:
                    seg = int(seg_s)-1
                    cell = int(cell_s)-1
                    if typ == "V" and 0 <= seg < 12 and 0 <= cell < 12:
                        self.VoltageList[seg][cell] = float(val_s)
                    elif typ == "T" and 0 <= seg < 12 and 0 <= cell < 10:
                        self.TempsList[seg][cell] = int(val_s)
                except ValueError:
                    pass
        # reschedule
        self.root.after(200, self._process_serial_queue)

    def _update_gui(self):
        """Refresh all labels and the treeview."""
        # Tab1 grids
        for seg in range(12):
            for cell in range(12):
                v = self.VoltageList[seg][cell]
                txt = f"{v:.3f} V" if v >= 0 else "-1 V"
                self.tab1_voltages[seg][cell].config(text=txt)
            for cell in range(10):
                t = self.TempsList[seg][cell]
                txt = f"{t} °C" if t >= 0 else "-1 °C"
                self.tab1_temps[seg][cell].config(text=txt)

        # Summary tree
        self.tree.delete(*self.tree.get_children())
        for seg in range(12):
            row = [f"Segment {seg+1}"] + [
                f"{self.VoltageList[seg][c]:.3f}V" if self.VoltageList[seg][c]>=0 else "-1V"
                for c in range(12)
            ]
            self.tree.insert("", "end", values=row)

        # reschedule
        self.root.after(1000, self._update_gui)

if __name__ == "__main__":
    root = tk.Tk()
    app = BMSApp(root)
    root.mainloop()
