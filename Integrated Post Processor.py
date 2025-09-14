import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import math
from tkinter.font import Font
import matplotlib
matplotlib.use('TkAgg')
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

def calculate_passes_and_angular_displacement():
    """Calculate number of passes and angular displacement based on toolpath and stock diameter"""
    try:
        stock_dia = float(stock_diameter_var.get())
        tool_dia = float(tool_diameter_var.get())
        
        # Calculate number of passes needed for complete revolution
        # Based on tool diameter and desired overlap
        overlap_factor = 0.8  # 80% overlap for better finish. Can be modified for better quality
        pass_width = tool_dia * overlap_factor
        num_passes = max(1, int(math.ceil(math.pi * stock_dia / pass_width)))
        
        # Calculate angular displacement per pass
        angular_displacement = 360.0 / num_passes
        
        # Update display variables
        num_passes_var.set(str(num_passes))
        angular_displacement_var.set(f"{angular_displacement:.2f}")
        
        return num_passes, angular_displacement
        
    except ValueError:
        return None, None

def modify_gcode(input_file, output_file, stock_diameter=25.0, tool_diameter=6.0, num_passes=None, angular_displacement=None):
    """
    Modify G-code to create multiple passes with angular indexing for rotary axis.
    Each pass runs the complete toolpath with incremental Y-axis rotation.
    """
    # Calculate passes and displacement if not provided
    if num_passes is None or angular_displacement is None:
        num_passes, angular_displacement = calculate_passes_and_angular_displacement()
        if num_passes is None:
            return None
    
    with open(input_file, 'r') as f:
        lines = f.readlines()
    
    # Filter out comments and empty lines, keep only movement commands
    filtered_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("(") and not stripped.startswith(";"):
            # Remove any existing Y commands
            stripped = re.sub(r'\bY[-+]?[0-9.]+', '', stripped)
            filtered_lines.append(stripped)
    
    # Output header
    output_lines = [
        "; Modified G-code for rotary axis with indexed passes\n",
        f"; Total passes: {num_passes}\n",
        f"; Angular displacement per pass: {angular_displacement:.2f} degrees\n",
        ";\n",
        "; CRITICAL: GRBL Y-AXIS CALIBRATION REQUIRED\n",
        "; This code assumes 1.000 Y unit = 1.000 degree rotation\n",
        "; Configure GRBL $101 (Y steps/unit) as:\n",
        "; $101 = (motor_steps_per_rev × microsteps × gear_ratio) / 360\n",
        "; Example: 200 steps × 16 microsteps × 3:1 ratio = $101=26.67\n",
        "; Alternative: Use arc-length method with Y=(Pi×diameter/360)×degrees\n",
        ";\n",
        "G90 ; Absolute positioning\n"
        ]
        
    # Generate  passes
    for pass_num in range(num_passes):
        current_angle = pass_num * angular_displacement
        
        # Add pass header
        output_lines.append(f"; Pass {pass_num + 1} of {num_passes}\n")
        
        # Safe retraction and positioning sequence
        if pass_num == 0:
            output_lines.append("G0 Z5.0 ; Safe retraction height\n")
            output_lines.append("M5 ; Spindle stop (safety during indexing)\n")
            output_lines.append(f"G0 Y{current_angle:.4f} ; Position to start angle\n")
            output_lines.append("M3 S12000 ; Spindle start (adjust speed as needed)\n")
        else:
            output_lines.append("G0 Z5.0 ; Retract before indexing\n")
            output_lines.append("M5 ; Spindle stop for safe indexing\n")
            output_lines.append(f"G0 Y{current_angle:.4f} ; Index to next pass\n")
            output_lines.append("M3 S12000 ; Restart spindle\n")

        # Add all the original toolpath commands for this pass
        for line in filtered_lines:
            if line.strip():
                output_lines.append(line + "\n")
    
    # Add ending commands
    output_lines.append("G0 Z5.0 ; Final retraction\n")
    output_lines.append("M5 ; Spindle stop\n")
    output_lines.append("G0 Y0 ; Return to start position\n")
    output_lines.append("M30 ; End program\n")
    # Write to output file
    with open(output_file, 'w') as out:
        out.writelines(output_lines)
    
    return output_file

def extract_tool_diameter_from_gcode(input_file):
    """Extract tool diameter from G-code comments"""
    with open(input_file, "r") as file:
        lines = file.readlines()

    tool_diameter = None
    for line in lines:
        # Look for tool diameter patterns
        d_match = re.search(r'(?:CD|D|DIAMETER)=?([0-9.]+)', line, re.IGNORECASE)
        if d_match:
            tool_diameter = float(d_match.group(1))
            break
        
        # Look for tool radius and convert
        r_match = re.search(r'(?:CR|R|RADIUS)=?([0-9.]+)', line, re.IGNORECASE)
        if r_match:
            tool_diameter = 2 * float(r_match.group(1))
            break

    return tool_diameter

def extract_feedrate_from_gcode(input_file):
    """Extract feedrate from G-code"""
    with open(input_file, "r") as file:
        lines = file.readlines()

    feedrate = None
    for line in lines:
        match = re.search(r'F([-+]?\d*\.\d+|\d+)', line)
        if match:
            feedrate = float(match.group(1))
            break

    return feedrate

def select_file():
    """Handle file selection and parameter detection"""
    file_path = filedialog.askopenfilename(
        filetypes=[("G-Code Files", "*.nc *.gcode *.ngc *.tap"), ("All Files", "*.*")],
        title="Select G-Code File"
    )
    
    if not file_path:
        return
    
    # Update file display
    file_name = os.path.basename(file_path)
    file_path_var.set(file_path)
    file_label.config(text=file_name)
    
    # Generate output path
    base = os.path.splitext(file_path)[0]
    output_file = f"{base}_rotary.nc"
    output_path_var.set(output_file)
    
    # Extract parameters from G-code
    tool_diameter = extract_tool_diameter_from_gcode(file_path)
    feedrate = extract_feedrate_from_gcode(file_path)
    
    # Update UI fields
    if tool_diameter is not None:
        tool_diameter_var.set(f"{tool_diameter:.3f}")
    
    if feedrate is not None:
        feedrate_var.set(f"{feedrate:.1f}")
    
    # Enable processing and show parameters
    process_button.config(state="normal")
    param_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 0))
    
    # Calculate initial values
    calculate_passes_and_angular_displacement()

def save_output_file():
    """Handle output file selection"""
    initial_file = output_path_var.get()
    file_path = filedialog.asksaveasfilename(
        defaultextension=".nc",
        filetypes=[("G-Code Files", "*.nc *.gcode *.ngc *.tap"), ("All Files", "*.*")],
        initialfile=os.path.basename(initial_file),
        title="Save Modified G-Code As"
    )
    
    if file_path:
        output_path_var.set(file_path)
        file_name = os.path.basename(file_path)
        output_label.config(text=file_name)

def process_file():
    """Process G-code with new indexing logic"""
    try:
        # Get parameters
        input_file = file_path_var.get()
        output_file = output_path_var.get()
        stock_diameter = float(stock_diameter_var.get())
        tool_diameter = float(tool_diameter_var.get())
        
        # Validate inputs
        if stock_diameter <= 0:
            messagebox.showerror("Error", "Stock diameter must be positive")
            return
        
        if tool_diameter <= 0:
            messagebox.showerror("Error", "Tool diameter must be positive")
            return
        
        if tool_diameter >= stock_diameter/2:
            messagebox.showerror("Error", "Tool diameter too large for stock")
            return
        
        # Update status
        status_var.set("Processing...")
        root.update_idletasks()
        
        # Get calculated values
        num_passes, angular_displacement = calculate_passes_and_angular_displacement()
        if num_passes is None:
            return
        
        # Modify G-code
        result_file = modify_gcode(input_file, output_file, stock_diameter, tool_diameter, num_passes, angular_displacement)
        
        if result_file:
            status_var.set("Processing complete! Generating visualizations...")
            root.update_idletasks()
            
            # Generate visualizations
            add_visualization_to_ui(main_frame, input_file, output_file)
            
            status_var.set("Conversion and visualization complete!")
            messagebox.showinfo("Success", f"Rotary G-code saved to:\n{result_file}\n\nPasses: {num_passes}\nAngular step: {angular_displacement:.2f}°")
        
    except ValueError as e:
        status_var.set("Error: Invalid values")
        messagebox.showerror("Error", f"Invalid numeric values:\n{str(e)}")
    except Exception as e:
        status_var.set("Error occurred")
        messagebox.showerror("Error", f"Processing error:\n{str(e)}")

def add_visualization_to_ui(main_frame, input_file, output_file=None):
    # Extract points
    all_points = extract_xz_from_gcode(input_file)

    if not all_points:
        tk.messagebox.showerror("Visualization Error", "No valid X-Z points found in the G-code file.")
        return

    x_coords, z_coords = zip(*all_points)
    min_z = min(z_coords)
    z_coords_shifted = [z - min_z for z in z_coords]

    # 2D TOOLPATH PLOT
    fig_2d, ax_2d = plt.subplots(figsize=(8, 5), dpi=100)
    fig_2d.suptitle("Toolpath Visualization", fontsize=12)
    ax_2d.plot(x_coords, z_coords_shifted, color=accent_color, linewidth=2, label="Toolpath")
    ax_2d.scatter(x_coords, z_coords_shifted, color=accent_color, s=15, alpha=0.7)
    ax_2d.axhline(y=0, color='red', linestyle='--', linewidth=2, label="Z Rotation Axis")
    ax_2d.set_xlabel("X Axis (Length)")
    ax_2d.set_ylabel("Z Axis (Radius)")
    ax_2d.grid(True, alpha=0.3)
    ax_2d.legend()
    fig_2d.tight_layout()
    fig_2d.show()

    # 3D MODEL PLOT (Popup) 
    fig_3d = plt.figure(figsize=(8, 5), dpi=100)
    ax_3d = fig_3d.add_subplot(111, projection='3d')
    fig_3d.suptitle("3D Part Visualization", fontsize=12)

    resolution = 80
    theta = np.linspace(0, 2 * np.pi, resolution)
    num_points = len(x_coords)

    x_surface = np.zeros((num_points, resolution))
    y_surface = np.zeros_like(x_surface)
    z_surface = np.zeros_like(x_surface)

    for i in range(num_points):
        x_surface[i, :] = x_coords[i]
        y_surface[i, :] = z_coords_shifted[i] * np.cos(theta)
        z_surface[i, :] = z_coords_shifted[i] * np.sin(theta)

    ax_3d.plot_surface(x_surface, y_surface, z_surface, color=accent_color, alpha=0.8, linewidth=0, antialiased=True)
    ax_3d.set_xlabel("X Axis (Length)")
    ax_3d.set_ylabel("Y Axis (Rotary)")
    ax_3d.set_zlabel("Z Axis (Radius)")
    ax_3d.view_init(elev=30, azim=45)
    ax_3d.grid(True, alpha=0.3)
    fig_3d.tight_layout()
    fig_3d.show()

    # Status update
    status_label = ttk.Label(main_frame, text="Visualization popups generated!", foreground="green", background=section_bg)
    status_label.grid(row=99, column=0, pady=10, padx=10, sticky="w")

    return

def create_tooltip(widget, text):
    """Create tooltip for widget"""
    def enter(event):
        x = y = 0
        x, y, _, _ = widget.bbox("insert")
        x += widget.winfo_rootx() + 25
        y += widget.winfo_rooty() + 25
        
        tooltip = tk.Toplevel(widget)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{x}+{y}")
        tooltip.configure(bg="#FFFFDD", bd=1, relief="solid")
        
        label = ttk.Label(tooltip, text=text, justify=tk.LEFT, background="#FFFFDD", relief="solid", borderwidth=0, wraplength=280)
        label.pack(ipadx=5, ipady=5)
        
        widget.tooltip = tooltip
        
    def leave(event):
        if hasattr(widget, "tooltip"):
            widget.tooltip.destroy()
    
    widget.bind("<Enter>", enter)
    widget.bind("<Leave>", leave)

def extract_xz_from_gcode(filename):
    """Extract X and Z coordinates from G-code file"""
    points = []
    
    try:
        with open(filename, 'r') as file:
            for line in file:
                line = line.strip()
                
                if not line or line.startswith(';') or line.startswith('('):
                    continue
                
                x_match = re.search(r'X(-?\d*\.?\d+)', line)
                z_match = re.search(r'Z(-?\d*\.?\d+)', line)
                
                if x_match and z_match:
                    x = float(x_match.group(1))
                    z = float(z_match.group(1))
                    points.append((x, z))
        
    except Exception as e:
        print(f"Error reading file: {e}")
    
    return points

def on_param_change(*args):
    """Update calculations when parameters change"""
    calculate_passes_and_angular_displacement()
    status_var.set("Ready to process")

def show_about():
    """Show about dialog"""
    about_window = tk.Toplevel(root)
    about_window.title("About CNC Rotary Axis Converter")
    about_window.geometry("500x400")
    about_window.resizable(False, False)
    about_window.transient(root)
    about_window.grab_set()
    
    about_frame = ttk.Frame(about_window, style="TFrame")
    about_frame.pack(fill="both", expand=True, padx=20, pady=20)
    
    app_title = ttk.Label(about_frame, text="CNC Rotary Axis Converter", style="Header.TLabel")
    app_title.pack(pady=(0, 5))
    
    version_text = ttk.Label(about_frame, text="Version 2.0.0", font=("Segoe UI", 10))
    version_text.pack(pady=(0, 15))
    
    credits_label = ttk.Label(about_frame, text="Credits", style="Subheader.TLabel")
    credits_label.pack(pady=(15, 5))
    
    credits_text = scrolledtext.ScrolledText(about_frame, wrap=tk.WORD, width=50, height=8, font=("Segoe UI", 10), background="#F5F5F5", borderwidth=1, relief="solid")
    credits_text.pack(pady=(5, 15), fill="both", expand=True)
    
    credits_content = """Algorithm for indexed rotary operations.

Features:
- Calculates optimal number of passes based on tool/stock diameter
- Uses angular indexing instead of continuous rotation
- Provides revolution geometry through controlled overlapping

This version creates multiple passes of the same toolpath with precise angular indexing to achieve complete revolution coverage.

Tool developed by Dr. Pedro Portugal (Algorithm Design) and Damian D. Venghaus (Web Deployment), © 2025."""
    credits_text.insert(tk.END, credits_content)
    credits_text.config(state="disabled")
    
    description_label = ttk.Label(about_frame, text="Converts X-Z G-code to indexed rotary operations with calculated passes and angular displacement.", wraplength=460, justify="center", font=("Segoe UI", 10))
    description_label.pack(pady=(0, 15))
    
    close_button = ttk.Button(about_frame, text="Close", command=about_window.destroy)
    close_button.pack(pady=(0, 10))

# Initialize main window
root = tk.Tk()
root.title("CNC Rotary Axis Converter")
root.geometry("640x750")
root.minsize(620, 730)

# Styling
style = ttk.Style()
style.theme_use("clam")

# Color scheme
bg_color = "#FFFFFF"
accent_color = "#0078D7"
text_color = "#333333"
heading_color = "#0078D7"
section_bg = "#F5F5F5"
button_bg = "#0078D7"
button_fg = "#FFFFFF"
entry_bg = "#FFFFFF"
status_bg = "#F0F0F0"

# Configure styles
style.configure("TFrame", background=bg_color)
style.configure("Section.TFrame", background=section_bg)
style.configure("TLabel", background=bg_color, foreground=text_color, font=("Segoe UI", 10))
style.configure("Header.TLabel", background=bg_color, foreground=heading_color, font=("Segoe UI", 14, "bold"))
style.configure("Subheader.TLabel", background=bg_color, foreground=heading_color, font=("Segoe UI", 12, "bold"))
style.configure("Status.TLabel", background=status_bg, foreground=text_color, font=("Segoe UI", 10))
style.configure("TButton", background=button_bg, foreground=button_fg, font=("Segoe UI", 10))
style.configure("TEntry", background=entry_bg, font=("Segoe UI", 10))

style.map("TButton", background=[("active", "#005BB5"), ("disabled", "#CCCCCC")], foreground=[("active", button_fg), ("disabled", "#888888")])

# Main frame
main_frame = ttk.Frame(root, style="TFrame")
main_frame.pack(fill="both", expand=True)

# Variables
file_path_var = tk.StringVar()
output_path_var = tk.StringVar()
stock_diameter_var = tk.StringVar(value="25.0")
tool_diameter_var = tk.StringVar(value="6.0")
feedrate_var = tk.StringVar(value="200.0")
num_passes_var = tk.StringVar(value="0")
angular_displacement_var = tk.StringVar(value="0.00")
status_var = tk.StringVar(value="Select a G-code file to begin")

# Trace parameter changes
stock_diameter_var.trace_add("write", on_param_change)
tool_diameter_var.trace_add("write", on_param_change)

# Header
header_frame = ttk.Frame(main_frame, style="TFrame")
header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
main_frame.grid_columnconfigure(0, weight=1)
header_frame.columnconfigure(0, weight=1)

title_label = ttk.Label(header_frame, text="CNC Rotary Axis G-Code Converter", style="Header.TLabel")
title_label.grid(row=0, column=0, sticky="w")

credits_button = ttk.Button(header_frame, text="About", command=show_about)
credits_button.grid(row=0, column=1, sticky="e")

subtitle_label = ttk.Label(header_frame, text="Convert X-Z G-code to indexed rotary operations", font=("Segoe UI", 10))
subtitle_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))

# File selection
file_frame = ttk.Frame(main_frame, style="Section.TFrame")
file_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(10, 0))

file_section_label = ttk.Label(file_frame, text="File Selection", style="Subheader.TLabel", background=section_bg)
file_section_label.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

input_file_frame = ttk.Frame(file_frame, style="Section.TFrame")
input_file_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
input_file_frame.columnconfigure(1, weight=1)

input_label = ttk.Label(input_file_frame, text="Input:", background=section_bg)
input_label.grid(row=0, column=0, sticky="w")

browse_button = ttk.Button(input_file_frame, text="Select G-Code File", command=select_file)
browse_button.grid(row=0, column=1, sticky="w", padx=(5, 0))

file_label = ttk.Label(input_file_frame, text="No file selected", background=section_bg)
file_label.grid(row=0, column=2, sticky="w", padx=(10, 0))

output_file_frame = ttk.Frame(file_frame, style="Section.TFrame")
output_file_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
output_file_frame.columnconfigure(1, weight=1)

output_text = ttk.Label(output_file_frame, text="Output:", background=section_bg)
output_text.grid(row=0, column=0, sticky="w")

save_button = ttk.Button(output_file_frame, text="Save As...", command=save_output_file)
save_button.grid(row=0, column=1, sticky="w", padx=(5, 0))

output_label = ttk.Label(output_file_frame, text="Not set", background=section_bg)
output_label.grid(row=0, column=2, sticky="w", padx=(10, 0))

# Parameters section
param_frame = ttk.Frame(main_frame, style="Section.TFrame")

param_section_label = ttk.Label(param_frame, text="Conversion Parameters", style="Subheader.TLabel", background=section_bg)
param_section_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 5))

# Stock parameters
stock_frame = ttk.Frame(param_frame, style="Section.TFrame")
stock_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
stock_frame.columnconfigure(1, weight=1)

stock_diameter_label = ttk.Label(stock_frame, text="Stock Diameter (mm):", background=section_bg)
stock_diameter_label.grid(row=0, column=0, sticky="w", pady=5)

stock_diameter_entry = ttk.Entry(stock_frame, textvariable=stock_diameter_var, width=10)
stock_diameter_entry.grid(row=0, column=1, sticky="w", pady=5)
create_tooltip(stock_diameter_entry, "Diameter of cylindrical stock material")

tool_diameter_label = ttk.Label(stock_frame, text="Tool Diameter (mm):", background=section_bg)
tool_diameter_label.grid(row=1, column=0, sticky="w", pady=5)

tool_diameter_entry = ttk.Entry(stock_frame, textvariable=tool_diameter_var, width=10)
tool_diameter_entry.grid(row=1, column=1, sticky="w", pady=5)
create_tooltip(tool_diameter_entry, "Diameter of cutting tool")

# Calculated values display
calc_frame = ttk.Frame(param_frame, style="Section.TFrame")
calc_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
calc_frame.columnconfigure(1, weight=1)

passes_label = ttk.Label(calc_frame, text="Calculated Passes:", background=section_bg)
passes_label.grid(row=0, column=0, sticky="w", pady=5)

passes_display = ttk.Label(calc_frame, textvariable=num_passes_var, background=section_bg, foreground=accent_color, font=("Segoe UI", 10, "bold"))
passes_display.grid(row=0, column=1, sticky="w", pady=5)

angular_label = ttk.Label(calc_frame, text="Angular Step (degrees):", background=section_bg)
angular_label.grid(row=1, column=0, sticky="w", pady=5)

angular_display = ttk.Label(calc_frame, textvariable=angular_displacement_var, background=section_bg, foreground=accent_color, font=("Segoe UI", 10, "bold"))
angular_display.grid(row=1, column=1, sticky="w", pady=5)

# Process button
process_frame = ttk.Frame(main_frame, style="TFrame")
process_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(20, 10))

process_button = ttk.Button(process_frame, text="Process G-Code", command=process_file, state="disabled")
process_button.pack(pady=5)

# Status
status_frame = ttk.Frame(main_frame, style="TFrame")
status_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 10))

status_label = ttk.Label(status_frame, textvariable=status_var, style="Status.TLabel")
status_label.pack(fill="x", pady=5)

# Help section
help_frame = ttk.Frame(main_frame, style="TFrame")
help_frame.grid(row=5, column=0, sticky="ew", padx=20, pady=(10, 20))

help_label = ttk.Label(help_frame, text="About Indexed Rotary Operations", style="Subheader.TLabel")
help_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

help_content = scrolledtext.ScrolledText(help_frame, wrap=tk.WORD, width=40, height=8, font=("Segoe UI", 9), background="#E8F0F8", borderwidth=1, relief="solid")
help_content.grid(row=1, column=0, sticky="ew")
help_frame.columnconfigure(0, weight=1)

help_text = """This tool converts X-Z G-code into indexed rotary operations by calculating optimal passes and angular displacement.

IMPORTANT - GRBL CALIBRATION REQUIRED:
This code assumes 1 Y-unit = 1 degree rotation. Configure GRBL:
$101 = (motor_steps/rev × microsteps × gear_ratio) / 360
Example: 200×16×3:1 ratio = $101=26.67 steps/degree

Logic:
- Calculates toolpath diameter based on stock and tool dimensions  
- Determines number of passes needed for complete revolution
- Uses angular indexing with safe retraction between passes
- Each pass includes spindle stop/start for safe indexing

Safety Features:
- Automatic Z-retraction before indexing
- Spindle stop during rotary movement
- Safe restart sequence for each pass

Benefits:
- More predictable results than continuous rotation
- Better surface finish through controlled overlapping
- Safe indexing with retraction sequences
- Compatible with calibrated GRBL controllers

The algorithm calculates: toolpath_diameter = stock_diameter - (2 × tool_diameter)
Number of passes = Pi × toolpath_diameter / (tool_diameter × overlap_factor)
Angular step = 360° / number_of_passes

This ensures complete coverage with optimal tool engagement and safe indexing."""

help_content.insert(tk.END, help_text)
help_content.config(state="disabled")

# Footer
footer_frame = ttk.Frame(main_frame, style="TFrame")
footer_frame.grid(row=6, column=0, sticky="ew", padx=20, pady=(0, 10))
footer_frame.columnconfigure(0, weight=1)

version_label = ttk.Label(footer_frame, text="v2.0.0", foreground="#888888", background=bg_color)
version_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

developer_label = ttk.Label(footer_frame, text="Indexed Rotary Operations", foreground="#888888", background=bg_color)
developer_label.grid(row=0, column=1, sticky="e", pady=(0, 5))

root.mainloop()