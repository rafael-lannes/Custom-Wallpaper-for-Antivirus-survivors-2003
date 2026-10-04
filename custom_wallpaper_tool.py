import os
import sys
import struct
import io
import hashlib
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk

# Default Steam game installation path
DEFAULT_GAME_DIR = r"F:\Arquivos de Programas\Steam\steamapps\common\Antivirus Survivors 2003 Professional"
TARGET_PCK_NAME = "AVS03Pro.pck"
BACKUP_PCK_NAME = "AVS03Pro.pck.bak"

def generate_wallpaper_ctex(pil_img: Image.Image) -> bytes:
    """
    Converts a PIL Image into Godot 4.7.1 WebP CompressedTexture2D (GST2)
    with full mipmap chain matching the original Antivirus Survivors 2003 texture format.
    """
    resized = pil_img.convert("RGB").resize((768, 480), Image.Resampling.LANCZOS)
    expected_sizes = [
        (768, 480), (384, 240), (192, 120), (96, 60), (48, 30),
        (24, 15), (12, 7), (6, 3), (3, 1), (1, 1)
    ]
    mip_data = []
    for w, h in expected_sizes:
        mip_img = resized.resize((w, h), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        mip_img.save(buf, format="WEBP", lossless=True)
        mip_data.append(buf.getvalue())

    # Godot 4 CTEX Header (GST2)
    magic = b"GST2"
    version = 1
    w = 768
    h = 480
    flags = 0x09800000
    fmt = 0xffffffff
    reserved = b"\x00" * 12
    fmt2 = 2
    dim_packed_w = 768
    dim_packed_h = 480
    mip_count = 9
    comp_mode = 5
    first_chunk_sz = len(mip_data[0])

    header = struct.pack(
        "<4sIIIII12sIHHIII",
        magic, version, w, h, flags, fmt, reserved,
        fmt2, dim_packed_w, dim_packed_h, mip_count, comp_mode, first_chunk_sz
    )

    out = bytearray(header)
    out.extend(mip_data[0])
    for i in range(1, len(mip_data)):
        sz = len(mip_data[i])
        out.extend(struct.pack("<I", sz))
        out.extend(mip_data[i])

    return bytes(out)

def apply_wallpaper_patch(pck_path: str, image_path: str) -> None:
    # 1. Ensure backup of original PCK exists
    bak_path = pck_path + ".bak"
    if not os.path.exists(bak_path):
        shutil.copy2(pck_path, bak_path)

    # 2. Convert user image to Godot CTEX
    with Image.open(image_path) as img:
        new_ctex = generate_wallpaper_ctex(img)

    with open(pck_path, "r+b") as f:
        # Read file_base and dir_offset from PCK header
        f.seek(24)
        file_base = struct.unpack("<Q", f.read(8))[0]
        dir_offset = struct.unpack("<Q", f.read(8))[0]

        # Read directory table at absolute dir_offset
        f.seek(dir_offset)
        file_count = struct.unpack("<I", f.read(4))[0]

        entries = []
        target_entry_idx = -1
        for i in range(file_count):
            nl = struct.unpack("<I", f.read(4))[0]
            raw_name = f.read(nl)
            off, sz = struct.unpack("<QQ", f.read(16))
            md5 = f.read(16)
            flags = struct.unpack("<I", f.read(4))[0]
            entry = {
                "nl": nl,
                "name": raw_name,
                "off": off,
                "sz": sz,
                "md5": md5,
                "flags": flags
            }
            if b"treebliss.png-" in raw_name:
                target_entry_idx = i
            entries.append(entry)

        if target_entry_idx == -1:
            raise RuntimeError("Initial wallpaper texture ('treebliss') was not found inside the game package.")

        # Write new CTEX at current dir_offset
        new_data_abs_offset = dir_offset
        new_data_rel_offset = new_data_abs_offset - file_base

        f.seek(new_data_abs_offset)
        f.write(new_ctex)

        pad = (4 - (len(new_ctex) % 4)) % 4
        if pad > 0:
            f.write(b"\x00" * pad)

        # Update entry
        entries[target_entry_idx]["off"] = new_data_rel_offset
        entries[target_entry_idx]["sz"] = len(new_ctex)
        entries[target_entry_idx]["md5"] = hashlib.md5(new_ctex).digest()

        # Write updated directory table right after new data + padding
        new_dir_abs_offset = new_data_abs_offset + len(new_ctex) + pad
        f.seek(new_dir_abs_offset)
        f.write(struct.pack("<I", len(entries)))
        for e in entries:
            f.write(struct.pack("<I", e["nl"]))
            f.write(e["name"])
            f.write(struct.pack("<QQ", e["off"], e["sz"]))
            f.write(e["md5"])
            f.write(struct.pack("<I", e["flags"]))

        # Update dir_offset pointer in PCK header (offset 32)
        f.seek(32)
        f.write(struct.pack("<Q", new_dir_abs_offset))
        f.flush()

def restore_backup(pck_path: str) -> bool:
    bak_path = pck_path + ".bak"
    if os.path.exists(bak_path):
        shutil.copy2(bak_path, pck_path)
        return True
    return False

class CustomWallpaperApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Custom Wallpaper for Antivirus Survivors 2003")
        self.root.geometry("640x590")
        self.root.resizable(False, False)

        # Classic Windows XP / 2003 retro appearance
        self.bg_color = "#ECE9D8"
        self.root.configure(bg=self.bg_color)

        self.game_pck_path = os.path.join(DEFAULT_GAME_DIR, TARGET_PCK_NAME)
        self.selected_image_path = None
        self.preview_image_tk = None

        self._build_ui()

    def _build_ui(self):
        # Header banner
        title_frame = tk.Frame(self.root, bg="#0A246A", padx=12, pady=8)
        title_frame.pack(fill="x")

        title_lbl = tk.Label(
            title_frame,
            text="Custom Wallpaper for Antivirus Survivors 2003",
            font=("Segoe UI", 12, "bold"),
            fg="white",
            bg="#0A246A"
        )
        title_lbl.pack(anchor="w")

        sub_frame = tk.Frame(title_frame, bg="#0A246A")
        sub_frame.pack(fill="x")

        subtitle_lbl = tk.Label(
            sub_frame,
            text="Home Screen & Default Profile Wallpaper Replacer",
            font=("Segoe UI", 8),
            fg="#DCE6F5",
            bg="#0A246A"
        )
        subtitle_lbl.pack(side="left")

        credits_lbl = tk.Label(
            sub_frame,
            text="Created by Ranesu",
            font=("Segoe UI", 8, "bold"),
            fg="#FFD700",
            bg="#0A246A"
        )
        credits_lbl.pack(side="right")

        # Content container
        content_frame = tk.Frame(self.root, bg=self.bg_color, padx=16, pady=10)
        content_frame.pack(fill="both", expand=True)

        # Game PCK file section
        pck_box = tk.LabelFrame(content_frame, text=" Game Package File (.pck) ", bg=self.bg_color, font=("Segoe UI", 9, "bold"))
        pck_box.pack(fill="x", pady=6)

        self.pck_entry = tk.Entry(pck_box, font=("Segoe UI", 9))
        self.pck_entry.insert(0, self.game_pck_path)
        self.pck_entry.pack(side="left", fill="x", expand=True, padx=8, pady=8)

        btn_browse_pck = tk.Button(pck_box, text="Browse...", command=self.on_browse_pck, width=10)
        btn_browse_pck.pack(side="right", padx=8, pady=8)

        # Image selection section
        img_box = tk.LabelFrame(content_frame, text=" Select Custom Wallpaper Image ", bg=self.bg_color, font=("Segoe UI", 9, "bold"))
        img_box.pack(fill="x", pady=6)

        self.img_entry = tk.Entry(img_box, font=("Segoe UI", 9))
        self.img_entry.pack(side="left", fill="x", expand=True, padx=8, pady=8)

        btn_browse_img = tk.Button(img_box, text="Choose...", command=self.on_browse_image, width=10)
        btn_browse_img.pack(side="right", padx=8, pady=8)

        # Image preview
        preview_box = tk.LabelFrame(content_frame, text=" Wallpaper Preview (768x480 aspect ratio) ", bg=self.bg_color, font=("Segoe UI", 9, "bold"))
        preview_box.pack(fill="both", expand=True, pady=6)

        self.preview_canvas = tk.Label(
            preview_box,
            text="No image selected\n(Click 'Choose...' above to select an image)",
            bg="#3A6EA5",
            fg="white",
            font=("Segoe UI", 10)
        )
        self.preview_canvas.pack(fill="both", expand=True, padx=8, pady=8)

        # Action bar
        action_frame = tk.Frame(self.root, bg=self.bg_color, padx=16, pady=10)
        action_frame.pack(fill="x")

        btn_restore = tk.Button(
            action_frame,
            text="Restore Original (Backup)",
            command=self.on_restore_original,
            font=("Segoe UI", 9),
            padx=10,
            pady=4
        )
        btn_restore.pack(side="left")

        self.btn_apply = tk.Button(
            action_frame,
            text="✓ Apply Wallpaper to Game",
            command=self.on_apply_wallpaper,
            font=("Segoe UI", 10, "bold"),
            bg="#2B78E4",
            fg="white",
            activebackground="#1C5AB8",
            activeforeground="white",
            padx=16,
            pady=4
        )
        self.btn_apply.pack(side="right")

    def on_browse_pck(self):
        selected = filedialog.askopenfilename(
            title="Locate game AVS03Pro.pck file",
            filetypes=[("Godot PCK", "*.pck"), ("All Files", "*.*")],
            initialdir=os.path.dirname(self.pck_entry.get()) if os.path.exists(self.pck_entry.get()) else "C:\\"
        )
        if selected:
            self.pck_entry.delete(0, tk.END)
            self.pck_entry.insert(0, selected)

    def on_browse_image(self):
        selected = filedialog.askopenfilename(
            title="Select Wallpaper Image",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.webp"), ("All Files", "*.*")]
        )
        if selected:
            self.img_entry.delete(0, tk.END)
            self.img_entry.insert(0, selected)
            self.selected_image_path = selected
            self.update_preview(selected)

    def update_preview(self, img_path: str):
        try:
            with Image.open(img_path) as img:
                thumb = img.convert("RGB").resize((384, 240), Image.Resampling.LANCZOS)
                self.preview_image_tk = ImageTk.PhotoImage(thumb)
                self.preview_canvas.configure(image=self.preview_image_tk, text="")
        except Exception as e:
            messagebox.showerror("Image Error", f"Could not open the selected image:\n{e}")

    def on_apply_wallpaper(self):
        pck_path = self.pck_entry.get().strip()
        img_path = self.img_entry.get().strip()

        if not os.path.isfile(pck_path):
            messagebox.showerror("File Not Found", f"Game PCK package was not found at:\n{pck_path}")
            return

        if not os.path.isfile(img_path):
            messagebox.showwarning("Select Image", "Please select a valid image file first.")
            return

        try:
            self.btn_apply.configure(text="Applying...", state="disabled")
            self.root.update()

            apply_wallpaper_patch(pck_path, img_path)

            messagebox.showinfo(
                "Success!",
                "Custom wallpaper applied successfully!\n\n"
                "Launch 'Antivirus Survivors 2003 Professional' to enjoy your new wallpaper on the desktop screen."
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply wallpaper:\n{e}")
        finally:
            self.btn_apply.configure(text="✓ Apply Wallpaper to Game", state="normal")

    def on_restore_original(self):
        pck_path = self.pck_entry.get().strip()
        if not os.path.isfile(pck_path + ".bak"):
            messagebox.showwarning("Backup Not Found", "No backup file (.pck.bak) was found to restore from.")
            return

        confirm = messagebox.askyesno(
            "Confirm Restore",
            "Do you want to restore the original game file from backup?"
        )
        if confirm:
            if restore_backup(pck_path):
                messagebox.showinfo("Restored", "Original game package restored successfully!")
            else:
                messagebox.showerror("Error", "Failed to restore backup.")

def main():
    root = tk.Tk()
    app = CustomWallpaperApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
