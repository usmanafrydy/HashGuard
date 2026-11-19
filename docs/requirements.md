# HashGuard Initial Requirements

## Project Details

**Project Title:** HashGuard — A Python-Based File Integrity Monitoring System

**Course:** Software Construction and Development

**Instructor:** Engr. Muhammad Umer Haroon

## Group Members

| Name | Roll Number |
| --- | --- |
| Usman Dawood Afridi | 47 |
| Siaf Akbar | 43 |
| Mushaf Mashood | 39 |

## Document Status

This document contains the initial requirements for HashGuard.
The requirements may be refined as development progresses.

## Problem Statement

Files can be changed or deleted without the user noticing. Checking every file manually takes time, especially when there are many files in different folders. HashGuard will save a digital fingerprint, called a hash, for each file and compare it with the hash calculated during a later scan. This will help users find files that have been added, changed, or deleted. The user can then review these changes to decide whether they were expected.

## Project Objectives

- Create a trusted baseline of file hashes for a selected folder.
- Detect files that have been added, modified, or deleted since the baseline was created.
- Clearly report files that could not be checked.
- Present scan results in a way that is easy to understand.
- Allow users to export scan results for later review.
- Help users stay informed about cybersecurity threats by retrieving
  and displaying security advisories through web scraping.

## Intended Users

HashGuard is intended for students, developers, and other users who
want to check important files on their computers for unexpected changes.

- Students can check whether their project files have changed since
  they created a baseline.
- Developers can check source code and configuration files for
  unexpected changes.
- Other users can check selected documents and folders for added,
  modified, or deleted files.

## Functional Requirements

- **FR-01 — Select a Folder:** The application shall allow the user
  to select a local folder to scan.

- **FR-02 — Scan Files:** The application shall scan files in the
  selected folder and its subfolders, applying the configured exclusions.

- **FR-03 — Calculate Hashes:** The application shall calculate a
  SHA-256 hash for each readable file included in the scan.

- **FR-04 — Create a Baseline:** The application shall allow the
  user to save a reference containing the selected folder's
  absolute path, baseline creation time, hash algorithm, and
  exclusion settings. For each successfully checked file, it
  shall store the path relative to the selected folder and its
  SHA-256 hash. Files that could not be included shall be
  recorded, and the baseline shall be marked as incomplete.

- **FR-05 — Load and Validate a Baseline:** The application shall
  allow the user to load a saved baseline for comparison with a
  later scan. It shall check that the baseline contains the
  required information and matches the selected folder. If the
  baseline is invalid or belongs to a different folder, the
  application shall explain the problem and stop the comparison.

- **FR-06 — Detect Changes:** The application shall compare the
  current scan with the baseline and identify added, modified,
  deleted, and unchanged files where sufficient information is
  available. If a file or location was not successfully checked
  during baseline creation or the current scan, the application
  shall report the affected comparison as unverified rather
  than assign an unsupported change status.

- **FR-07 — Report Verification Errors:** The application shall report
  files or folders that could not be checked. Files in inaccessible
  locations shall not automatically be classified as deleted.

- **FR-08 — Configure Exclusions:** The application shall allow the
  user to exclude selected folders or filename patterns from scanning.
  The exclusions shall be recorded with the baseline and applied
  during comparisons.

- **FR-09 — Display Results:** The application shall display file
  paths, their statuses, and a summary of the scan results.

- **FR-10 — Export Reports:** The application shall allow the user
  to export scan results as a CSV file.

- **FR-11 — Preserve the Baseline:** Running a comparison scan shall
  not automatically overwrite the saved baseline. Creating a new
  baseline shall require an explicit user action.

- **FR-12 — Retrieve Security Advisories:** The application shall
  allow the user to manually retrieve security advisories from one
  configured public cybersecurity website. It shall download the
  webpage and extract advisory information from its HTML using
  web scraping. The application shall display up to 10 recent
  advisories, including their titles, publication dates when
  available, and links to the original articles. It shall show
  when the information was last successfully retrieved.

- **FR-13 — Handle Advisory Retrieval Errors:** If the advisory
  website cannot be reached or the expected information cannot
  be extracted, the application shall display a clear error
  message. A failed refresh shall preserve any previously
  retrieved advisories and their last successful retrieval time.
  The application shall indicate that the refresh failed.
  Local file scanning and baseline comparison shall remain
  available when advisory retrieval fails.

## Acceptance Conditions

### Baseline Creation (FR-04)

- A baseline shall be created successfully when the selected folder has been scanned and the required baseline information has been saved.
- The baseline shall contain the selected folder's absolute path, creation time, hash algorithm, exclusion settings, and file records.
- Each successfully checked file shall have a relative path and SHA-256 hash stored in the baseline.
- Files that cannot be checked shall be recorded as errors.
- If files cannot be checked, the baseline shall be marked as incomplete.
- The application shall not silently treat an incomplete baseline as fully verified.

### Baseline Loading and Validation (FR-05)

- A valid baseline shall load successfully when it contains all required information and belongs to the selected folder.
- A baseline with missing, invalid, or corrupted required information shall be rejected.
- A baseline belonging to a different folder shall not be used for comparison.
- When baseline validation fails, the application shall display an understandable error message.
- The comparison shall not proceed using an invalid baseline.

### Change Detection (FR-06)

- A file present in the current scan but absent from the baseline shall be classified as Added.
- A file present in both scans with different SHA-256 hashes shall be classified as Modified.
- A file present in the baseline but absent from a successfully completed current scan shall be classified as Deleted.
- A file present in both scans with matching SHA-256 hashes shall be classified as Unchanged.
- Files affected by incomplete scans or verification errors shall be classified as Unverified when their status cannot be reliably determined.
- The comparison shall not classify inaccessible files or folders as Deleted without sufficient verification.
- The comparison summary shall accurately reflect the number of files in each status.

### Baseline Preservation (FR-11)

- Performing a comparison shall not modify the existing baseline.
- A new baseline shall only be created following an explicit user action.
- The existing baseline shall remain available after a comparison is completed.

## Non-Functional Requirements

- **NFR-01 — Usability:** The interface shall use clear labels and
  understandable messages. File statuses shall be shown using text,
  so users do not have to rely only on colors.

- **NFR-02 — Reliability:** A failure to read one file shall not stop
  the application from checking other accessible files. Scans with
  errors shall be clearly marked as incomplete.

- **NFR-03 — Memory Efficiency:** The application shall read files
  in chunks when calculating hashes rather than loading an entire
  file into memory.

- **NFR-04 — File Safety:** Scanning shall not modify or delete the
  contents of monitored files. Application data and reports shall
  be stored outside the monitored folder.

- **NFR-05 — Maintainability:** The code shall be organized into
  separate modules for scanning, hashing, comparison, storage,
  reporting, security advisory retrieval, and the interface.
  Each module shall have a clear responsibility.

- **NFR-06 — Testability:** The core hashing, comparison, and
  advisory HTML parsing functions shall be testable without
  opening the desktop interface or making live internet requests.
  Advisory parsing tests shall use saved sample HTML with known
  expected results.

- **NFR-07 — Compatibility:** The initial application shall be
  developed and tested on Windows using Python 3. The tested
  Python version shall be recorded in the project documentation.

- **NFR-08 — Responsiveness:** The desktop interface shall remain
  responsive while file scanning or security advisory retrieval
  is running. It shall display progress information when available,
  or a busy indicator when progress cannot be measured.

## Prioritized Features

### Must Have

- Select and scan a local folder and its subfolders.
- Calculate SHA-256 hashes for readable files.
- Create and load a baseline.
- Detect added, modified, deleted, and unchanged files.
- Report unreadable files and incomplete scans.
- Apply exclusion rules consistently.
- Preserve the baseline unless the user explicitly creates a new one.
- Display understandable scan results.
- Retrieve and display security advisories through HTML web scraping.
- Handle advisory retrieval failures without interrupting local
  file scanning or baseline comparison.

### Should Have

- Provide a desktop interface for the scanning workflow.
- Export scan results as a CSV report.
- Allow users to filter results by file status.

### Could Have

- Store and display previous scan results.
- Support periodic scanning while the application is open.
- Preserve and select between multiple baseline versions.

The Must Have features will be developed first. Should Have features
remain planned for the semester version but will follow the core
functionality. Could Have features are optional and depend on the
time available.

## Initial Assumptions

- The user will create the baseline from files they consider trustworthy.
  HashGuard will not determine whether those files were already unsafe.

- The user will have permission to access the selected folder.
  Any files that remain inaccessible will be reported as unverified.

- The user will keep the baseline in a trusted location outside the
  monitored folder and protect it from unauthorized changes.

- Files are expected to remain reasonably stable during a scan.
  If the application detects that a file changed while being read,
  it will report that the file could not be reliably verified.

- The application will run locally on the user's computer.
  An internet connection will not be required for its core scanning
  and comparison features.

- Retrieving new security advisories will require an internet
  connection and access to the configured cybersecurity website.
  Previously retrieved advisories may become outdated, so their
  last successful retrieval time will remain visible.

## Project Constraints

- The application will be developed in Python.

- Windows will be the initial development and testing platform.
  Support for other operating systems is outside the initial scope.

- The project must be developed within the semester schedule and
  with the resources available to the group.

- Each scan will cover one selected local folder and its subfolders.
  Remote computers and cloud storage services are outside the
  initial scope.

- SHA-256 will be used consistently for file content hashing.

- Baselines and reports will be stored locally, outside the
  monitored folder.

- The initial version will use scans started by the user.
  Periodic scanning is an optional later improvement.

- The initial version will skip symbolic links and Windows junctions
  rather than follow them to other locations.

## Known Limitations

- HashGuard will detect differences from a saved baseline, but it
  will not determine whether a change was authorized or malicious.

- The application will not prevent file changes, remove malware,
  or restore modified or deleted files.

- Changes made and then reversed between scans may go undetected.

- A renamed or moved file will initially be reported as a deletion
  at its original path and an addition at its new path.

- Files that cannot be read will remain unverified. An incomplete
  scan cannot confirm the integrity of every file in the folder.

- If someone can alter both the monitored files and the trusted
  baseline, they may be able to hide changes from the application.

- Scanning time will depend on the number of files, their sizes,
  and the computer's storage performance.

- The initial version will check file contents. Changes only to
  file permissions or other metadata will not be treated as
  content modifications.

- Changes to the source website's HTML structure may prevent
  advisory retrieval until the scraping code is updated.
  Website downtime or connection problems may also prevent updates.

- Security advisories provide general cybersecurity information.
  They do not establish whether a monitored file is malicious
  or whether a particular file change is related to an advisory.
