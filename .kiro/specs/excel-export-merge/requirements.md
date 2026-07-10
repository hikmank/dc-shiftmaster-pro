# Requirements Document

## Introduction

The DC-ShiftMaster Pro Excel export currently produces two separate calendar worksheets — one for day shifts and one for night shifts — each using a 2-week block layout with Wed–Tue weeks showing B/F markers and teammate names. This feature merges both shifts into a single unified calendar worksheet and adds the actual shift start/end times to each cell, so users can see the complete daily picture (day + night) at a glance without switching between sheets.

The change applies to the shared `ExcelExporter` class in `dc_shiftmaster/excel_export.py`, which is consumed by all three application frontends (desktop/Tkinter, web/Flet, HTML/Flask). No caller-side changes are required because the `ExcelExporter.export()` public API signature remains the same.

## Glossary

- **ExcelExporter**: The class in `dc_shiftmaster/excel_export.py` responsible for generating the `.xlsx` workbook.
- **Calendar_Worksheet**: The main worksheet in the exported workbook that displays the shift rotation in a calendar grid with Wed–Tue weeks.
- **Two_Week_Block**: A visual grouping of two consecutive Wed–Tue weeks rendered as rows in the calendar grid.
- **Shift_Cell**: A single cell in the calendar grid representing one team's assignment for a specific date, containing the B/F marker, teammate names, and shift times.
- **Day_Shift**: The daytime shift window, typically 06:00–18:30, configurable via `ShiftWindow`.
- **Night_Shift**: The nighttime shift window, typically 18:00–06:30, configurable via `ShiftWindow`.
- **Back_Half**: The rotation group (marker "B") that owns Thu/Fri/Sat and alternating Wednesdays.
- **Front_Half**: The rotation group (marker "F") that owns Sun/Mon/Tue and alternating Wednesdays.
- **Shift_Window**: A `ShiftWindow` model instance defining the `start_time` and `end_time` for a day or night shift.
- **Coverage_Summary_Sheet**: The existing worksheet that shows daily headcount coverage across time blocks.
- **Timeline_Sheet**: The existing worksheet that shows 24-hour color-bar timelines per day.

## Requirements

### Requirement 1: Merge Day and Night Shifts into a Single Calendar Worksheet

**User Story:** As a shift manager, I want day and night shifts displayed on a single calendar worksheet, so that I can see the full daily staffing picture without switching between two separate sheets.

#### Acceptance Criteria

1. WHEN the ExcelExporter generates the workbook, THE Calendar_Worksheet SHALL contain both day shift and night shift assignments for every date in a single worksheet titled "{year} Shift Calendar".
2. THE ExcelExporter SHALL remove the previously separate "Day Shift {year}" and "Night Shift {year}" worksheets and replace them with the single merged Calendar_Worksheet.
3. WHEN rendering a Two_Week_Block, THE Calendar_Worksheet SHALL display day shift rows and night shift rows for each week within the same block, so that each date's complete staffing is visible together.
4. THE Calendar_Worksheet SHALL use the existing color scheme to distinguish shifts: gold (`FFD966`) fill for Back_Half day shifts, green (`A9D18E`) fill for Front_Half day shifts, blue (`B4C6E7`) fill for Back_Half night shifts, and purple (`D5A6E6`) fill for Front_Half night shifts.
5. THE Calendar_Worksheet SHALL preserve the existing Wed–Tue week orientation, date row, and day-name row layout within each Two_Week_Block.

### Requirement 2: Display Shift Times in Calendar Cells

**User Story:** As a shift manager, I want the actual shift start and end times shown in each calendar cell, so that I can see at a glance when each shift runs without consulting a separate settings page.

#### Acceptance Criteria

1. WHEN shift_windows are provided to the ExcelExporter, THE Shift_Cell SHALL include the shift time range (e.g. "06:00–18:30") in addition to the B/F marker and teammate names.
2. WHEN shift_windows are not provided or are missing a shift type, THE Shift_Cell SHALL omit the time range and display only the B/F marker and teammate names.
3. THE Shift_Cell SHALL display content in the order: B/F marker, then shift time range, then teammate names, each on a separate line within the cell.
4. THE Shift_Cell SHALL use a smaller font size (8pt or less) for the time range text to keep cells compact while remaining legible.

### Requirement 3: Merged Calendar Two-Week Block Layout

**User Story:** As a shift manager, I want the merged calendar to have a clear, readable layout that separates day and night information within each week block, so that I can quickly scan the schedule.

#### Acceptance Criteria

1. WHEN rendering a Two_Week_Block, THE Calendar_Worksheet SHALL use the following row order per week: (1) date row, (2) day-name row, (3) day-shift B-marker row, (4) day-shift F-marker row, (5) night-shift B-marker row, (6) night-shift F-marker row.
2. THE Calendar_Worksheet SHALL include a visual label or sub-header distinguishing the day-shift rows from the night-shift rows within each week (e.g. a "Day" label in column A for day-shift rows and a "Night" label for night-shift rows).
3. THE Calendar_Worksheet SHALL set column widths to at least 18 characters to accommodate the additional time-range text in each Shift_Cell.

### Requirement 4: Preserve Existing Sheets and Export API

**User Story:** As a developer, I want the Coverage Summary and Timeline sheets to remain unchanged and the export API to stay backward-compatible, so that all three frontends continue to work without modification.

#### Acceptance Criteria

1. THE ExcelExporter SHALL continue to produce the Coverage_Summary_Sheet and Timeline_Sheet with their existing content and formatting.
2. THE ExcelExporter.export() method SHALL retain its current signature: `export(year, schedule, engine, filepath, shift_windows=None)`.
3. WHEN any frontend (desktop, web, or HTML) calls ExcelExporter.export(), THE ExcelExporter SHALL produce the merged Calendar_Worksheet without requiring changes to the calling code.
4. IF the ExcelExporter encounters an OS or permission error while saving the workbook, THEN THE ExcelExporter SHALL raise an `OSError` with a descriptive message, preserving the existing error-handling behavior.

### Requirement 5: Worksheet Ordering

**User Story:** As a shift manager, I want the merged calendar to be the first sheet I see when opening the Excel file, so that the most important information is immediately visible.

#### Acceptance Criteria

1. THE ExcelExporter SHALL place the Calendar_Worksheet as the first (leftmost) sheet in the workbook.
2. THE ExcelExporter SHALL place the Coverage_Summary_Sheet as the second sheet and the Timeline_Sheet as the third sheet in the workbook.
