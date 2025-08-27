import tkinter as tk
from io import BytesIO
import requests
from PIL import Image, ImageTk
import tkinter.font as tkFont
import threading

# ----- Pokémon-Logik -----
def get_pokemon_data(name, level=100):
    try:
        url = f"https://pokeapi.co/api/v2/pokemon/{name.lower()}/"
        response = requests.get(url)
        if response.status_code != 200:
            return None
        data = response.json()
        types = [t["type"]["name"] for t in data["types"]]
        image_url = data["sprites"]["front_default"]
        img_data = requests.get(image_url).content if image_url else None
        moves = []
        for move in data["moves"]:
            for detail in move["version_group_details"]:
                if detail["version_group"]["name"] == "platinum" and \
                        detail["move_learn_method"]["name"] == "level-up":
                    if detail["level_learned_at"] <= level:
                        moves.append(move["move"]["name"])
        return {"name": data["name"], "types": types, "moves": moves, "image": img_data}
    except:
        return None

def get_type_relations(types):
    strengths = set()
    weaknesses = set()
    for t in types:
        try:
            data = requests.get(f"https://pokeapi.co/api/v2/type/{t}/").json()
            for s in data["damage_relations"]["double_damage_to"]:
                strengths.add(s["name"])
            for w in data["damage_relations"]["double_damage_from"]:
                weaknesses.add(w["name"])
        except:
            continue
    return list(strengths), list(weaknesses)

# ----- GUI -----
root = tk.Tk()
root.title("Pokémon Team Info")
root.geometry("1200x800")
root.configure(bg="#333333")

root.rowconfigure(0, weight=1)
root.columnconfigure(0, weight=1)

team_container = tk.Frame(root, bg="#333333")
team_container.grid(row=0, column=0, sticky="nsew")

for r in range(2):
    team_container.rowconfigure(r, weight=1)
for c in range(3):
    team_container.columnconfigure(c, weight=1)

team_frames = []
img_labels = []
name_entries = []
level_entries = []
stats_labels = []
team_data = [None] * 6

resize_job = None  # Debounce-Job

# ----- Hilfsfunktionen -----
def _derive_slot_colors(widget, lift=0.08, border_delta=0.18):
    base_bg = widget.cget("bg")
    r16, g16, b16 = widget.winfo_rgb(base_bg)
    r8, g8, b8 = (r16 // 257), (g16 // 257), (b16 // 257)
    luminance = 0.2126 * r8 + 0.7152 * g8 + 0.0722 * b8
    fg = "#000000" if luminance > 140 else "#FFFFFF"
    def lighten(x, f): return min(255, int(round(x + (255 - x) * f)))
    lr, lg, lb = lighten(r8, lift), lighten(g8, lift), lighten(b8, lift)
    entry_bg = f"#{lr:02x}{lg:02x}{lb:02x}"
    def clamp(v): return max(0, min(255, v))
    if luminance < 128:
        br, bg_, bb = lighten(r8, border_delta), lighten(g8, border_delta), lighten(b8, border_delta)
    else:
        br, bg_, bb = clamp(int(r8*(1-border_delta))), clamp(int(g8*(1-border_delta))), clamp(int(b8*(1-border_delta)))
    border = f"#{br:02x}{bg_:02x}{bb:02x}"
    return {"base_bg": base_bg, "fg": fg, "entry_bg": entry_bg, "border": border}

def update_text_font(label, frame):
    text_height = int(frame.winfo_height() * 0.55)
    size = max(8, min(12, int(text_height / 20)))
    font = tkFont.Font(family="Helvetica", size=size)
    label.config(font=font)

def update_team_display():
    for idx, frame in enumerate(team_frames):
        data = team_data[idx]
        img_label = img_labels[idx]
        stats_label = stats_labels[idx]

        if data:
            # Bild laden oder aus Cache nehmen
            if "img_pil" not in data:
                data["img_pil"] = Image.open(BytesIO(data["image"]))
            img = data["img_pil"]

            frame_width = frame.winfo_width()
            frame_height = int(frame.winfo_height() * 0.45)
            if frame_width > 1 and frame_height > 1:
                img_ratio = img.width / img.height
                frame_ratio = frame_width / frame_height
                if frame_ratio > img_ratio:
                    new_height = frame_height
                    new_width = int(img_ratio * new_height)
                else:
                    new_width = frame_width
                    new_height = int(new_width / img_ratio)
                img_resized = img.resize((new_width, new_height), Image.LANCZOS)
                img_tk = ImageTk.PhotoImage(img_resized)
                img_label.configure(image=img_tk)
                img_label.image = img_tk
                img_label.place(relx=0.5, rely=0.225, anchor="center")

            strengths = data.get("strengths", [])
            weaknesses = data.get("weaknesses", [])

            stats_text = (
                f"Typen: {', '.join(data['types'])}\n"
                f"Moves: {', '.join(data['moves'])}\n"
                f"Strengths: {', '.join(strengths) if strengths else '-'}\n"
                f"Weakness: {', '.join(weaknesses) if weaknesses else '-'}"
            )
            stats_label.config(text=stats_text)
            stats_label.place(relx=0.5, rely=0.7, anchor="center")
            update_text_font(stats_label, frame)
        else:
            img_label.configure(image="")
            img_label.image = None
            stats_label.config(text="")

def change_pokemon(slot):
    def load_data():
        name = name_entries[slot].get()
        if not name:
            return
        try:
            level = int(level_entries[slot].get())
        except:
            level = 100
        data = get_pokemon_data(name, level)
        if data:
            strengths, weaknesses = get_type_relations(data['types'])
            data['strengths'] = strengths
            data['weaknesses'] = weaknesses
            team_data[slot] = data
            root.after(0, update_team_display)

    threading.Thread(target=load_data).start()

def actually_resize():
    for idx, frame in enumerate(team_frames):
        stats_label = stats_labels[idx]
        stats_label.config(wraplength=int(frame.winfo_width() * 0.9))
    update_team_display()

def on_resize(event):
    global resize_job
    if resize_job:
        root.after_cancel(resize_job)
    resize_job = root.after(150, actually_resize)  # nur alle 150ms

# ----- Slots erstellen -----
for i in range(2):
    for j in range(3):
        idx = i*3 + j
        frame = tk.Frame(team_container, bg="#333333", bd=2, relief="raised")
        frame.grid(row=i, column=j, sticky="nsew", padx=5, pady=5)
        frame.rowconfigure(0, weight=3)
        frame.rowconfigure(1, weight=3)
        frame.rowconfigure(2, weight=3)
        frame.columnconfigure(0, weight=2)
        team_frames.append(frame)

        img_label = tk.Label(frame, bg="#333333")
        img_label.grid(row=0, column=0, sticky="nsew")
        img_labels.append(img_label)

        input_frame = tk.Frame(frame, bg="#444444")
        input_frame.grid(row=1, column=0, sticky="ew", pady=5, padx=5)
        tk.Label(input_frame, text="Name:", bg="#444444", fg="white").grid(row=0, column=0)
        name_entry = tk.Entry(input_frame, width=12)
        name_entry.grid(row=0, column=1, padx=3)
        tk.Label(input_frame, text="Level:", bg="#444444", fg="white").grid(row=0, column=2)
        level_entry = tk.Entry(input_frame, width=5)
        level_entry.grid(row=0, column=3, padx=3)
        tk.Button(input_frame, text="Suchen", command=lambda s=idx: change_pokemon(s)).grid(row=0, column=4, padx=3)
        name_entries.append(name_entry)
        level_entries.append(level_entry)

        stats_label = tk.Label(frame, text="", bg="#333333", fg="white", justify="left", anchor="n")
        stats_label.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        stats_labels.append(stats_label)

root.bind("<Configure>", on_resize)
root.mainloop()
