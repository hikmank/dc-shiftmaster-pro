"""
Training Rotation Scheduler - Beautiful Modern GUI
"""
import customtkinter as ctk
from datetime import datetime, timedelta
from tkinter import messagebox, filedialog
import tkinter as tk
import scheduler

ctk.set_appearance_mode("dark")

BG_DARK = "#0d1117"
BG_CARD = "#161b22"
BG_CARD_ALT = "#1c2333"
BG_NAV = "#010409"
ACCENT = "#58a6ff"
ACCENT_HOVER = "#79c0ff"
ACCENT_DIM = "#1f3a5f"
GREEN = "#3fb950"
GREEN_HOVER = "#56d364"
RED = "#f85149"
RED_HOVER = "#ff7b72"
ORANGE = "#d29922"
TEXT_PRIMARY = "#e6edf3"
TEXT_SECONDARY = "#8b949e"
TEXT_DIM = "#484f58"
BORDER = "#30363d"
PURPLE = "#bc8cff"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Training Rotation Scheduler")
        self.geometry("1200x780")
        self.minsize(1050, 680)
        self.configure(fg_color=BG_DARK)
        self.data = scheduler.load_data()
        self.nav = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=BG_NAV)
        self.nav.pack(side="left", fill="y")
        self.nav.pack_propagate(False)
        logo_frame = ctk.CTkFrame(self.nav, fg_color="transparent")
        logo_frame.pack(fill="x", padx=20, pady=(28, 8))
        ctk.CTkLabel(logo_frame, text="Scheduler", font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")
        ctk.CTkLabel(self.nav, text="Training Rotation Manager",
                     font=ctk.CTkFont(size=11), text_color=TEXT_DIM).pack(padx=20, anchor="w")
        ctk.CTkFrame(self.nav, height=1, fg_color=BORDER).pack(fill="x", padx=16, pady=(18, 14))
        ctk.CTkLabel(self.nav, text="NAVIGATION", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=TEXT_DIM).pack(padx=22, anchor="w", pady=(0, 6))
        self.nav_buttons = {}
        btn_info = [
            ("  Schedule", "Schedule", self.show_schedule),
            ("  Team", "Team", self.show_team),
            ("  Travel", "Travel", self.show_travel),
            ("  History", "History", self.show_history),
        ]
        for label, key, cmd in btn_info:
            btn = ctk.CTkButton(self.nav, text=label, command=cmd, height=38,
                                fg_color="transparent", hover_color=ACCENT_DIM,
                                anchor="w", font=ctk.CTkFont(size=13),
                                text_color=TEXT_SECONDARY, corner_radius=8)
            btn.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[key] = btn
        spacer = ctk.CTkFrame(self.nav, fg_color="transparent")
        spacer.pack(fill="both", expand=True)
        ctk.CTkFrame(self.nav, height=1, fg_color=BORDER).pack(fill="x", padx=16, pady=(0, 10))
        self.member_count_label = ctk.CTkLabel(self.nav, text="", font=ctk.CTkFont(size=11), text_color=TEXT_DIM)
        self.member_count_label.pack(padx=22, anchor="w", pady=(0, 16))
        self.update_member_count()
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=BG_DARK)
        self.content.pack(side="right", fill="both", expand=True)
        self.show_schedule()

    def update_member_count(self):
        self.member_count_label.configure(text=f"{len(self.data['employees'])} team members")

    def clear_content(self):
        for w in self.content.winfo_children():
            w.destroy()

    def set_active_nav(self, name):
        for n, btn in self.nav_buttons.items():
            if n == name:
                btn.configure(fg_color=ACCENT_DIM, text_color=ACCENT)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_SECONDARY)

    def show_schedule(self):
        self.set_active_nav("Schedule")
        self.clear_content()
        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(24, 0))
        ctk.CTkLabel(header, text="Weekly Schedule", font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")
        self.week_offset = 0
        nav_bar = ctk.CTkFrame(self.content, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        nav_bar.pack(fill="x", padx=30, pady=(16, 0))
        inner_nav = ctk.CTkFrame(nav_bar, fg_color="transparent")
        inner_nav.pack(fill="x", padx=16, pady=12)
        ctk.CTkButton(inner_nav, text="< Previous", width=110, height=34, fg_color="transparent",
                       border_width=1, border_color=BORDER, hover_color=ACCENT_DIM,
                       text_color=TEXT_SECONDARY, corner_radius=8, command=self.prev_week).pack(side="left")
        self.week_label = ctk.CTkLabel(inner_nav, text="", font=ctk.CTkFont(size=14, weight="bold"),
                                        text_color=TEXT_PRIMARY)
        self.week_label.pack(side="left", expand=True)
        ctk.CTkButton(inner_nav, text="Generate", width=120, height=34, fg_color=ACCENT,
                       hover_color=ACCENT_HOVER, text_color=BG_DARK, corner_radius=8,
                       font=ctk.CTkFont(size=13, weight="bold"),
                       command=self.generate_schedule).pack(side="right", padx=(0, 8))
        ctk.CTkButton(inner_nav, text="Next >", width=110, height=34, fg_color="transparent",
                       border_width=1, border_color=BORDER, hover_color=ACCENT_DIM,
                       text_color=TEXT_SECONDARY, corner_radius=8, command=self.next_week).pack(side="right", padx=(0, 8))
        ctk.CTkButton(inner_nav, text="Export", width=100, height=34, fg_color="transparent",
                       border_width=1, border_color=GREEN, hover_color="#1a3a1a", text_color=GREEN,
                       corner_radius=8, font=ctk.CTkFont(size=13), command=self.export_schedule).pack(side="right", padx=(0, 8))
        self.schedule_frame = ctk.CTkScrollableFrame(self.content, fg_color="transparent", scrollbar_button_color=BORDER)
        self.schedule_frame.pack(fill="both", expand=True, padx=30, pady=(12, 20))
        self.refresh_schedule()

    def get_target_date(self):
        return datetime.now() + timedelta(weeks=self.week_offset)

    def prev_week(self):
        self.week_offset -= 1
        self.refresh_schedule()

    def next_week(self):
        self.week_offset += 1
        self.refresh_schedule()

    def generate_schedule(self):
        scheduler.generate_week_schedule(self.data, self.get_target_date())
        self.refresh_schedule()

    def refresh_schedule(self):
        for w in self.schedule_frame.winfo_children():
            w.destroy()
        target = self.get_target_date()
        week_key = scheduler.get_week_key(target)
        dates = scheduler.get_week_dates(target)
        self.week_label.configure(text=f"{week_key}  |  {dates[0].strftime('%b %d')} - {dates[3].strftime('%b %d, %Y')}")
        schedule = self.data.get("schedules", {}).get(week_key)
        if not schedule:
            empty = ctk.CTkFrame(self.schedule_frame, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
            empty.pack(fill="x", pady=30, padx=10)
            ctk.CTkLabel(empty, text="No schedule for this week", font=ctk.CTkFont(size=16, weight="bold"),
                         text_color=TEXT_PRIMARY).pack(pady=(30, 4))
            ctk.CTkLabel(empty, text="Click Generate to create the rotation", font=ctk.CTkFont(size=13),
                         text_color=TEXT_SECONDARY).pack(pady=(0, 30))
            return
        hdr = ctk.CTkFrame(self.schedule_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=6, pady=(4, 8))
        hdr.columnconfigure(0, weight=2)
        hdr.columnconfigure(1, weight=3)
        hdr.columnconfigure(2, weight=3)
        ctk.CTkLabel(hdr, text="DAY", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_DIM).grid(row=0, column=0, sticky="w", padx=8)
        for j, loc in enumerate(scheduler.LOCATIONS):
            color = ACCENT if j == 0 else PURPLE
            ctk.CTkLabel(hdr, text=loc, font=ctk.CTkFont(size=11, weight="bold"), text_color=color).grid(row=0, column=j+1, padx=8)
        for i, day in enumerate(scheduler.DAYS):
            day_data = schedule.get(day, {})
            card = ctk.CTkFrame(self.schedule_frame, fg_color=BG_CARD if i % 2 == 0 else BG_CARD_ALT,
                                corner_radius=10, border_width=1, border_color=BORDER)
            card.pack(fill="x", pady=3, padx=4)
            card.columnconfigure(0, weight=2)
            card.columnconfigure(1, weight=3)
            card.columnconfigure(2, weight=3)
            date_str = dates[i].strftime("%b %d")
            day_frame = ctk.CTkFrame(card, fg_color="transparent")
            day_frame.grid(row=0, column=0, sticky="w", padx=16, pady=14)
            ctk.CTkLabel(day_frame, text=day, font=ctk.CTkFont(size=14, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="w")
            ctk.CTkLabel(day_frame, text=date_str, font=ctk.CTkFont(size=11), text_color=TEXT_SECONDARY).pack(anchor="w")
            for j, loc in enumerate(scheduler.LOCATIONS):
                people = day_data.get(loc, [])
                cell = ctk.CTkFrame(card, fg_color="transparent")
                cell.grid(row=0, column=j+1, padx=10, pady=14)
                for person in people:
                    tag_color = ACCENT_DIM if j == 0 else "#2d1f4e"
                    txt_color = ACCENT if j == 0 else PURPLE
                    tag = ctk.CTkFrame(cell, fg_color=tag_color, corner_radius=6)
                    tag.pack(pady=2)
                    ctk.CTkLabel(tag, text=f"  {person}  ", font=ctk.CTkFont(size=12), text_color=txt_color).pack(padx=8, pady=3)
                if not people:
                    ctk.CTkLabel(cell, text="--", text_color=TEXT_DIM).pack()

    def show_team(self):
        self.set_active_nav("Team")
        self.clear_content()
        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(24, 0))
        ctk.CTkLabel(header, text="Team Management", font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")
        ctk.CTkLabel(header, text=f"  {len(self.data['employees'])} members  ", font=ctk.CTkFont(size=12),
                     fg_color=ACCENT_DIM, corner_radius=10, text_color=ACCENT).pack(side="left", padx=12)
        add_card = ctk.CTkFrame(self.content, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        add_card.pack(fill="x", padx=30, pady=(16, 0))
        add_inner = ctk.CTkFrame(add_card, fg_color="transparent")
        add_inner.pack(fill="x", padx=16, pady=14)
        ctk.CTkLabel(add_inner, text="Add New Member", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT_SECONDARY).pack(anchor="w", pady=(0, 8))
        input_row = ctk.CTkFrame(add_inner, fg_color="transparent")
        input_row.pack(fill="x")
        self.new_name_entry = ctk.CTkEntry(input_row, placeholder_text="Enter team member name...",
                                            height=38, corner_radius=8, fg_color=BG_DARK,
                                            border_color=BORDER, text_color=TEXT_PRIMARY)
        self.new_name_entry.pack(side="left", fill="x", expand=True)
        self.new_name_entry.bind("<Return>", lambda e: self.add_member())
        ctk.CTkButton(input_row, text="+ Add", width=90, height=38, fg_color=GREEN, hover_color=GREEN_HOVER,
                       text_color=BG_DARK, corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
                       command=self.add_member).pack(side="right", padx=(10, 0))
        self.team_list_frame = ctk.CTkScrollableFrame(self.content, fg_color="transparent", scrollbar_button_color=BORDER)
        self.team_list_frame.pack(fill="both", expand=True, padx=30, pady=(12, 20))
        self.refresh_team_list()

    def refresh_team_list(self):
        for w in self.team_list_frame.winfo_children():
            w.destroy()
        colors = [ACCENT, GREEN, PURPLE, ORANGE, "#f778ba"]
        for i, name in enumerate(sorted(self.data["employees"])):
            row = ctk.CTkFrame(self.team_list_frame, fg_color=BG_CARD if i % 2 == 0 else BG_CARD_ALT,
                               corner_radius=10, border_width=1, border_color=BORDER)
            row.pack(fill="x", pady=2, padx=4)
            initials = "".join([p[0] for p in name.split()[:2]]).upper()
            avatar_color = colors[i % len(colors)]
            avatar = ctk.CTkFrame(row, width=36, height=36, corner_radius=18, fg_color=avatar_color)
            avatar.pack(side="left", padx=(14, 10), pady=10)
            avatar.pack_propagate(False)
            ctk.CTkLabel(avatar, text=initials, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=BG_DARK).place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=14), text_color=TEXT_PRIMARY).pack(side="left", padx=(0, 10), pady=10)
            count = self.data.get("history", {}).get(name, 0)
            ctk.CTkLabel(row, text=f"  {count} assignments  ", font=ctk.CTkFont(size=11),
                         fg_color=BG_DARK, corner_radius=8, text_color=TEXT_SECONDARY).pack(side="left", padx=5)
            trips = self.data.get("external_travel", {}).get(name, [])
            if trips:
                ctk.CTkLabel(row, text=f"  {len(trips)} trips  ", font=ctk.CTkFont(size=11),
                             fg_color="#2d1f0a", corner_radius=8, text_color=ORANGE).pack(side="left", padx=5)
            ctk.CTkButton(row, text="Remove", width=75, height=30, fg_color="transparent", border_width=1,
                          border_color=RED, hover_color="#3d1214", text_color=RED, corner_radius=8,
                          font=ctk.CTkFont(size=12), command=lambda n=name: self.remove_member(n)).pack(side="right", padx=14, pady=10)

    def add_member(self):
        name = self.new_name_entry.get().strip()
        if not name:
            return
        if scheduler.add_employee(self.data, name):
            self.new_name_entry.delete(0, "end")
            self.update_member_count()
            self.show_team()
        else:
            messagebox.showwarning("Duplicate", f"'{name}' is already on the team.")

    def remove_member(self, name):
        if messagebox.askyesno("Confirm Removal", f"Remove {name} from the team?"):
            scheduler.remove_employee(self.data, name)
            self.update_member_count()
            self.show_team()

    def show_travel(self):
        self.set_active_nav("Travel")
        self.clear_content()
        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(24, 0))
        ctk.CTkLabel(header, text="External Travel Calendar", font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")
        ctk.CTkButton(header, text="Export", width=100, height=34, fg_color="transparent",
                       border_width=1, border_color=GREEN, hover_color="#1a3a1a", text_color=GREEN,
                       corner_radius=8, font=ctk.CTkFont(size=13), command=self.export_travel).pack(side="right", padx=(0, 10))
        ctk.CTkButton(header, text="Import Excel", width=140, height=34, fg_color=ACCENT,
                       hover_color=ACCENT_HOVER, text_color=BG_DARK, corner_radius=8,
                       font=ctk.CTkFont(size=13, weight="bold"), command=self.import_excel).pack(side="right")
        hint = ctk.CTkFrame(self.content, fg_color=ACCENT_DIM, corner_radius=10)
        hint.pack(fill="x", padx=30, pady=(12, 0))
        ctk.CTkLabel(hint, text="Excel columns: Employee/Name | Start Date | End Date | Region (optional)",
                     font=ctk.CTkFont(size=12), text_color=ACCENT).pack(padx=14, pady=8)
        form_card = ctk.CTkFrame(self.content, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        form_card.pack(fill="x", padx=30, pady=(12, 0))
        form_inner = ctk.CTkFrame(form_card, fg_color="transparent")
        form_inner.pack(fill="x", padx=16, pady=14)
        ctk.CTkLabel(form_inner, text="Add Travel Entry", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT_SECONDARY).pack(anchor="w", pady=(0, 10))
        row1 = ctk.CTkFrame(form_inner, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(row1, text="Employee", font=ctk.CTkFont(size=12), text_color=TEXT_DIM).pack(side="left", padx=(0, 8))
        self.travel_name_var = ctk.StringVar(value=sorted(self.data["employees"])[0] if self.data["employees"] else "")
        self.travel_name_menu = ctk.CTkOptionMenu(row1, variable=self.travel_name_var,
            values=sorted(self.data["employees"]), width=220, height=34, fg_color=BG_DARK,
            button_color=BORDER, button_hover_color=ACCENT_DIM, dropdown_fg_color=BG_CARD,
            corner_radius=8, text_color=TEXT_PRIMARY)
        self.travel_name_menu.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(row1, text="Region", font=ctk.CTkFont(size=12), text_color=TEXT_DIM).pack(side="left", padx=(0, 8))
        self.travel_region = ctk.CTkEntry(row1, width=200, height=34, corner_radius=8,
            placeholder_text="e.g. NYC, Chicago...", fg_color=BG_DARK, border_color=BORDER, text_color=TEXT_PRIMARY)
        self.travel_region.pack(side="left")
        row2 = ctk.CTkFrame(form_inner, fg_color="transparent")
        row2.pack(fill="x")
        ctk.CTkLabel(row2, text="Start", font=ctk.CTkFont(size=12), text_color=TEXT_DIM).pack(side="left", padx=(0, 8))
        self.travel_start = ctk.CTkEntry(row2, width=140, height=34, corner_radius=8,
            placeholder_text="YYYY-MM-DD", fg_color=BG_DARK, border_color=BORDER, text_color=TEXT_PRIMARY)
        self.travel_start.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(row2, text="End", font=ctk.CTkFont(size=12), text_color=TEXT_DIM).pack(side="left", padx=(0, 8))
        self.travel_end = ctk.CTkEntry(row2, width=140, height=34, corner_radius=8,
            placeholder_text="YYYY-MM-DD", fg_color=BG_DARK, border_color=BORDER, text_color=TEXT_PRIMARY)
        self.travel_end.pack(side="left", padx=(0, 20))
        ctk.CTkButton(row2, text="+ Add Trip", width=100, height=34, fg_color=GREEN, hover_color=GREEN_HOVER,
                       text_color=BG_DARK, corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
                       command=self.add_travel).pack(side="right")
        self.travel_list_frame = ctk.CTkScrollableFrame(self.content, fg_color="transparent", scrollbar_button_color=BORDER)
        self.travel_list_frame.pack(fill="both", expand=True, padx=30, pady=(12, 20))
        self.refresh_travel_list()

    def add_travel(self):
        name = self.travel_name_var.get()
        start = self.travel_start.get().strip()
        end = self.travel_end.get().strip()
        region = self.travel_region.get().strip()
        try:
            datetime.strptime(start, "%Y-%m-%d")
            datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Invalid Date", "Please use YYYY-MM-DD format.")
            return
        if start > end:
            messagebox.showerror("Invalid Range", "Start date must be before end date.")
            return
        if scheduler.add_external_travel(self.data, name, start, end, region):
            self.travel_start.delete(0, "end")
            self.travel_end.delete(0, "end")
            self.travel_region.delete(0, "end")
            self.refresh_travel_list()
        else:
            messagebox.showerror("Error", "Could not add travel entry.")

    def refresh_travel_list(self):
        for w in self.travel_list_frame.winfo_children():
            w.destroy()
        has_entries = False
        for name in sorted(self.data.get("external_travel", {}).keys()):
            trips = self.data["external_travel"][name]
            for idx, trip in enumerate(trips):
                has_entries = True
                row = ctk.CTkFrame(self.travel_list_frame, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER)
                row.pack(fill="x", pady=2, padx=4)
                ctk.CTkFrame(row, width=4, height=30, fg_color=ORANGE, corner_radius=2).pack(side="left", padx=(14, 10), pady=10)
                info = ctk.CTkFrame(row, fg_color="transparent")
                info.pack(side="left", fill="x", expand=True, pady=10)
                ctk.CTkLabel(info, text=name, font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="w")
                region_text = f"  |  {trip['region']}" if trip.get("region") else ""
                ctk.CTkLabel(info, text=f"{trip['start']}  ->  {trip['end']}{region_text}",
                             font=ctk.CTkFont(size=12), text_color=TEXT_SECONDARY).pack(anchor="w")
                ctk.CTkButton(row, text="X", width=32, height=32, fg_color="transparent", hover_color="#3d1214",
                              text_color=RED, corner_radius=8, command=lambda n=name, i=idx: self.remove_travel(n, i)).pack(side="right", padx=12, pady=10)
        if not has_entries:
            empty = ctk.CTkFrame(self.travel_list_frame, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
            empty.pack(fill="x", pady=20, padx=10)
            ctk.CTkLabel(empty, text="No travel entries yet", font=ctk.CTkFont(size=15, weight="bold"),
                         text_color=TEXT_PRIMARY).pack(pady=(24, 4))
            ctk.CTkLabel(empty, text="Add trips manually or import from Excel", font=ctk.CTkFont(size=12),
                         text_color=TEXT_SECONDARY).pack(pady=(0, 24))

    def remove_travel(self, name, index):
        scheduler.remove_external_travel(self.data, name, index)
        self.refresh_travel_list()

    def import_excel(self):
        filepath = filedialog.askopenfilename(title="Select Travel Excel File",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")])
        if not filepath:
            return
        imported, skipped, errors = scheduler.import_travel_from_excel(self.data, filepath)
        msg = f"Imported: {imported} entries\nSkipped: {skipped}"
        if errors:
            msg += "\n\nIssues:\n" + "\n".join(errors[:10])
        messagebox.showinfo("Import Complete", msg)
        self.refresh_travel_list()

    def show_history(self):
        self.set_active_nav("History")
        self.clear_content()
        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(24, 0))
        ctk.CTkLabel(header, text="Assignment History", font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")
        ctk.CTkButton(header, text="Export", width=100, height=34, fg_color="transparent",
                       border_width=1, border_color=GREEN, hover_color="#1a3a1a", text_color=GREEN,
                       corner_radius=8, font=ctk.CTkFont(size=13), command=self.export_history).pack(side="right", padx=(0, 10))
        ctk.CTkButton(header, text="Reset Queue", width=130, height=34, fg_color="transparent",
                       border_width=1, border_color=RED, hover_color="#3d1214", text_color=RED,
                       corner_radius=8, command=self.reset_queue).pack(side="right")
        stats = ctk.CTkFrame(self.content, fg_color="transparent")
        stats.pack(fill="x", padx=30, pady=(16, 0))
        history = self.data.get("history", {})
        total = sum(history.values()) if history else 0
        max_count = max(history.values()) if history else 0
        min_count = min((history.get(e, 0) for e in self.data["employees"]), default=0)
        queue_len = len(self.data.get("rotation_queue", []))
        stat_data = [
            ("Total Assignments", str(total), ACCENT),
            ("Most Assigned", str(max_count), ORANGE),
            ("Least Assigned", str(min_count), GREEN),
            ("Queue Remaining", str(queue_len), PURPLE),
        ]
        for i, (label, value, color) in enumerate(stat_data):
            card = ctk.CTkFrame(stats, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
            card.pack(side="left", fill="x", expand=True, padx=(0 if i == 0 else 6, 0))
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(padx=16, pady=14)
            ctk.CTkLabel(inner, text=value, font=ctk.CTkFont(size=26, weight="bold"), text_color=color).pack(anchor="w")
            ctk.CTkLabel(inner, text=label, font=ctk.CTkFont(size=11), text_color=TEXT_SECONDARY).pack(anchor="w")
        chart_frame = ctk.CTkScrollableFrame(self.content, fg_color="transparent", scrollbar_button_color=BORDER)
        chart_frame.pack(fill="both", expand=True, padx=30, pady=(12, 8))
        bar_max = max_count if max_count > 0 else 1
        colors = [ACCENT, GREEN, PURPLE, ORANGE, "#f778ba"]
        for i, name in enumerate(sorted(self.data["employees"])):
            count = history.get(name, 0)
            row = ctk.CTkFrame(chart_frame, fg_color="transparent")
            row.pack(fill="x", pady=3, padx=4)
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=13), text_color=TEXT_PRIMARY,
                         width=180, anchor="w").pack(side="left")
            bar_container = ctk.CTkFrame(row, fg_color=BG_CARD, height=24, corner_radius=6)
            bar_container.pack(side="left", fill="x", expand=True, padx=8)
            bar_container.pack_propagate(False)
            bar_width = max(int((count / bar_max) * 400), 6)
            bar = ctk.CTkFrame(bar_container, fg_color=colors[i % len(colors)], width=bar_width, corner_radius=6)
            bar.pack(side="left", fill="y")
            ctk.CTkLabel(row, text=str(count), font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=TEXT_SECONDARY, width=35).pack(side="right")
        queue_card = ctk.CTkFrame(self.content, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER)
        queue_card.pack(fill="x", padx=30, pady=(4, 20))
        q_inner = ctk.CTkFrame(queue_card, fg_color="transparent")
        q_inner.pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(q_inner, text="Rotation Queue (next up first)", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT_SECONDARY).pack(anchor="w", pady=(0, 6))
        queue = self.data.get("rotation_queue", [])
        if queue:
            tag_frame = ctk.CTkFrame(q_inner, fg_color="transparent")
            tag_frame.pack(anchor="w")
            for j, person in enumerate(queue):
                tag = ctk.CTkFrame(tag_frame, fg_color=ACCENT_DIM if j == 0 else BG_DARK, corner_radius=6)
                tag.pack(side="left", padx=(0, 6), pady=2)
                prefix = "> " if j == 0 else ""
                ctk.CTkLabel(tag, text=f" {prefix}{person} ", font=ctk.CTkFont(size=11),
                             text_color=ACCENT if j == 0 else TEXT_SECONDARY).pack(padx=6, pady=3)
        else:
            ctk.CTkLabel(q_inner, text="Queue empty - will refill on next generation",
                         font=ctk.CTkFont(size=12), text_color=TEXT_DIM).pack(anchor="w")


    def export_schedule(self):
        target = self.get_target_date()
        week_key = scheduler.get_week_key(target)
        if week_key not in self.data.get("schedules", {}):
            messagebox.showwarning("No Data", "No schedule to export for this week.")
            return
        filepath = filedialog.asksaveasfilename(title="Export Schedule",
            defaultextension=".xlsx", initialfile=f"schedule_{week_key}",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv")])
        if not filepath:
            return
        if filepath.endswith(".csv"):
            scheduler.export_schedule_csv(self.data, week_key, filepath)
        else:
            scheduler.export_schedule_excel(self.data, week_key, filepath)
        messagebox.showinfo("Exported", f"Schedule exported to:\n{filepath}")

    def export_travel(self):
        filepath = filedialog.asksaveasfilename(title="Export Travel",
            defaultextension=".xlsx", initialfile="travel_calendar",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv")])
        if not filepath:
            return
        if filepath.endswith(".csv"):
            scheduler.export_travel_csv(self.data, filepath)
        else:
            scheduler.export_travel_excel(self.data, filepath)
        messagebox.showinfo("Exported", f"Travel data exported to:\n{filepath}")

    def export_history(self):
        filepath = filedialog.asksaveasfilename(title="Export History",
            defaultextension=".xlsx", initialfile="assignment_history",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv")])
        if not filepath:
            return
        if filepath.endswith(".csv"):
            scheduler.export_history_csv(self.data, filepath)
        else:
            scheduler.export_history_excel(self.data, filepath)
        messagebox.showinfo("Exported", f"History exported to:\n{filepath}")

    def reset_queue(self):
        if messagebox.askyesno("Reset Rotation", "Reset the rotation queue?\nEveryone gets shuffled back in."):
            import random
            self.data["rotation_queue"] = list(self.data["employees"])
            random.shuffle(self.data["rotation_queue"])
            scheduler.save_data(self.data)
            self.show_history()


if __name__ == "__main__":
    app = App()
    app.mainloop()
