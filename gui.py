import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.filedialog import asksaveasfilename
from PIL import Image, ImageTk
import pywinstyles
import threading
import requests
import sv_ttk
import json
import sys
import os

CONFIG_FILE = "config.json"
API_URL = "http://127.0.0.1:8000/generate-quote-image/"

def start_api():
    threading.Thread(target=lambda: os.system('uvicorn main:app --reload'), daemon=True).start()


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"authors": {}, "fonts": []}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

def apply_theme_to_titlebar(root):
    version = sys.getwindowsversion()

    if version.major == 10 and version.build >= 22000:
        pywinstyles.change_header_color(root, "#1c1c1c" if sv_ttk.get_theme() == "dark" else "#fafafa")
    elif version.major == 10:
        pywinstyles.apply_style(root, "dark" if sv_ttk.get_theme() == "dark" else "normal")

        # A hacky way to update the title bar's color on Windows 10 (it doesn't update instantly like on Windows 11)
        root.wm_attributes("-alpha", 0.99)
        root.wm_attributes("-alpha", 1)

class QuoteGeneratorApp:
    def __init__(self, root):
        self.action_button = None
        self.last_inputs = None
        self.save_image = None
        self.last_generated_image = None
        self.font_dropdown = None
        self.author_dropdown = None
        self.quote_entry = None
        self.submit_button = None
        self.image_label = None
        self.save_button = None
        self.generated_image_path = None

        self.config = load_config()
        self.root = root
        self.root.title("Quote Image Generator")
        self.root.resizable(False, False)

        self.quote_var = tk.StringVar()
        self.author_var = tk.StringVar()
        self.selected_font = tk.StringVar()
        self.selected_author = tk.StringVar()
        self.quote_font_size = tk.IntVar(value=48)
        self.author_font_size = tk.IntVar(value=40)

        self.build_ui()

    def build_ui(self):
        sidebar_frame = ttk.Frame(self.root, padding=10)
        sidebar_frame.grid(row=0, column=0, sticky="nesw")
        image_frame = ttk.Frame(self.root, padding=10)
        image_frame.grid(row=0, column=1, sticky="nesw")

        ttk.Label(sidebar_frame, text="Quote:").pack(anchor="w")
        self.quote_entry = tk.Text(sidebar_frame, height=4, width=20)
        self.quote_entry.pack(fill="x", pady=5)

        ttk.Label(sidebar_frame, text="Author:").pack(anchor="w")
        self.author_dropdown = ttk.Combobox(sidebar_frame, textvariable=self.selected_author)
        self.author_dropdown['values'] = list(self.config["authors"].keys())
        self.author_dropdown.pack(fill="x", pady=5)

        ttk.Label(sidebar_frame, text="Quote font size:").pack(anchor="w")
        ttk.Spinbox(sidebar_frame, from_=10, to=100, textvariable=self.quote_font_size).pack(fill="x", pady=5)

        ttk.Label(sidebar_frame, text="Author font size:").pack(anchor="w")
        ttk.Spinbox(sidebar_frame, from_=10, to=100, textvariable=self.author_font_size).pack(fill="x", pady=5)

        ttk.Label(sidebar_frame, text="Font file:").pack(anchor="w")
        self.font_dropdown = ttk.Combobox(sidebar_frame, textvariable=self.selected_font)
        self.font_dropdown['values'] = self.config["fonts"]
        self.font_dropdown.pack(fill="x", pady=5)

        ttk.Button(sidebar_frame, text="Select background image", command=self.select_background).pack(fill="x", pady=5)
        ttk.Button(sidebar_frame, text="Add font file", command=self.select_font).pack(fill="x", pady=(5, 0))

        self.action_button = ttk.Button(image_frame, text="Generate/Save Image", command=self.send_request)
        self.action_button.pack(fill="x", pady=5)

        self.image_label = ttk.Label(image_frame)
        self.image_label.pack(pady=(10, 0))

        if len(self.config["authors"]) > 0:
            self.author_dropdown.current(0)

        if len(self.config["fonts"]) > 0:
            self.font_dropdown.current(0)

        if os.path.isfile("last_result.png"):
            self.display_image('last_result.png')

    def select_background(self):
        path = filedialog.askopenfilename(title="Choose background image", filetypes=[("PNG", "*.png")])
        if path:
            author = self.selected_author.get()
            if not author:
                messagebox.showwarning("Author missing", "Please enter or select an author first.")
                return
            self.config["authors"][author] = {"background": path}
            self.update_dropdowns()
            save_config(self.config)

    def select_font(self):
        path = filedialog.askopenfilename(title="Choose font file", filetypes=[("TTF", "*.ttf")])
        if path and path not in self.config["fonts"]:
            self.config["fonts"].append(path)
            self.update_dropdowns()
            save_config(self.config)

    def update_dropdowns(self):
        self.author_dropdown['values'] = list(self.config["authors"].keys())
        self.font_dropdown['values'] = self.config["fonts"]

    def current_input_signature(self):
        return {
            "quote": self.quote_entry.get("1.0", "end").strip(),
            "author": self.selected_author.get(),
            "font": self.selected_font.get(),
            "quote_font_size": self.quote_font_size.get(),
            "author_font_size": self.author_font_size.get(),
        }

    def inputs_match_last(self):
        return self.last_inputs == self.current_input_signature()

    def send_request(self):
        current_inputs = self.current_input_signature()
        if self.last_generated_image and self.inputs_match_last():
            self.save_image_dialog()
            return

        quote = current_inputs["quote"]
        author = current_inputs["author"]
        font = current_inputs["font"]

        if not all([quote, author, font]):
            messagebox.showerror("Input Error", "Please fill in all required fields.")
            return

        if author not in self.config["authors"]:
            messagebox.showerror("Missing Background", "No background image set for this author.")
            return

        files = {
            "quote": (None, quote),
            "author": (None, author),
            "quote_font_size": (None, str(current_inputs["quote_font_size"])),
            "author_font_size": (None, str(current_inputs["author_font_size"])),
            "quote_text_color": (None, "white"),
            "author_text_color": (None, "white"),
            "shadow_blur_radius": (None, "5"),
            "background_image": open(self.config["authors"][author]["background"], "rb"),
            "overlay_image": open("data/overlay.png", "rb"),
            "quote_font_file": open(font, "rb"),
            "author_font_file": open(font, "rb"),
        }

        try:
            response = requests.post(API_URL, files=files)
            if response.status_code == 200:
                self.generated_image_path = "last_result.png"
                with open(self.generated_image_path, "wb") as f:
                    f.write(response.content)

                self.last_generated_image = self.generated_image_path
                self.last_inputs = current_inputs
                self.display_image(self.generated_image_path)

                self.action_button.config(text="Generate/Save Image")
            else:
                messagebox.showerror("API Error", response.text)
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))

    def display_image(self, path):
        img = Image.open(path).resize((340, 340))
        tk_img = ImageTk.PhotoImage(img)
        self.image_label.configure(image=tk_img)
        self.image_label.image = tk_img

    def manual_save(self):
        filetypes = [("PNG Image", "*.png"), ("JPEG Image", "*.jpg"), ("WEBP Image", "*.webp")]
        save_path = asksaveasfilename(defaultextension=".png", filetypes=filetypes)
        if save_path:
            img = Image.open(self.generated_image_path)
            ext = os.path.splitext(save_path)[1].lstrip(".").upper()
            img.save(save_path, ext)
            messagebox.showinfo("Saved", f"Image saved to {save_path}")

    def regular_save(self):
        def save_with_filename():
            filename = entry.get().strip()
            if not filename:
                messagebox.showerror("Error", "Filename cannot be empty.")
                return
            win.destroy()

            quote = self.last_inputs["quote"]
            author = self.last_inputs["author"]
            output_name = filename.lower()

            directory = f'{os.getcwd()}\\output\\{author}\\{output_name}'
            os.makedirs(directory, exist_ok=True)

            for ext in ["png", "webp"]:
                save_path = f"{directory}\\{output_name}.{ext}"
                Image.open(self.generated_image_path).save(save_path, ext.upper())

            messagebox.showinfo("Saved", f"Image saved as:\n{output_name}.png & .webp\nin {directory}")

        win = tk.Toplevel(self.root)
        win.title("Enter Filename")
        win.geometry("300x130")
        win.grab_set()

        ttk.Label(win, text="Enter a filename for the image:").pack(pady=10)
        entry = ttk.Entry(win)
        entry.pack(fill="x", padx=20)
        entry.focus()

        ttk.Button(win, text="Save", command=save_with_filename).pack(pady=10)

    def save_image_dialog(self):
        if not self.generated_image_path:
            messagebox.showinfo("No Image", "Generate an image first.")
            return

        win = tk.Toplevel(self.root)
        win.title("Save Image")
        win.geometry("300x120")
        win.grab_set()

        ttk.Label(win, text="Choose how to save the image:").pack(pady=10)

        ttk.Button(win, text="Manual Save (choose format & name)", command=lambda: [self.manual_save(),
                                                                                    win.destroy()]).pack(fill="x", padx=20, pady=5)
        ttk.Button(win, text="Regular Save (auto name/folder)", command=lambda: [self.regular_save(),
                                                                                 win.destroy()]).pack(fill="x", padx=20)

if __name__ == "__main__":
    window = tk.Tk()
    app = QuoteGeneratorApp(window)
    apply_theme_to_titlebar(window)
    sv_ttk.set_theme("dark")
    window.mainloop()
