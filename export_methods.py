
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
