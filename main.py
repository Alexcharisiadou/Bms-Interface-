import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import random
import serial
from time import sleep


class BMSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DRT BMS Interface")
        self.root.geometry("1200x700")
        self.root.configure(bg="#2E3B4E")  # Dark blue background

        # --------------------------
        # Configure Styles (Purple Theme)
        # --------------------------
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#2E3B4E")
        self.style.configure("TLabel", background="#2E3B4E", foreground="white", font=("Arial", 14))
        self.style.configure("TButton", background="#4CAF50", foreground="white", font=("Arial", 12, "bold"))
        self.style.map("TButton", background=[("active", "#45A049")])

        # Styles for Notebook Tab1 (Grid View)
        self.style.configure("Purple.TLabelframe", background="#e6ccff", borderwidth=2, relief="groove")
        self.style.configure("Purple.TLabelframe.Label", background="#e6ccff", foreground="#4b0082",
                             font=("Arial", 14, "bold"))
        self.style.configure("Purple.TLabel", background="#e6ccff", foreground="black", font=("Arial", 11), padding=5)
        self.style.configure("PurpleHeader.TLabel", background="#e6ccff", foreground="#4b0082",
                             font=("Arial", 12, "bold"), padding=5)

        # --------------------------
        # Data Arrays & Connection Variables
        # --------------------------
        self.VoltageList = [[0.0 for _ in range(12)] for _ in range(12)]  # 12 segments x 12 cells
        self.TempsList = [[0 for _ in range(10)] for _ in range(12)]  # 12 segments x 10 cells
        self.canDapterIsConnected = False
        self.ser = None

        # --------------------------
        # Create Notebook with Two Tabs
        # --------------------------
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill="both", padx=20, pady=20)

        # Tab 1: Detailed Cell View (Grids)
        self.tab1 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab1, text="Cell Details")

        # Tab 2: Summary & Controls (Treeview & Buttons)
        self.tab2 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab2, text="Summary & Control")

        self.create_tab1()
        self.create_tab2()

        # --------------------------
        # Start the Update Thread
        # --------------------------
        self.update_thread = threading.Thread(target=self.update_values, daemon=True)
        self.update_thread.start()

    def create_tab1(self):
        # Tab 1: Two LabelFrames for Temperatures and Voltages

        # Temperature Grid (12 rows x 10 columns)
        self.temp_frame = ttk.LabelFrame(self.tab1, text="Temperatures", style="Purple.TLabelframe", padding=10)
        self.temp_frame.pack(side=tk.TOP, fill="both", expand=True, padx=10, pady=10)

        # Create header row for temperature grid
        self.tab1_temps = [[None for _ in range(10)] for _ in range(12)]
        for col in range(10):
            header = ttk.Label(self.temp_frame, text=f"Cell {col + 1}", style="PurpleHeader.TLabel")
            header.grid(row=0, column=col, padx=5, pady=5)
        for row in range(12):
            for col in range(10):
                lbl = ttk.Label(self.temp_frame, text="-- °C", style="Purple.TLabel")
                lbl.grid(row=row + 1, column=col, padx=5, pady=5)
                self.tab1_temps[row][col] = lbl

        # Voltage Grid (12 rows x 12 columns)
        self.volt_frame = ttk.LabelFrame(self.tab1, text="Voltages", style="Purple.TLabelframe", padding=10)
        self.volt_frame.pack(side=tk.TOP, fill="both", expand=True, padx=10, pady=10)

        self.tab1_voltages = [[None for _ in range(12)] for _ in range(12)]
        for col in range(12):
            header = ttk.Label(self.volt_frame, text=f"Cell {col + 1}", style="PurpleHeader.TLabel")
            header.grid(row=0, column=col, padx=5, pady=5)
        for row in range(12):
            for col in range(12):
                lbl = ttk.Label(self.volt_frame, text="-- V", style="Purple.TLabel")
                lbl.grid(row=row + 1, column=col, padx=5, pady=5)
                self.tab1_voltages[row][col] = lbl

    def create_tab2(self):
        # Tab 2: Treeview for Voltage Segments and Controls

        # Treeview Frame
        self.tree_frame = ttk.Frame(self.tab2)
        self.tree_frame.pack(side=tk.TOP, fill="both", expand=True, padx=10, pady=10)

        # Treeview: Columns for Segment and 12 cells
        self.tree_voltages = ttk.Treeview(self.tree_frame,
                                          columns=("Segment", *[str(i) for i in range(1, 13)]),
                                          show="headings")
        for col in self.tree_voltages["columns"]:
            self.tree_voltages.heading(col, text=col)
            self.tree_voltages.column(col, width=80, anchor="center")
        self.tree_voltages.pack(expand=True, fill="both", pady=10)

        # Controls Frame: Charging current entry, Connect and Charge buttons, Status label
        self.controls_frame = ttk.Frame(self.tab2)
        self.controls_frame.pack(side=tk.TOP, pady=10)

        self.charge_label = ttk.Label(self.controls_frame, text="Set Charging Current (A):")
        self.charge_label.grid(row=0, column=0, padx=10, pady=5)

        self.charging_current = ttk.Entry(self.controls_frame, width=10)
        self.charging_current.grid(row=0, column=1, padx=10, pady=5)

        self.charge_button = ttk.Button(self.controls_frame, text="Start Charge", command=self.start_charge)
        self.charge_button.grid(row=0, column=2, padx=10, pady=5)

        self.connect_button = ttk.Button(self.controls_frame, text="Connect to BMS", command=self.serialConnect)
        self.connect_button.grid(row=0, column=3, padx=10, pady=5)

        self.connect_status = ttk.Label(self.controls_frame, text="Status: Disconnected", foreground="#FF5733")
        self.connect_status.grid(row=1, column=0, columnspan=4, pady=10)

    def serialConnect(self):
        try:
            self.ser = serial.Serial("COM3", 9600)
            self.connect_status.config(text="CanDapter Connected", foreground="limegreen")
            self.canDapterIsConnected = True
            self.ser.write("S5\rL1\r".encode())
            sleep(1)
            self.ser.write("O\rL1\r".encode())
        except Exception as e:
            messagebox.showerror("Error", f"Could not connect to CanDapter! {e}")
            self.canDapterIsConnected = False

    def start_charge(self):
        if not self.canDapterIsConnected:
            messagebox.showerror("Error", "Connect to BMS first!")
            return
        try:
            charge_value = float(self.charging_current.get())
            if charge_value < 0 or charge_value > 10:
                raise ValueError("Invalid charge value")
            # Calculate hex string for the command
            strHex = hex(int(10 * charge_value) + 100).replace("0x", "")
            canStr = "T1502" + strHex + "00"
            self.ser.write(canStr.encode('ascii'))
            self.ser.write(b'\rL1\r')
            messagebox.showinfo("Charging", f"Charging started with {charge_value}A")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid charge current (0-10A)")

    def update_values(self):
        while True:
            if self.canDapterIsConnected:
                try:
                    # Read data from serial and decode
                    x = self.ser.read_until(b'\r').decode().replace('t', '')
                    if len(x) < 12:
                        continue
                    if int(x[0:3], 16) == 1792:
                        seg = int(x[4:6], 16) % 12
                        cell = int(x[6:8], 16) - 4
                        if 0 <= seg < 12 and 0 <= cell < 12:
                            self.VoltageList[seg][cell] = int(x[8:12], 16) * 0.000150
                    elif int(x[0:3], 16) == 1793:
                        seg = int(x[4:6], 16)
                        cell = int(x[6:8], 16)
                        if 0 <= seg < 12 and 0 <= cell < 10:
                            self.TempsList[seg][cell] = int(x[8:10], 16) - 100

                    # Update treeview with new voltage data
                    self.tree_voltages.delete(*self.tree_voltages.get_children())
                    for i in range(12):
                        self.tree_voltages.insert("", "end",
                                                  values=(f"Segment {i + 1}",
                                                          *[f"{self.VoltageList[i][j]:.3f}V" for j in range(12)]))
                except Exception as e:
                    self.canDapterIsConnected = False
                    self.connect_status.config(text="CanDapter disconnected, reconnect:", foreground="red")
            else:
                # Simulate random data if not connected
                for i in range(12):
                    for j in range(12):
                        self.VoltageList[i][j] = random.randint(300, 420) / 100.0
                for i in range(12):
                    for j in range(10):
                        self.TempsList[i][j] = random.randint(15, 35)
                self.tree_voltages.delete(*self.tree_voltages.get_children())
                for i in range(12):
                    self.tree_voltages.insert("", "end",
                                              values=(f"Segment {i + 1}",
                                                      *[f"{self.VoltageList[i][j]:.3f}V" for j in range(12)]))

            # --------------------------
            # Update Grid Views in Tab1
            # --------------------------
            # Update Temperature Grid (12x10)
            for i in range(12):
                for j in range(10):
                    new_temp = f"{self.TempsList[i][j]} °C"
                    fg_color = "red" if self.TempsList[i][j] > 30 else "black"
                    self.tab1_temps[i][j].config(text=new_temp, foreground=fg_color)
            # Update Voltage Grid (12x12)
            for i in range(12):
                for j in range(12):
                    new_volt = f"{self.VoltageList[i][j]:.3f} V"
                    self.tab1_voltages[i][j].config(text=new_volt)

            time.sleep(1)


if __name__ == "__main__":
    root = tk.Tk()
    app = BMSApp(root)
    root.mainloop()
