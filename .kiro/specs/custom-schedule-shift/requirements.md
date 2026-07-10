# Requirements Document

## Introduction

This feature adds a "Custom" shift type to the Team Management section of DC-ShiftMaster HTML. Currently, teammates can only be assigned to one of four fixed shift rotations (FHD, FHN, BHD, BHN). The Custom shift type allows a teammate to have a non-standard schedule by selecting specific days of the week (Mon–Sun) via checkboxes, rather than following a fixed rotation pattern.

## Glossary

- **Team_Management_UI**: The Team tab in DC-ShiftMaster HTML responsible for viewing, adding, editing, and deleting teammates
- **Shift_Type_Selector**: The dropdown control that allows selection of a shift type when adding or editing a teammate
- **Custom_Schedule**: A shift type where the teammate works on individually selected days of the week rather than following a fixed rotation
- **Day_Selector**: A set of seven checkboxes (Mon, Tue, Wed, Thu, Fri, Sat, Sun) used to specify which days a Custom-schedule teammate works
- **Teammate_Record**: The data object representing a teammate, containing fields such as name, shift_type, custom_start, and custom_days
- **Standard_Shift_Types**: The four existing fixed rotation shift types: FHD, FHN, BHD, BHN

## Requirements

### Requirement 1: Custom Shift Type Option in Shift Selector

**User Story:** As a team manager, I want to see a "Custom" option in the shift type dropdown, so that I can assign teammates to a custom schedule instead of a fixed rotation.

#### Acceptance Criteria

1. THE Shift_Type_Selector SHALL include "Custom" as an additional option alongside the Standard_Shift_Types (FHD, FHN, BHD, BHN)
2. WHEN a user opens the Add Teammate form, THE Shift_Type_Selector SHALL display all five shift type options: FHD, FHN, BHD, BHN, Custom
3. WHEN a user opens the Edit Teammate inline form, THE Shift_Type_Selector SHALL display all five shift type options with the teammate's current shift type pre-selected, even if that shift type option is unavailable in the dropdown configuration

### Requirement 2: Day Selector for Custom Schedule

**User Story:** As a team manager, I want to select specific days of the week for a Custom-schedule teammate, so that the system knows which days that teammate works.

#### Acceptance Criteria

1. WHEN "Custom" is selected in the Shift_Type_Selector, THE Team_Management_UI SHALL display the Day_Selector with seven checkboxes labeled Mon, Tue, Wed, Thu, Fri, Sat, Sun
2. WHILE a Standard_Shift_Type is selected in the Shift_Type_Selector, THE Team_Management_UI SHALL hide the Day_Selector
3. WHEN the user switches the Shift_Type_Selector from "Custom" to a Standard_Shift_Type, THE Team_Management_UI SHALL hide the Day_Selector
4. WHEN the user switches the Shift_Type_Selector from a Standard_Shift_Type to "Custom", THE Team_Management_UI SHALL show the Day_Selector with all checkboxes unchecked

### Requirement 3: Persisting Custom Schedule Data

**User Story:** As a team manager, I want custom day selections to be saved with the teammate record, so that the schedule persists across sessions.

#### Acceptance Criteria

1. WHEN a teammate is saved with shift_type "Custom", THE Team_Management_UI SHALL include the selected days as a custom_days field in the Teammate_Record sent to the API
2. THE custom_days field SHALL store the selected days as a JSON array of day abbreviations (e.g., ["Mon", "Wed", "Fri"])
3. WHEN a teammate with shift_type "Custom" is loaded for editing, THE Day_Selector SHALL pre-check the checkboxes corresponding to the stored custom_days values
4. IF no days are selected when the user attempts to save a Custom-schedule teammate, THEN THE Team_Management_UI SHALL display a validation error and prevent the save; the error message SHALL only appear when the save is actually prevented
5. IF at least one day is selected when the user attempts to save a Custom-schedule teammate, THEN THE Team_Management_UI SHALL allow the save after performing additional validation checks (e.g., verifying name is non-empty)

### Requirement 4: Display of Custom-Schedule Teammates in Team List

**User Story:** As a team manager, I want to see Custom-schedule teammates grouped and labeled clearly in the team list, so that I can distinguish them from standard-rotation teammates.

#### Acceptance Criteria

1. WHEN at least one teammate has shift_type "Custom", THE Team_Management_UI SHALL display a "Custom" shift group section in the team list alongside the existing FHD, FHN, BHD, BHN group sections; IF no teammates have shift_type "Custom", THEN THE Custom group section SHALL NOT be displayed
2. WHEN a teammate has shift_type "Custom", THE Team_Management_UI SHALL display the teammate's selected days (e.g., "Mon, Wed, Fri") next to the teammate name in the list row
3. THE Custom shift group section SHALL display the count of Custom-schedule teammates in its heading (e.g., "Custom (3)")

### Requirement 5: CSV Export and Import Compatibility

**User Story:** As a team manager, I want the CSV export and import to support the Custom shift type and days, so that I can bulk-manage teammates with custom schedules.

#### Acceptance Criteria

1. WHEN exporting teammates to CSV, THE Team_Management_UI SHALL always include a custom_days column in the CSV file structure, containing the semicolon-separated day values for Custom-schedule teammates (e.g., "Mon;Wed;Fri")
2. WHEN exporting teammates with a Standard_Shift_Type, THE Team_Management_UI SHALL include the custom_days column but leave it empty for those rows
3. WHEN importing a CSV row with shift_type "Custom", THE Team_Management_UI SHALL parse the custom_days column as semicolon-separated day abbreviations and store them in the Teammate_Record
4. IF a CSV import row has shift_type "Custom" but the custom_days column is empty or contains invalid day values, THEN THE Team_Management_UI SHALL skip that row and report it as a skipped row

### Requirement 6: Scheduling Engine Compatibility

**User Story:** As a team manager, I want the scheduling engine to correctly determine working days for Custom-schedule teammates, so that the calendar reflects their actual schedule.

#### Acceptance Criteria

1. WHEN generating a schedule for a teammate with shift_type "Custom", THE Scheduling_Engine SHALL mark the teammate as working only on the days specified in custom_days, including allowing zero working days if custom_days is empty
2. WHEN generating a schedule for a teammate with a Standard_Shift_Type, THE Scheduling_Engine SHALL continue using the existing rotation logic without change
3. THE Scheduling_Engine SHALL treat the custom_days as a weekly recurring pattern applied to every week in the schedule period
