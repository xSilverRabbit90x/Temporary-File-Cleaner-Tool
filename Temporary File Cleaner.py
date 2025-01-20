import os
import ctypes
import tkinter as tk
from tkinter import messagebox
import shutil
import psutil
import time
import threading
import pystray
from pystray import MenuItem, Icon
from PIL import Image, ImageDraw

# Function to forcefully remove files 
def force_remove(file_path):
    try:
        ctypes.windll.kernel32.DeleteFileW(file_path)
    except Exception as e:
        print(f"Error while forcefully removing {file_path}: {e}")

# Function to close processes using the specified file
def close_process_using_file(file_path):
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for item in proc.open_files():
                if item.path == file_path:
                    proc.terminate()
                    proc.wait()
                    print(f"Process {proc.name()} (PID: {proc.pid}) closed.")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

# Function to clean temporary files in a specified directory
def clean_temp(directory, force_delete=False):
    non_deleted_files = []
    try:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                try:
                    if os.path.isfile(file_path):
                        if force_delete:
                            os.chmod(file_path, 0o777)
                        os.remove(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception:
                    non_deleted_files.append(file_path)
                    if force_delete:
                        close_process_using_file(file_path)
                        force_remove(file_path)
                        try:
                            os.remove(file_path)
                        except Exception:
                            non_deleted_files.append(file_path)

            return True, non_deleted_files
        else:
            return False, ["The folder does not exist."]
    except Exception as e:
        return False, [f"An error occurred during cleanup: {e}"]

# Function to clean user temporary files
def clean_user_temp(force_delete):
    user_temp_dir = os.path.join(os.getenv('LOCALAPPDATA'), 'Temp')
    return clean_temp(user_temp_dir, force_delete)

# Function to clean Windows temporary files
def clean_windows_temp(force_delete):
    windows_temp_dir = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'Temp')
    return clean_temp(windows_temp_dir, force_delete)

class AutomaticCleaner:
    def __init__(self, root):
        self.root = root
        self.root.configure(bg="#f0f0f0")
        self.force_delete_var = tk.BooleanVar()
        self.interval_var = tk.StringVar()
        self.interval_var.set("5 min")  # Default setting

        self.success_message_var = tk.BooleanVar(value=False)  # Set to False by default

        self.title_label = tk.Label(root, text="Temporary File Cleaner", font=('Helvetica', 18, 'bold'), bg="#f0f0f0", fg="#333")
        self.title_label.pack(pady=10)

        self.countdown_label = tk.Label(root, text="", font=('Helvetica', 14), bg="#f0f0f0", fg="#555")
        self.countdown_label.pack(pady=10)

        self.force_delete_checkbox = tk.Checkbutton(root, text="Force file deletion", variable=self.force_delete_var, bg="#f0f0f0", fg="#333", font=('Helvetica', 12))
        self.force_delete_checkbox.pack(pady=5)

        self.interval_label = tk.Label(root, text="Cleanup interval:", font=('Helvetica', 12), bg="#f0f0f0", fg="#333")
        self.interval_label.pack()
        self.interval_option = tk.OptionMenu(root, self.interval_var, "5 seconds", "30 seconds", "1 minute", "5 min", "30 min", "1 hour", "2 hours", "3 hours", "5 hours")
        self.interval_option.config(bg="#e0e0e0", font=('Helvetica', 12))
        self.interval_option.pack(pady=5)

        self.start_cleaning_button = tk.Button(root, text="Start/Stop Automatic Cleaning", command=self.start_or_stop_cleaning, bg="#0078D7", fg="white", font=('Helvetica', 12), relief="groove")
        self.start_cleaning_button.pack(pady=10)

        self.minimize_and_start_button = tk.Button(root, text="Minimize and Start Automatic Cleaning", command=self.minimize_and_start, bg="#0078D7", fg="white", font=('Helvetica', 12), relief="groove")
        self.minimize_and_start_button.pack(pady=10)

        self.success_message_checkbox = tk.Checkbutton(root, text="Enable success message", variable=self.success_message_var, bg="#f0f0f0", fg="#333", font=('Helvetica', 12))
        self.success_message_checkbox.pack(pady=5)

        self.clean_user_temp_button = tk.Button(root, text="Clean user temporary files", command=lambda: self.clean_temp_user(), bg="#28a745", fg="white", font=('Helvetica', 12), relief="groove")
        self.clean_user_temp_button.pack(pady=10)

        self.clean_windows_temp_button = tk.Button(root, text="Clean Windows temporary files", command=lambda: self.clean_temp_windows(), bg="#28a745", fg="white", font=('Helvetica', 12), relief="groove")
        self.clean_windows_temp_button.pack(pady=10)

        self.cleaning_in_progress = False
        self.tray_icon = None
        self.tray_thread = None  # Added to manage the tray icon thread

    def clean_temp_user(self):
        user_temp_success, user_temp_errors = clean_user_temp(self.force_delete_var.get())
        self.show_message(user_temp_success, user_temp_errors)

    def clean_temp_windows(self):
        windows_temp_success, windows_temp_errors = clean_windows_temp(self.force_delete_var.get())
        self.show_message(False, windows_temp_errors)

    def start_cleaning(self):
        self.cleaning_in_progress = True
        self.start_cleaning_button['text'] = "Stop Automatic Cleaning"
        threading.Thread(target=self.start_cleanup_loop, daemon=True).start()

    def start_or_stop_cleaning(self):
        if self.cleaning_in_progress:
            self.stop_automatic_cleaning()
            self.start_cleaning_button['text'] = "Start/Stop Automatic Cleaning"
        else:
            self.start_cleaning()

    def stop_automatic_cleaning(self):
        self.cleaning_in_progress = False
        self.countdown_label['text'] = "Automatic cleaning interrupted."
        self.reset_label()

    def reset_label(self):
        self.countdown_label['text'] = ""

    def start_cleanup_loop(self):
        while self.cleaning_in_progress:
            self.trigger_cleanup()
            time.sleep(self.get_selected_time())

    def trigger_cleanup(self):
        self.countdown_label['text'] = "Cleaning in progress..."
        user_temp_success, user_temp_errors = clean_user_temp(self.force_delete_var.get())
        windows_temp_success, windows_temp_errors = clean_windows_temp(self.force_delete_var.get())

        if self.success_message_var.get():
            self.show_message(user_temp_success, user_temp_errors + windows_temp_errors)

        self.countdown_label['text'] = "Cleaning completed!"
        time.sleep(2)

    def show_message(self, success, errors):
        if success or errors:
            message = "Cleaning completed successfully!"
            if errors:
                message += "\nErrors during cleaning:\n" + "\n".join(errors)
            messagebox.showinfo("Completed", message)
        else:
            messagebox.showinfo("Completed", "No files to clean.")

    def minimize_and_start(self):
        self.root.withdraw()  # Minimize the window
        threading.Thread(target=self.start_cleanup_in_tray, daemon=True).start()  # Run in a separate thread

    def start_cleanup_in_tray(self):
        self.start_cleaning()  # Start cleaning
        self.show_tray_icon()  # Show the tray icon

    def get_selected_time(self):
        interval = self.interval_var.get()
        times = {
            "5 seconds": 5,
            "30 seconds": 30,
            "1 minute": 60,
            "5 min": 300,
            "30 min": 1800,
            "1 hour": 3600,
            "2 hours": 7200,
            "3 hours": 10800,
            "5 hours": 18000
        }
        return times.get(interval, 300)  # Fallback to 5 min if not found

    def show_tray_icon(self):
        if self.tray_icon is None:
            image = Image.new('RGB', (64, 64), (255, 255, 255))
            dc = ImageDraw.Draw(image)
            dc.ellipse((16, 16, 48, 48), fill=(0, 128, 255))
            self.tray_icon = Icon("Cleaner", image)
            self.tray_icon.menu = pystray.Menu(
                MenuItem("Show", self.restore_window),
                MenuItem("Exit", self.exit_app)  # Ensure exit_app is a callable for the menu item
            )
            self.tray_icon.run(setup)

    def restore_window(self, icon):
        icon.stop()
        self.root.deiconify()

    def exit_app(self, icon=None):
        if icon:
            icon.stop()
        self.cleaning_in_progress = False  # Stop cleaning
        self.root.quit()  # Close the application

def setup(icon):
    icon.visible = True

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Temporary File Cleaner")
    root.geometry("400x600")
    cleaner = AutomaticCleaner(root)

    root.protocol("WM_DELETE_WINDOW", lambda: cleaner.exit_app())
    root.bind("<Unmap>", lambda event: cleaner.minimize_and_start() if root.state() == "iconic" else None)

    root.mainloop()
