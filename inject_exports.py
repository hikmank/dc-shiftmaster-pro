import re

code = open('app_v2.py', 'r', encoding='utf-8').read()
exports = open('export_methods.py', 'r', encoding='utf-8').read()

# 1) Add export button to Schedule nav bar - before schedule_frame creation
marker1 = '        self.schedule_frame = ctk.CTkScrollableFrame(self.content, fg_color="transparent", scrollbar_button_color=BORDER)'
insert1 = '''        ctk.CTkButton(inner_nav, text="Export", width=100, height=34, fg_color="transparent",
                       border_width=1, border_color=GREEN, hover_color="#1a3a1a", text_color=GREEN,
                       corner_radius=8, font=ctk.CTkFont(size=13), command=self.export_schedule).pack(side="right", padx=(0, 8))
'''
code = code.replace(marker1, insert1 + marker1, 1)

# 2) Add export button to Travel header - before Import Excel button
marker2 = '        ctk.CTkButton(header, text="Import Excel"'
insert2 = '''        ctk.CTkButton(header, text="Export", width=100, height=34, fg_color="transparent",
                       border_width=1, border_color=GREEN, hover_color="#1a3a1a", text_color=GREEN,
                       corner_radius=8, font=ctk.CTkFont(size=13), command=self.export_travel).pack(side="right", padx=(0, 10))
'''
code = code.replace(marker2, insert2 + marker2, 1)

# 3) Add export button to History header - before Reset Queue button
marker3 = '        ctk.CTkButton(header, text="Reset Queue"'
insert3 = '''        ctk.CTkButton(header, text="Export", width=100, height=34, fg_color="transparent",
                       border_width=1, border_color=GREEN, hover_color="#1a3a1a", text_color=GREEN,
                       corner_radius=8, font=ctk.CTkFont(size=13), command=self.export_history).pack(side="right", padx=(0, 10))
'''
code = code.replace(marker3, insert3 + marker3, 1)

# 4) Add export methods before reset_queue
marker4 = '    def reset_queue(self):'
code = code.replace(marker4, exports.rstrip() + '\n\n' + marker4, 1)

with open('app_v2.py', 'w', encoding='utf-8') as f:
    f.write(code)

print('OK')
print('Lines:', code.count('\n'))
print('export_schedule:', 'export_schedule' in code)
print('export_travel:', 'export_travel' in code)
print('export_history:', 'export_history' in code)
