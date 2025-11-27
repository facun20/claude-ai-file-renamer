import os
import json
import datetime
import mimetypes
import re
import time
import threading
import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext, messagebox
from pathlib import Path
from dotenv import load_dotenv
import renamer_lib as lib

# Load environment variables from .env file if present
load_dotenv()

class FileRenamerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Claude File Renamer")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Variables
        self.directory_var = tk.StringVar()
        self.api_key_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.files_to_rename = []
        self.rename_suggestions = []
        
        # Create GUI elements
        self.create_widgets()
        
        # Dictionary to track checkboxes
        self.checkbox_vars = {}
        
    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # API Key Frame
        api_frame = ttk.LabelFrame(main_frame, text="Claude API Key", padding="10")
        api_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(api_frame, text="API Key:").pack(side=tk.LEFT, padx=5)
        api_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, width=50, show="*")
        api_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Show/hide API key toggle
        self.show_api = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            api_frame, 
            text="Show", 
            variable=self.show_api,
            command=lambda: api_entry.config(show="" if self.show_api.get() else "*")
        ).pack(side=tk.LEFT, padx=5)
        
        # Directory Selection
        dir_frame = ttk.LabelFrame(main_frame, text="Directory Selection", padding="10")
        dir_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(dir_frame, text="Directory:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(dir_frame, textvariable=self.directory_var, width=50).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(dir_frame, text="Browse", command=self.browse_directory).pack(side=tk.LEFT, padx=5)
        
        # File list
        files_frame = ttk.LabelFrame(main_frame, text="Files to Rename", padding="10")
        files_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Scrollable canvas for the file list
        self.canvas = tk.Canvas(files_frame)
        scrollbar = ttk.Scrollbar(files_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Frame inside the canvas for the file list
        self.files_list_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.files_list_frame, anchor="nw")
        
        self.files_list_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="Scan Directory", command=self.scan_directory).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Analyze Files", command=self.analyze_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Rename Selected Files", command=self.rename_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Select All", command=lambda: self.select_all(True)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Deselect All", command=lambda: self.select_all(False)).pack(side=tk.LEFT, padx=5)
        
        # Status bar
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=5)
        
        self.progress_bar = ttk.Progressbar(
            status_frame, 
            variable=self.progress_var, 
            mode='determinate'
        )
        self.progress_bar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(status_frame, textvariable=self.status_var).pack(anchor=tk.W, padx=5)
        
        # Log area
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.pack(fill=tk.X, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=6)
        self.log_text.pack(fill=tk.X)
        
    def browse_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.directory_var.set(directory)
    
    def log(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def update_status(self, message, progress=None):
        self.status_var.set(message)
        if progress is not None:
            self.progress_var.set(progress)
        self.root.update_idletasks()
    
    def select_all(self, state):
        for var in self.checkbox_vars.values():
            var.set(state)
    
    def clear_file_list(self):
        # Clear the existing file list
        for widget in self.files_list_frame.winfo_children():
            widget.destroy()
        self.checkbox_vars = {}
    
    def scan_directory(self):
        directory = self.directory_var.get()
        if not directory:
            messagebox.showerror("Error", "Please select a directory first.")
            return
            
        if not os.path.isdir(directory):
            messagebox.showerror("Error", "Invalid directory path.")
            return
        
        self.clear_file_list()
        self.files_to_rename = []
        self.update_status("Scanning directory...", 0)
        self.log(f"Scanning directory: {directory}")
        
        # Supported file extensions
        supported_extensions = [
            '.docx', '.doc',
            '.xlsx', '.xls', '.csv',
            '.pdf',
            '.jpg', '.jpeg', '.png', '.gif'
        ]
        
        # Get files
        try:
            all_files = []
            for item in os.listdir(directory):
                file_path = os.path.join(directory, item)
                if os.path.isfile(file_path):
                    _, extension = os.path.splitext(file_path)
                    if extension.lower() in supported_extensions:
                        all_files.append(file_path)
            
            self.update_status(f"Found {len(all_files)} files", 50)
            self.log(f"Found {len(all_files)} supported files")
            
            # Display files in the UI
            for i, file_path in enumerate(all_files):
                filename = os.path.basename(file_path)
                
                # Create variable for checkbox
                var = tk.BooleanVar(value=True)
                self.checkbox_vars[file_path] = var
                
                # Create a frame for each file row
                file_frame = ttk.Frame(self.files_list_frame)
                file_frame.pack(fill=tk.X, pady=2)
                
                # Add checkbox
                ttk.Checkbutton(file_frame, variable=var).pack(side=tk.LEFT, padx=5)
                
                # Add filename label
                ttk.Label(file_frame, text=filename, width=40, anchor=tk.W).pack(side=tk.LEFT, padx=5)
                
                # Add a placeholder for the new name
                ttk.Label(file_frame, text="(Not analyzed yet)", width=50, anchor=tk.W).pack(side=tk.LEFT, padx=5)
                
                self.files_to_rename.append({
                    "path": file_path,
                    "filename": filename,
                    "frame": file_frame,
                })
            
            self.update_status(f"Ready to analyze {len(all_files)} files", 100)
            
        except Exception as e:
            self.update_status(f"Error: {str(e)}", 0)
            self.log(f"Error scanning directory: {str(e)}")
            messagebox.showerror("Error", f"Error scanning directory: {str(e)}")
    
    def update_file_row(self, index, new_name, reason):
        """Update the UI with a new filename suggestion."""
        # Get the file frame
        file_frame = self.files_to_rename[index]["frame"]
        
        # Find and update the label with the new name
        children = file_frame.winfo_children()
        if len(children) >= 3:  # Should have 3 widgets: checkbox, filename, new name
            label = children[2]
            label.config(text=new_name)
            
            # Add tooltip with reason
            self.create_tooltip(label, reason)
    
    def create_tooltip(self, widget, text):
        """Create a tooltip for a widget."""
        def enter(event):
            x, y, _, _ = widget.bbox("insert")
            x += widget.winfo_rootx() + 25
            y += widget.winfo_rooty() + 25
            
            # Create a toplevel window
            self.tooltip = tk.Toplevel(widget)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{x}+{y}")
            
            label = ttk.Label(self.tooltip, text=text, wraplength=400, 
                              background="#ffffe0", relief="solid", borderwidth=1,
                              padding=5)
            label.pack()
            
        def leave(event):
            if hasattr(self, "tooltip"):
                self.tooltip.destroy()
                
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)
    
    def analyze_files(self):
        """Analyze files with Claude and update the UI."""
        # Check if API key is provided
        api_key = self.api_key_var.get()
        if not api_key:
            messagebox.showerror("Error", "Please enter your Claude API key.")
            return
        
        # Check if there are files to analyze
        if not self.files_to_rename:
            messagebox.showerror("Error", "No files to analyze. Please scan a directory first.")
            return
        
        # Clear previous suggestions
        self.rename_suggestions = []
        
        # Start analysis in a separate thread
        self.update_status("Starting analysis...", 0)
        threading.Thread(target=self._analyze_files_thread, args=(api_key,), daemon=True).start()
    
    def _analyze_files_thread(self, api_key):
        """Background thread for file analysis."""
        total_files = len(self.files_to_rename)
        self.update_status(f"Analyzing {total_files} files...", 0)
        
        for i, file_info in enumerate(self.files_to_rename):
            file_path = file_info["path"]
            filename = file_info["filename"]
            
            # Update progress
            progress = (i / total_files) * 100
            self.update_status(f"Analyzing file {i+1}/{total_files}: {filename}", progress)
            self.log(f"Analyzing {filename}...")
            
            try:
                # Use Claude to generate naming suggestion via library
                suggestion = lib.create_claude_naming_suggestion(file_info, api_key)

                # Handle filename collisions
                file_dir = os.path.dirname(file_info["path"])
                unique_name = lib.get_unique_filename(file_dir, suggestion["new_name"])

                if unique_name != suggestion["new_name"]:
                    suggestion["new_name"] = unique_name
                    suggestion["reason"] += " (Unique identifier added to prevent naming collision)"
                
                # Add to suggestions list
                self.rename_suggestions.append(suggestion)
                
                # Update UI with suggestion
                self.update_file_row(i, suggestion["new_name"], suggestion.get("reason", "No reason provided"))
                
                # Small delay to avoid overwhelming the API
                if i < total_files - 1:
                    time.sleep(0.5)
                    
            except Exception as e:
                self.log(f"Error processing {filename}: {str(e)}")
                # Use fallback naming
                fallback = lib.smart_fallback_naming(file_info)
                self.rename_suggestions.append(fallback)
                self.update_file_row(i, fallback["new_name"], fallback.get("reason", "Fallback naming used"))
        
        self.update_status(f"Analysis complete. {total_files} files analyzed.", 100)
        self.log("File analysis complete!")
    
    def rename_files(self):
        """Rename selected files."""
        # Check if there are suggestions
        if not self.rename_suggestions:
            messagebox.showerror("Error", "No rename suggestions available. Please analyze files first.")
            return
        
        # Get selected files
        selected_files = []
        for i, file_info in enumerate(self.files_to_rename):
            if self.checkbox_vars.get(file_info["path"], tk.BooleanVar(value=False)).get():
                if i < len(self.rename_suggestions):
                    selected_files.append(self.rename_suggestions[i])
        
        if not selected_files:
            messagebox.showerror("Error", "No files selected for renaming.")
            return
        
        # Confirm rename
        confirm = messagebox.askyesno(
            "Confirm Rename", 
            f"Are you sure you want to rename {len(selected_files)} files?"
        )
        
        if not confirm:
            return
            
        # Start renaming in a separate thread
        self.update_status(f"Renaming {len(selected_files)} files...", 0)
        threading.Thread(target=self._rename_files_thread, args=(selected_files,), daemon=True).start()
    
    def _rename_files_thread(self, files):
        """Background thread for file renaming."""
        total_files = len(files)
        success_count = 0
        error_count = 0
        
        for i, file in enumerate(files):
            src_path = file["path"]
            dir_name = os.path.dirname(src_path)
            new_path = os.path.join(dir_name, file["new_name"])
            
            # Update progress
            progress = (i / total_files) * 100
            self.update_status(f"Renaming file {i+1}/{total_files}", progress)
            
            try:
                # Check if destination file already exists (should be handled during suggestion creation)
                if os.path.exists(new_path) and new_path != src_path:
                    raise FileExistsError(f"A file with the name {file['new_name']} already exists.")
                    
                os.rename(src_path, new_path)
                self.log(f"Renamed: {os.path.basename(src_path)} -> {file['new_name']}")
                success_count += 1
            except Exception as e:
                self.log(f"Error renaming {os.path.basename(src_path)}: {str(e)}")
                error_count += 1
        
        # Show summary
        self.update_status(f"Renaming complete. {success_count} succeeded, {error_count} failed.", 100)
        messagebox.showinfo(
            "Rename Complete", 
            f"Renamed {success_count} files successfully.\n{error_count} files failed."
        )
        
        # Suggest refreshing the directory
        if success_count > 0:
            refresh = messagebox.askyesno(
                "Refresh", 
                "Would you like to refresh the directory to see the changes?"
            )
            if refresh:
                self.scan_directory()

def main():
    root = tk.Tk()
    app = FileRenamerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
