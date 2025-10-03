import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import csv
import time
import threading
from datetime import datetime
import numpy as np
import serial.tools.list_ports
import signal
import sys
import os
from marvelmind import MarvelmindHedge

class MarvelmindTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("Marvelmind Indoor Tracking System - Lab Data Collector")
        self.root.geometry("1200x800")
        
        # Initialize Marvelmind connection
        self.hedge = None
        self.tracking_active = False
        self.data_collection_active = False
        self.collected_data = []
        self.position_history = []
        self.max_history = 500
        
        # Data collection settings
        self.collection_label = ""
        self.collection_type = "static"
        self.collection_duration = 10
        
        self.setup_gui()
        self.setup_plot()
        
        # Setup signal handler for Ctrl+C
        self.setup_signal_handler()
        
    def setup_signal_handler(self):
        """Setup Ctrl+C signal handler for graceful shutdown"""
        def signal_handler(sig, frame):
            print('\nReceived Ctrl+C, shutting down gracefully...')
            self.cleanup_and_exit()
            
        signal.signal(signal.SIGINT, signal_handler)
        print("Press Ctrl+C to quit the application")
        
    def cleanup_and_exit(self):
        """Clean up resources and exit gracefully"""
        self.tracking_active = False
        if self.hedge:
            print("Stopping Marvelmind connection...")
            self.hedge.stop()
            self.hedge = None
        print("Application closed successfully.")
        self.root.destroy()
        sys.exit(0)
        
    def setup_gui(self):
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Control Panel
        control_frame = ttk.LabelFrame(main_frame, text="Control Panel", padding="10")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Connection controls
        conn_frame = ttk.Frame(control_frame)
        conn_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Serial Port Selection
        port_frame = ttk.Frame(conn_frame)
        port_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(port_frame, text="Serial Port:").pack(side=tk.LEFT)
        
        # Dropdown for port selection
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(port_frame, textvariable=self.port_var, width=25, state="readonly")
        self.port_combo.pack(side=tk.LEFT, padx=(5, 10))
        self.port_combo.bind('<<ComboboxSelected>>', self.on_port_selected)
        
        # Refresh ports button
        ttk.Button(port_frame, text="Refresh Ports", command=self.refresh_ports).pack(side=tk.LEFT, padx=(0, 10))
        
        # Quit button
        ttk.Button(port_frame, text="Quit", command=self.cleanup_and_exit).pack(side=tk.RIGHT, padx=(10, 0))
        
        # Auto-detect and populate ports on startup
        self.refresh_ports()
        
        # Connection buttons
        button_frame = ttk.Frame(conn_frame)
        button_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.connect_btn = ttk.Button(button_frame, text="Connect", command=self.connect_hedge)
        self.connect_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.disconnect_btn = ttk.Button(button_frame, text="Disconnect", command=self.disconnect_hedge, state=tk.DISABLED)
        self.disconnect_btn.pack(side=tk.LEFT)
        
        # Status
        self.status_var = tk.StringVar(value="Disconnected")
        ttk.Label(button_frame, text="Status:").pack(side=tk.LEFT, padx=(20, 5))
        self.status_label = ttk.Label(button_frame, textvariable=self.status_var, foreground="red")
        self.status_label.pack(side=tk.LEFT)
        
        # Instructions
        instruction_text = "Instructions: Select port → Connect → Start Collection | Press Ctrl+C to quit"
        ttk.Label(button_frame, text=instruction_text, font=("Arial", 8), foreground="gray").pack(side=tk.RIGHT, padx=(10, 0))
        
        # Data Collection Controls
        collection_frame = ttk.LabelFrame(control_frame, text="Data Collection", padding="5")
        collection_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Collection type
        type_frame = ttk.Frame(collection_frame)
        type_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(type_frame, text="Type:").pack(side=tk.LEFT)
        self.type_var = tk.StringVar(value="static")
        type_radio1 = ttk.Radiobutton(type_frame, text="Static", variable=self.type_var, value="static")
        type_radio2 = ttk.Radiobutton(type_frame, text="Dynamic", variable=self.type_var, value="dynamic")
        type_radio1.pack(side=tk.LEFT, padx=(5, 10))
        type_radio2.pack(side=tk.LEFT)
        
        # Duration for static collection
        duration_frame = ttk.Frame(collection_frame)
        duration_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(duration_frame, text="Duration (s):").pack(side=tk.LEFT)
        self.duration_var = tk.StringVar(value="10")
        ttk.Entry(duration_frame, textvariable=self.duration_var, width=10).pack(side=tk.LEFT, padx=(5, 10))
        
        # Label
        ttk.Label(duration_frame, text="Label:").pack(side=tk.LEFT, padx=(10, 5))
        self.label_var = tk.StringVar()
        ttk.Entry(duration_frame, textvariable=self.label_var, width=20).pack(side=tk.LEFT, padx=(0, 10))
        
        # Collection buttons
        button_frame2 = ttk.Frame(collection_frame)
        button_frame2.pack(fill=tk.X, pady=(5, 0))
        
        self.start_collection_btn = ttk.Button(button_frame2, text="Start Collection", 
                                             command=self.start_data_collection, state=tk.DISABLED)
        self.start_collection_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_collection_btn = ttk.Button(button_frame2, text="Stop Collection", 
                                            command=self.stop_data_collection, state=tk.DISABLED)
        self.stop_collection_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(button_frame2, text="Save Data", command=self.save_data).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame2, text="Quick Save", command=self.quick_save).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame2, text="Clear Data", command=self.clear_data).pack(side=tk.LEFT)
        
        # Current position display
        pos_frame = ttk.LabelFrame(control_frame, text="Current Hedgehog Position", padding="5")
        pos_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.pos_var = tk.StringVar(value="X: -- m, Y: -- m, Z: -- m")
        ttk.Label(pos_frame, textvariable=self.pos_var).pack()
        
        self.data_count_var = tk.StringVar(value="Collected Points: 0")
        ttk.Label(pos_frame, textvariable=self.data_count_var).pack()
        
        # Plot frame
        self.plot_frame = ttk.LabelFrame(main_frame, text="Real-time Hedgehog Tracking", padding="5")
        self.plot_frame.pack(fill=tk.BOTH, expand=True)

    def refresh_ports(self):
        """Detect and populate available serial ports"""
        try:
            ports = serial.tools.list_ports.comports()
            
            if ports:
                port_list = []
                port_info = []
                
                for port in ports:
                    port_list.append(port.device)
                    desc = f"{port.device}"
                    if port.description and port.description != "n/a":
                        desc += f" - {port.description}"
                    if port.manufacturer and port.manufacturer != "n/a":
                        desc += f" ({port.manufacturer})"
                    port_info.append(desc)
                
                self.port_combo['values'] = port_info
                
                if len(port_list) > 0:
                    # Try to find a likely USB serial port
                    best_port = 0
                    for i, port in enumerate(ports):
                        port_desc = (port.description or "").lower()
                        port_manuf = (port.manufacturer or "").lower()
                        
                        if any(keyword in port_desc or keyword in port_manuf for keyword in 
                               ['usb', 'serial', 'ch340', 'cp210', 'ftdi']):
                            best_port = i
                            break
                    
                    self.port_combo.current(best_port)
                    self.port_var.set(port_list[best_port])
                    
            else:
                self.port_combo['values'] = ["No ports detected"]
                self.port_combo.current(0)
                self.port_var.set("")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error detecting ports: {e}")
            
    def on_port_selected(self, event=None):
        """Handle port selection from combobox"""
        selected_text = self.port_combo.get()
        if selected_text and " - " in selected_text:
            port_device = selected_text.split(" - ")[0]
            self.port_var.set(port_device)
        
    def setup_plot(self):
        # Create matplotlib figure
        self.fig, self.ax = plt.subplots(figsize=(10, 8))
        self.ax.set_xlabel('X Position (m)')
        self.ax.set_ylabel('Y Position (m)')
        self.ax.set_title('Marvelmind Hedgehog Tracking - Top View')
        self.ax.grid(True, alpha=0.3)
        self.ax.set_aspect('equal')
        
        # Initialize plot elements
        self.hedgehog_point, = self.ax.plot([], [], 'ro', markersize=10, label='Hedgehog (Current)')
        self.trail_line, = self.ax.plot([], [], 'b-', alpha=0.6, linewidth=1, label='Movement Trail')
        self.collection_points, = self.ax.plot([], [], 'go', markersize=8, alpha=0.7, label='Collection Points')
        
        self.ax.legend()
        
        # Embed plot in tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
    def connect_hedge(self):
        selected_port = self.port_var.get()
        
        if not selected_port:
            messagebox.showerror("No Port Selected", "Please select a serial port first")
            return
            
        try:
            self.hedge = MarvelmindHedge(tty=selected_port, adr=None, debug=True)
            self.hedge.start()
            
            # Wait for connection
            time.sleep(2)
            
            # Start tracking thread
            self.tracking_active = True
            self.tracking_thread = threading.Thread(target=self.tracking_loop, daemon=True)
            self.tracking_thread.start()
            
            self.status_var.set(f"Connected to {selected_port}")
            self.status_label.config(foreground="green")
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
            self.start_collection_btn.config(state=tk.NORMAL)
            self.port_combo.config(state=tk.DISABLED)
            
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect to {selected_port}:\n{str(e)}")
            
    def disconnect_hedge(self):
        self.tracking_active = False
        if self.hedge:
            self.hedge.stop()
            self.hedge = None
            
        self.status_var.set("Disconnected")
        self.status_label.config(foreground="red")
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.start_collection_btn.config(state=tk.DISABLED)
        self.stop_collection_btn.config(state=tk.DISABLED)
        self.port_combo.config(state="readonly")
        
    def tracking_loop(self):
        while self.tracking_active and self.hedge:
            try:
                position = self.hedge.position()
                
                # FIXED: Correct indexing for Marvelmind position data
                # position returns [hedge_id, x, y, z, angle, timestamp, validity_flag]
                if position and len(position) >= 6:
                    x, y, z = position[1], position[2], position[3]  
                    timestamp = time.time()
                    
                    # Update position display
                    self.pos_var.set(f"X: {x:.3f} m, Y: {y:.3f} m, Z: {z:.3f} m")
                    
                    # Add to history
                    self.position_history.append((timestamp, x, y, z))
                    if len(self.position_history) > self.max_history:
                        self.position_history.pop(0)
                    
                    # Collect data if active
                    if self.data_collection_active:
                        data_point = {
                            'timestamp': timestamp,
                            'datetime': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S.%f'),
                            'x': x,
                            'y': y,
                            'z': z,
                            'label': self.collection_label,
                            'type': self.collection_type
                        }
                        self.collected_data.append(data_point)
                        self.data_count_var.set(f"Collected Points: {len(self.collected_data)}")
                    
                    # Update plot
                    self.update_plot()
                    
            except Exception as e:
                print(f"Tracking error: {e}")
                
            time.sleep(0.1)  # 10 Hz update rate
    
    def update_plot(self):
        if not self.position_history:
            return
            
        # Extract coordinates
        timestamps, x_coords, y_coords, z_coords = zip(*self.position_history)
        
        # Update current position
        current_x, current_y = x_coords[-1], y_coords[-1]
        self.hedgehog_point.set_data([current_x], [current_y])
        
        # Update trail
        self.trail_line.set_data(x_coords, y_coords)
        
        # Update collection points
        if self.collected_data:
            collect_x = [point['x'] for point in self.collected_data]
            collect_y = [point['y'] for point in self.collected_data]
            self.collection_points.set_data(collect_x, collect_y)
        
        # Auto-scale axes
        all_x = list(x_coords)
        all_y = list(y_coords)
        if self.collected_data:
            all_x.extend([point['x'] for point in self.collected_data])
            all_y.extend([point['y'] for point in self.collected_data])
            
        if all_x and all_y:
            margin = 0.5  # 0.5 meter margin
            self.ax.set_xlim(min(all_x) - margin, max(all_x) + margin)
            self.ax.set_ylim(min(all_y) - margin, max(all_y) + margin)
        
        # Redraw
        self.canvas.draw_idle()
    
    def start_data_collection(self):
        self.collection_label = self.label_var.get() or f"Collection_{datetime.now().strftime('%H%M%S')}"
        self.collection_type = self.type_var.get()
        
        self.data_collection_active = True
        self.start_collection_btn.config(state=tk.DISABLED)
        self.stop_collection_btn.config(state=tk.NORMAL)
        
        # For static collection, auto-stop after specified duration
        if self.collection_type == "static":
            try:
                duration = int(self.duration_var.get())
                threading.Timer(duration, self.stop_data_collection).start()
                messagebox.showinfo("Data Collection", f"Static collection started for {duration} seconds")
            except ValueError:
                messagebox.showerror("Error", "Invalid duration value")
                self.stop_data_collection()
        else:
            messagebox.showinfo("Data Collection", "Dynamic collection started. Click 'Stop Collection' when finished.")
    
    def stop_data_collection(self):
        self.data_collection_active = False
        self.start_collection_btn.config(state=tk.NORMAL)
        self.stop_collection_btn.config(state=tk.DISABLED)
        
        if self.collection_type == "static":
            current_label_data = [p for p in self.collected_data if p['label'] == self.collection_label]
            messagebox.showinfo("Collection Complete", f"Static data collection completed. Collected {len(current_label_data)} points.")

    def quick_save(self):
        """Quick save to Desktop with timestamp"""
        if not self.collected_data:
            messagebox.showwarning("No Data", "No data to save. Start collection first!")
            return
        
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            filename = os.path.join(desktop, f"marvelmind_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            
            result = messagebox.askyesno("Quick Save", f"Save data to Desktop?\n\n{filename}")
            if result:
                self.write_csv_file(filename)
        except Exception as e:
            messagebox.showerror("Quick Save Failed", f"Could not save to Desktop: {e}")

    def save_data(self):
        print(f"Save Data clicked. Collected data points: {len(self.collected_data)}")
        
        if not self.collected_data:
            messagebox.showwarning("No Data", "No data to save. Start collection first!")
            return
        
        try:
            print("Attempting to open file dialog...")
            
            # Force the dialog to appear on top
            self.root.lift()
            self.root.attributes('-topmost', True)
            
            filename = filedialog.asksaveasfilename(
                parent=self.root,
                title="Save Marvelmind Data",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialname=f"marvelmind_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            
            # Reset topmost
            self.root.attributes('-topmost', False)
            
            print(f"Dialog returned: {repr(filename)}")
            
            if filename:
                self.write_csv_file(filename)
            else:
                print("No filename selected - trying fallback method")
                self.save_data_fallback()
                
        except Exception as e:
            print(f"Error with file dialog: {e}")
            messagebox.showerror("Dialog Error", f"File dialog failed: {e}\nTrying fallback save method...")
            self.save_data_fallback()

    def write_csv_file(self, filename):
        """Write data to CSV file"""
        try:
            print(f"Writing to file: {filename}")
            with open(filename, 'w', newline='') as csvfile:
                fieldnames = ['timestamp', 'datetime', 'x', 'y', 'z', 'label', 'type']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for data_point in self.collected_data:
                    writer.writerow(data_point)
                    
            print(f"File saved successfully!")
            messagebox.showinfo("Save Complete", f"Data saved to:\n{filename}")
            
        except Exception as e:
            print(f"Error writing file: {e}")
            messagebox.showerror("Write Error", f"Failed to write file: {e}")

    def save_data_fallback(self):
        """Fallback save method - let user choose directory"""
        try:
            # Try to open a directory dialog instead
            print("Trying directory dialog...")
            
            directory = filedialog.askdirectory(
                parent=self.root,
                title="Choose Directory to Save Data",
                initialdir=os.path.expanduser("~/Desktop")  # Start at Desktop
            )
            
            if directory:
                filename = os.path.join(directory, f"marvelmind_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
                print(f"Saving to chosen directory: {filename}")
                self.write_csv_file(filename)
            else:
                # If directory dialog also fails, use manual entry
                print("Directory dialog failed, using manual entry")
                self.save_data_manual_entry()
                    
        except Exception as e:
            print(f"Directory dialog failed: {e}")
            self.save_data_manual_entry()

    def save_data_manual_entry(self):
        """Manual filename entry if dialog fails"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Enter Filename")
        dialog.geometry("500x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Enter full path and filename:").pack(pady=10)
        
        # Get current directory as default
        current_dir = os.path.dirname(os.path.abspath(__file__))
        default_filename = os.path.join(current_dir, f"marvelmind_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        
        filename_var = tk.StringVar(value=default_filename)
        entry = ttk.Entry(dialog, textvariable=filename_var, width=60)
        entry.pack(pady=5, padx=10)
        
        def save_manual():
            filename = filename_var.get()
            if filename:
                dialog.destroy()
                self.write_csv_file(filename)
            else:
                messagebox.showerror("Error", "Please enter a filename")
        
        def cancel_manual():
            dialog.destroy()
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Save", command=save_manual).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=cancel_manual).pack(side=tk.LEFT, padx=5)
        
        entry.focus()
        entry.select_range(0, tk.END)
    
    def clear_data(self):
        if messagebox.askyesno("Clear Data", "Are you sure you want to clear all collected data?"):
            self.collected_data.clear()
            self.position_history.clear()
            self.data_count_var.set("Collected Points: 0")
            self.update_plot()

def main():
    root = tk.Tk()
    app = MarvelmindTracker(root)
    
    # Handle window close button (X)
    def on_closing():
        app.cleanup_and_exit()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.cleanup_and_exit()

if __name__ == "__main__":
    main()
