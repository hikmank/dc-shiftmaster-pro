# Implementation Plan: Excel Export Merge

## Overview

Modify `dc_shiftmaster/excel_export.py` to replace the two separate day/night calendar worksheets with a single merged worksheet. Add shift time annotations to cells and expand the two-week block layout to 6 rows per week (day + night). Preserve Coverage Summary and Timeline sheets unchanged, and keep the `export()` API backward-compatible.

## Tasks

- [x] 1. Add `_format_cell_content()` helper method
  - [x] 1.1 Implement `_format_cell_content(self, marker, shift_window, slot)` in `ExcelExporter`
    - Returns multi-line string: marker line, optional time range line, optional teammate names line
    - When `shift_window` is provided, include "{start_time}–{end_time}" on line 2
    - When `shift_window` is None, omit the time range line
    - When `slot` is None or `slot.teammates == ["nobody"]`, omit the names line
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 1.2 Write property test for `_format_cell_content`
    - **Property 3: Cell content format with shift times**
    - **Validates: Requirements 2.1, 2.2, 2.3**

- [x] 2. Implement `_write_merged_two_week_block()` method
  - [x] 2.1 Create `_write_merged_two_week_block(self, ws, start_row, week_start, year, engine, lookup, shift_windows)` in `ExcelExporter`
    - For each of the 2 weeks, write 6 rows: date row, day-name row, day-B row, day-F row, night-B row, night-F row
    - Write "Day" label in column A for the day-shift B-marker row
    - Write "Night" label in column A for the night-shift B-marker row
    - Use `_format_cell_content()` for marker cell values
    - Apply correct fills: gold/green for day B/F, blue/purple for night B/F
    - Use 8pt or smaller font for time range text
    - Set wrap_text and vertical="top" alignment on marker cells
    - Return the next available row after the block
    - _Requirements: 1.3, 1.4, 1.5, 2.3, 2.4, 3.1, 3.2_

  - [x] 2.2 Write property test for merged block layout structure
    - **Property 2: Merged block layout structure**
    - **Validates: Requirements 1.3, 3.1, 3.2**

  - [x] 2.3 Write property test for color scheme correctness
    - **Property 4: Color scheme correctness**
    - **Validates: Requirements 1.4**

  - [x] 2.4 Write property test for Wednesday-to-Tuesday week orientation
    - **Property 5: Wednesday-to-Tuesday week orientation**
    - **Validates: Requirements 1.5**

- [x] 3. Implement `_write_merged_sheet()` method
  - [x] 3.1 Create `_write_merged_sheet(self, ws, year, cycle_start, year_end, engine, lookup, shift_windows)` in `ExcelExporter`
    - Write title "{year} Shift Calendar" merged across columns A:G in row 1
    - Iterate from `cycle_start` to `year_end` in 14-day increments, calling `_write_merged_two_week_block()` for each block
    - Set column widths to at least 18 characters for columns 1–7
    - _Requirements: 1.1, 1.3, 3.3_

- [x] 4. Modify `export()` to use merged sheet
  - [x] 4.1 Replace the two `_write_sheet()` calls with a single `_write_merged_sheet()` call
    - Set the active worksheet title to "{year} Shift Calendar"
    - Remove creation of "Day Shift {year}" and "Night Shift {year}" sheets
    - Keep Coverage Summary as sheet 2 and Timeline as sheet 3
    - Pass `shift_windows` through to `_write_merged_sheet()`
    - Preserve existing error handling (OSError re-raise)
    - _Requirements: 1.1, 1.2, 4.1, 4.2, 4.3, 4.4, 5.1, 5.2_

  - [x] 4.2 Write property test for workbook sheet structure and ordering
    - **Property 1: Workbook sheet structure and ordering**
    - **Validates: Requirements 1.1, 1.2, 5.1, 5.2**

  - [x] 4.3 Write property test for Coverage and Timeline sheets preserved
    - **Property 6: Coverage and Timeline sheets preserved**
    - **Validates: Requirements 4.1**

- [x] 5. Checkpoint — Verify merged export works end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Write unit tests for edge cases and formatting details
  - [x] 6.1 Write unit tests in `tests/test_excel_export_merge_unit.py`
    - Test: time-range text uses ≤ 8pt font size
    - Test: `export()` accepts the documented parameters (backward-compatible signature)
    - Test: OSError with descriptive message on bad filepath
    - Test: column widths are ≥ 18 characters
    - Test: calling `export()` without `shift_windows` still produces valid workbook
    - Test: "nobody" slots render only marker (and optionally time), no names
    - _Requirements: 2.4, 3.3, 4.2, 4.3, 4.4_

- [x] 7. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- The design uses Python with openpyxl (matching the existing codebase)
- Property tests use Hypothesis (already configured in the project via `tests/conftest.py`)
- Existing `_write_sheet()` and `_write_two_week_block()` methods can be left in place or removed — the key change is that `export()` no longer calls them
- The `_write_coverage_sheet()` and `_write_timeline_sheet()` methods remain untouched
