"""XNC Server Simulator - Main UI Application"""

import json
import os
import queue
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

_src_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
if os.path.exists(_src_path):
    sys.path.insert(0, _src_path)

from server import XNCUDPServer, ReceivedMessage


class XNCServerSimulatorApp:
    """Main Application Class"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("XNC Server Simulator")
        self.root.geometry("1300x750")
        self.root.minsize(1100, 600)
        
        self._server: Optional[XNCUDPServer] = None
        self._message_queue: queue.Queue = queue.Queue()
        self._clients: Dict[Tuple[str, int], float] = {}
        self._messages: List[ReceivedMessage] = []
        self._max_messages = 1000
        
        self._setup_styles()
        self._setup_ui()
        self._start_message_processor()
    
    def _setup_styles(self):
        """Setup custom styles"""
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Info.TLabel", foreground="#0066cc")
        style.configure("Success.TLabel", foreground="#009933")
        style.configure("Error.TLabel", foreground="#cc0000")
    
    def _setup_ui(self):
        """Setup the UI components"""
        self._create_menu()
        self._create_main_layout()
        self._create_status_bar()
    
    def _create_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Export Messages", command=self._export_messages)
        file_menu.add_command(label="Export Mapping", command=self._export_mapping)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)
    
    def _create_main_layout(self):
        """Create main layout with left-right split"""
        main_frame = ttk.Frame(self.root, padding=5)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        right_frame = ttk.Frame(main_frame, width=380)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right_frame.pack_propagate(False)
        
        self._create_server_panel(right_frame)
        self._create_command_panel(right_frame)
        self._create_message_panel(left_frame)
    
    def _create_server_panel(self, parent):
        """Create server control panel"""
        frame = ttk.LabelFrame(parent, text="Server Control", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))
        
        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="Port:").pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value="9000")
        self.port_entry = ttk.Entry(row1, textvariable=self.port_var, width=10)
        self.port_entry.pack(side=tk.LEFT, padx=5)
        
        self.start_btn = ttk.Button(row1, text="▶ Start", command=self._toggle_server, width=10)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(row1, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        ttk.Label(row1, text="Status:").pack(side=tk.LEFT)
        self.status_label = ttk.Label(row1, text="● Stopped", foreground="red")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, pady=5)
        
        ttk.Label(row2, text="Clients:").pack(side=tk.LEFT)
        self.clients_label = ttk.Label(row2, text="0", style="Info.TLabel")
        self.clients_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(row2, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        self.clear_btn = ttk.Button(row2, text="Clear", command=self._clear_messages, width=8)
        self.clear_btn.pack(side=tk.LEFT)
        
        self.auto_scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="Auto Scroll", variable=self.auto_scroll_var).pack(side=tk.LEFT, padx=10)
    
    def _create_command_panel(self, parent):
        """Create command panel for sending commands"""
        frame = ttk.LabelFrame(parent, text="Send Command", padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        target_frame = ttk.Frame(frame)
        target_frame.pack(fill=tk.X, pady=3)
        
        ttk.Label(target_frame, text="Client IP:", width=10).pack(side=tk.LEFT)
        self.client_combo = ttk.Combobox(target_frame, width=15, state="readonly")
        self.client_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(target_frame, text="Port:").pack(side=tk.LEFT)
        self.target_port_var = tk.StringVar(value="8888")
        self.target_port_entry = ttk.Entry(target_frame, textvariable=self.target_port_var, width=6)
        self.target_port_entry.pack(side=tk.LEFT, padx=3)
        
        cmd_frame = ttk.Frame(frame)
        cmd_frame.pack(fill=tk.X, pady=3)
        
        ttk.Label(cmd_frame, text="Command:", width=10).pack(side=tk.LEFT)
        self.cmd_type_var = tk.StringVar(value="WRITE_PROPERTY")
        self.cmd_type_combo = ttk.Combobox(
            cmd_frame, 
            textvariable=self.cmd_type_var,
            values=["READ_PROPERTY", "WRITE_PROPERTY"],
            width=15,
            state="readonly"
        )
        self.cmd_type_combo.pack(side=tk.LEFT, padx=5)
        self.cmd_type_combo.bind("<<ComboboxSelected>>", self._on_cmd_type_change)
        
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        
        param_frame = ttk.Frame(frame)
        param_frame.pack(fill=tk.X, pady=3)
        
        ttk.Label(param_frame, text="vdID:", width=10).pack(side=tk.LEFT)
        self.device_var = tk.StringVar()
        self.device_entry = ttk.Entry(param_frame, textvariable=self.device_var, width=8)
        self.device_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(param_frame, text="oid:").pack(side=tk.LEFT, padx=(10, 0))
        self.point_var = tk.StringVar()
        self.point_entry = ttk.Entry(param_frame, textvariable=self.point_var, width=8)
        self.point_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(param_frame, text="PID:").pack(side=tk.LEFT, padx=(10, 0))
        self.pid_var = tk.StringVar(value="85")
        self.pid_entry = ttk.Entry(param_frame, textvariable=self.pid_var, width=5)
        self.pid_entry.pack(side=tk.LEFT, padx=5)
        
        value_frame = ttk.Frame(frame)
        value_frame.pack(fill=tk.X, pady=3)
        
        ttk.Label(value_frame, text="Value:", width=10).pack(side=tk.LEFT)
        self.value_var = tk.StringVar()
        self.value_entry = ttk.Entry(value_frame, textvariable=self.value_var, width=25)
        self.value_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        uuid_frame = ttk.Frame(frame)
        uuid_frame.pack(fill=tk.X, pady=3)
        
        ttk.Label(uuid_frame, text="UUID:", width=10).pack(side=tk.LEFT)
        self.uuid_var = tk.StringVar(value="0")
        self.uuid_entry = ttk.Entry(uuid_frame, textvariable=self.uuid_var, width=8)
        self.uuid_entry.pack(side=tk.LEFT, padx=5)
        
        self.send_btn = ttk.Button(uuid_frame, text="📤 Send Command", command=self._send_command)
        self.send_btn.pack(side=tk.RIGHT, padx=5)
        self.send_btn.config(state="disabled")
        
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        
        detail_frame = ttk.LabelFrame(frame, text="Message Detail", padding=5)
        detail_frame.pack(fill=tk.BOTH, expand=True)
        
        self.detail_text = scrolledtext.ScrolledText(detail_frame, height=12, wrap=tk.WORD, font=("Consolas", 9))
        self.detail_text.pack(fill=tk.BOTH, expand=True)
    
    def _create_message_panel(self, parent):
        """Create message display panel"""
        frame = ttk.LabelFrame(parent, text="Received Messages", padding=5)
        frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("Time", "Client", "Type", "vdID", "Seq", "Points")
        self.message_tree = ttk.Treeview(frame, columns=columns, show="headings", height=15)
        
        self.message_tree.heading("Time", text="Time")
        self.message_tree.heading("Client", text="Client")
        self.message_tree.heading("Type", text="Type")
        self.message_tree.heading("vdID", text="vdID")
        self.message_tree.heading("Seq", text="Seq")
        self.message_tree.heading("Points", text="Points")
        
        self.message_tree.column("Time", width=80, minwidth=60)
        self.message_tree.column("Client", width=120, minwidth=100)
        self.message_tree.column("Type", width=150, minwidth=120)
        self.message_tree.column("vdID", width=60, minwidth=50)
        self.message_tree.column("Seq", width=50, minwidth=40)
        self.message_tree.column("Points", width=300, minwidth=200)
        
        self.message_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.message_tree.bind("<<TreeviewSelect>>", self._on_message_select)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.message_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.message_tree.config(yscrollcommand=scrollbar.set)
    
    def _create_status_bar(self):
        """Create status bar"""
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W, padding=(5, 2))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _start_message_processor(self):
        """Start the message processor thread"""
        self._process_messages()
    
    def _process_messages(self):
        """Process messages from queue"""
        try:
            while True:
                msg = self._message_queue.get_nowait()
                self._add_message_to_tree(msg)
        except queue.Empty:
            pass
        
        self._update_clients_display()
        self.root.after(100, self._process_messages)
    
    def _toggle_server(self):
        """Toggle server start/stop"""
        if self._server is None:
            try:
                port = int(self.port_var.get())
            except ValueError:
                messagebox.showerror("Error", "Invalid port number")
                return
            
            self._server = XNCUDPServer(
                port=port,
                on_message_received=self._on_message_received,
                on_client_connected=self._on_client_connected,
                on_error=self._on_error
            )
            
            if self._server.start():
                self.start_btn.config(text="⏹ Stop")
                self.status_label.config(text="● Running", foreground="green")
                self.port_entry.config(state="disabled")
                self.send_btn.config(state="normal")
                self.status_bar.config(text=f"Server started on port {port}")
            else:
                self._server = None
                messagebox.showerror("Error", "Failed to start server")
        else:
            self._server.stop()
            self._server = None
            self.start_btn.config(text="▶ Start")
            self.status_label.config(text="● Stopped", foreground="red")
            self.port_entry.config(state="normal")
            self.send_btn.config(state="disabled")
            self.status_bar.config(text="Server stopped")
    
    def _on_message_received(self, msg: ReceivedMessage):
        """Callback when message received"""
        self._message_queue.put(msg)
    
    def _on_client_connected(self, addr: Tuple[str, int]):
        """Callback when client connected"""
        self._clients[addr] = time.time()
    
    def _on_error(self, error: str):
        """Callback on error"""
        self.root.after(0, lambda: self.status_bar.config(text=f"Error: {error}"))
    
    def _add_message_to_tree(self, msg: ReceivedMessage):
        """Add message to tree view"""
        self._messages.append(msg)
        if len(self._messages) > self._max_messages:
            self._messages.pop(0)
            children = self.message_tree.get_children()
            if children:
                self.message_tree.delete(children[0])
        
        time_str = datetime.fromtimestamp(msg.timestamp).strftime("%H:%M:%S.%f")[:-3]
        client_str = f"{msg.client_addr[0]}:{msg.client_addr[1]}"
        points_str = ", ".join(f"{k}={v}" for k, v in list(msg.points.items())[:2])
        if len(msg.points) > 2:
            points_str += "..."
        
        item_id = self.message_tree.insert("", tk.END, values=(
            time_str,
            client_str,
            msg.message_type,
            msg.device_id or "-",
            msg.sequence,
            points_str
        ), tags=(msg.message_type,))
        
        self.message_tree.tag_configure("UPDATE_PROPERTY", foreground="#0066cc")
        self.message_tree.tag_configure("READ_PROPERTY", foreground="#009933")
        self.message_tree.tag_configure("WRITE_PROPERTY", foreground="#ff6600")
        self.message_tree.tag_configure("[SEND] READ_PROPERTY", foreground="#006633")
        self.message_tree.tag_configure("[SEND] WRITE_PROPERTY", foreground="#cc5500")
        
        if self.auto_scroll_var.get():
            self.message_tree.see(item_id)
    
    def _update_clients_display(self):
        """Update clients display"""
        if self._server:
            clients = self._server.get_clients()
            self.clients_label.config(text=str(len(clients)))
            
            client_ips = list(set(addr[0] for addr in clients))
            client_ips.sort()
            
            current = self.client_combo.get()
            self.client_combo["values"] = client_ips
            if current not in client_ips and client_ips:
                self.client_combo.set(client_ips[0])
    
    def _on_message_select(self, event):
        """Handle message selection"""
        selection = self.message_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        values = self.message_tree.item(item, "values")
        if not values:
            return
        
        idx = self.message_tree.index(item)
        if idx < len(self._messages):
            msg = self._messages[idx]
            detail = self._format_message_detail(msg)
            self.detail_text.delete("1.0", tk.END)
            self.detail_text.insert("1.0", detail)
    
    def _format_message_detail(self, msg: ReceivedMessage) -> str:
        """Format message detail for display"""
        lines = [
            f"Timestamp: {datetime.fromtimestamp(msg.timestamp).isoformat()}",
            f"Client: {msg.client_addr[0]}:{msg.client_addr[1]}",
            f"Sequence: {msg.sequence}",
            f"Message Type: {msg.message_type}",
            f"vdID: {msg.device_id}",
            "",
            "Points:"
        ]
        
        for name, value in msg.points.items():
            lines.append(f"  {name}: {value}")
        
        lines.extend(["", "Raw Parsed Data:"])
        lines.append(json.dumps(msg.parsed_data, indent=2, ensure_ascii=False))
        
        return "\n".join(lines)
    
    def _on_client_select(self, event):
        """Handle client selection"""
        pass
    
    def _on_cmd_type_change(self, event):
        """Handle command type change"""
        if self.cmd_type_var.get() == "WRITE_PROPERTY":
            self.value_entry.config(state="normal")
        else:
            self.value_entry.config(state="disabled")
    
    def _send_command(self):
        """Send command to selected client"""
        if not self._server:
            return
        
        host = self.client_combo.get()
        if not host:
            messagebox.showwarning("Warning", "Please select a client")
            return
        
        try:
            target_port = int(self.target_port_var.get())
            client_addr = (host, target_port)
        except:
            messagebox.showerror("Error", "Invalid target port")
            return
        
        device_id = self.device_var.get().strip()
        point_name = self.point_var.get().strip()
        
        if not device_id or not point_name:
            messagebox.showwarning("Warning", "Please enter vdID and oid")
            return
        
        try:
            pid = int(self.pid_var.get())
            uuid = int(self.uuid_var.get())
            vdid = int(device_id)
            oid = int(point_name)
        except ValueError:
            messagebox.showerror("Error", "vdID, oid, PID and UUID must be integers")
            return
        
        cmd_type = self.cmd_type_var.get()
        value = None
        
        if cmd_type == "WRITE_PROPERTY":
            value_str = self.value_var.get().strip()
            if not value_str:
                messagebox.showwarning("Warning", "Please enter a value for WRITE_PROPERTY")
                return
            
            try:
                if value_str.lower() == "true":
                    value = True
                elif value_str.lower() == "false":
                    value = False
                elif "." in value_str:
                    value = float(value_str)
                else:
                    value = int(value_str)
            except ValueError:
                value = value_str
        
        if cmd_type == "READ_PROPERTY":
            success = self._server.send_read_command(
                client_addr=client_addr,
                device_id=device_id,
                point_name=point_name,
                pid=pid,
                uuid=uuid
            )
        else:
            success = self._server.send_write_command(
                client_addr=client_addr,
                device_id=device_id,
                point_name=point_name,
                value=value,
                pid=pid,
                uuid=uuid
            )
        
        if success:
            self._add_sent_message(cmd_type, client_addr, vdid, oid, pid, uuid, value)
            self.status_bar.config(text=f"Command sent to {host}:{target_port}")
        else:
            self.status_bar.config(text=f"Failed to send command to {host}:{target_port}")
    
    def _add_sent_message(self, cmd_type: str, client_addr: Tuple[str, int], vdid: int, oid: int, pid: int, uuid: int, value: Any = None):
        """Add sent command message to display"""
        from codec import ProtobufCodec
        
        if cmd_type == "READ_PROPERTY":
            msg = ProtobufCodec.create_read_property_message(uuid, vdid, oid, pid)
        else:
            msg = ProtobufCodec.create_write_property_message(uuid, vdid, oid, pid, value)
        
        parsed = ProtobufCodec.message_to_dict(msg)
        
        points = {f"oid={oid}(pid={pid})": value if value is not None else "READ"}
        
        sent_msg = ReceivedMessage(
            timestamp=time.time(),
            client_addr=client_addr,
            sequence=0,
            raw_data=b"",
            parsed_data=parsed,
            message_type=f"[SEND] {cmd_type}",
            device_id=str(vdid),
            points=points
        )
        
        self._add_message_to_tree(sent_msg)
    
    def _clear_messages(self):
        """Clear all messages"""
        self._messages.clear()
        for item in self.message_tree.get_children():
            self.message_tree.delete(item)
        self.detail_text.delete("1.0", tk.END)
    
    def _sort_messages(self, column: str):
        """Sort messages by column"""
        pass
    
    def _export_messages(self):
        """Export messages to JSON file"""
        if not self._messages:
            messagebox.showinfo("Info", "No messages to export")
            return
        
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            data = []
            for msg in self._messages:
                data.append({
                    "timestamp": msg.timestamp,
                    "client_addr": list(msg.client_addr),
                    "sequence": msg.sequence,
                    "message_type": msg.message_type,
                    "device_id": msg.device_id,
                    "points": msg.points,
                    "parsed_data": msg.parsed_data
                })
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            messagebox.showinfo("Success", f"Exported {len(data)} messages to {filename}")
    
    def _export_mapping(self):
        """Export device/point mapping"""
        if not self._server:
            messagebox.showinfo("Info", "Server not running")
            return
        
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            mapping = self._server.get_mapping()
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(mapping, f, indent=2, ensure_ascii=False)
            
            messagebox.showinfo("Success", f"Exported mapping to {filename}")
    
    def _show_about(self):
        """Show about dialog"""
        messagebox.showinfo(
            "About XNC Server Simulator",
            "XNC Server Simulator v1.0\n\n"
            "A tool for simulating XNC server to debug XAgent.\n\n"
            "Features:\n"
            "• Receive and display data from XAgent\n"
            "• Send READ/WRITE commands to XAgent\n"
            "• Export messages and mappings"
        )
    
    def on_closing(self):
        """Handle window closing"""
        if self._server:
            self._server.stop()
        self.root.destroy()


def run_app():
    """Run the application"""
    root = tk.Tk()
    app = XNCServerSimulatorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    run_app()
