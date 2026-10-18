# HashGuard

HashGuard is a Python-based file integrity monitoring system developed for our Software Construction and Development Course semester project.

The application will calculate SHA-256 hashes for files in a selected
folder and save them as a reference baseline. Later scans will compare
the current files against this baseline to identify added, modified,
and deleted files. Files that cannot be checked will be reported as
unverified.

HashGuard aims to help users identify unexpected file changes and
review the results through a desktop interface and exported reports.

## Course

Software Construction and Development.

## Instructor

Sir Umer Haroon

## Group Members

|         Name        | Roll Number |
|---------------------|-------------|
| Usman Dawood Afridi |      47     |
| Siaf Akbar          |      43     |
| Mushaf Mashood      |      39     |

## Problem Statement

Manually checking a collection of files for changes is time-consuming
and becomes difficult as the number of files increases. File names,
sizes, and modification dates alone do not reliably establish whether
file contents still match an earlier state.

HashGuard will address this problem by comparing file hashes against
a saved baseline and presenting a clear record of detected differences.

## Project Objectives

- Establish a reference baseline for a selected folder.
- Detect file additions, content modifications, and deletions.
- Clearly report unreadable files and incomplete scans.
- Allow users to exclude selected files or folders.
- Provide readable scan results and exportable reports.
- Apply modular design, version control, and automated testing.

## Intended Users

The initial application is intended for students, developers, and
individual users who want to check whether files in a local folder
have changed since a trusted baseline was created.

## Planned Features

- Select a local folder for scanning.
- Scan files within the selected folder and its subfolders.
- Calculate SHA-256 hashes for readable files.
- Create and load a reference baseline.
- Classify files as added, modified, deleted, or unchanged.
- Report files and locations that could not be verified.
- Apply configurable exclusion rules.
- Display and filter scan results.
- Export scan reports in CSV format.
- Provide a desktop interface.

Scan history and periodic scanning may be added after the core
functionalities are complete.

## Planned Technologies

| Technology | Purpose |
| --- | --- |  
| Python | Application development |
| hashlib | SHA-256 file hashing |
| pathlib and os | File paths and directory traversal |
| JSON | Initial baseline storage |
| Tkinter and ttk | Desktop interface |
| csv | Report export |
| unittest | Automated testing |
| Git and GitHub | Version control and collaboration |

SQLite may be introduced if persistent scan history is implemented.

## Initial Scope and Limitations

- The initial version will inspect one selected local folder per scan.
- Users must create the baseline from a state they consider trustworthy.
- Detected changes do not automatically indicate malicious activity.
- The application will not prevent changes or restore deleted files.
- Changes made and reversed between scans may go undetected.
- A renamed file will initially appear as a deletion and an addition.
- Inaccessible files or folders will be reported as unverified rather
  than automatically classified as deleted.
- Protecting the application and its baseline is necessary for
  trustworthy results.

## Current Project Status

Project initiation and requirements documentation are in progress.
Application implementation has not started.

The current milestone is to establish the shared repository,
document the initial requirements, assign responsibilities, and
prepare a prioritized product backlog.

## Project Documentation

- [Requirements document](docs/requirements.md)
- [Requirements PDF](docs/requirements.pdf)
- [Product backlog](docs/backlog.md)

The requirements and PDF are currently drafts.
Group reviews are pending.

## Development Approach

Development will proceed incrementally, beginning with hashing a
single file, then folder scanning, baseline storage, and comparison.

Error handling and automated tests will be developed alongside the
core functionality. Reporting and the desktop interface will follow.

Each group member will contribute through their own GitHub account.
Requirements and backlog items will be updated as the project evolves.

## Repository Conventions

### Files and Folders

- Use lowercase names for files and folders.
- Use underscores to separate words in Python filenames,
  such as file_scanner.py.
- Keep project documentation in docs, application code in src,
  and automated tests in tests as development progresses.
- Keep README.md uppercase to follow the repository's existing convention.

### Requirement and Task Identifiers

- Functional requirements use FR-01, FR-02, and so on.
- Non-functional requirements use NFR-01, NFR-02, and so on.
- Backlog tasks use HG-01, HG-02, and so on.
- Split tasks may use suffixes, such as HG-03A and HG-03B.
- Keep identifiers stable so commits and tests can refer to them.

### Commits

- Write meaningful messages describing the changes.
- Use docs: for documentation, feat: for new functionality,
  fix: for corrections, and test: for automated tests.
- Each member commits their own contributions using their own account.

### Project Versions

- Use Git history to track changes and tags to identify milestones.
- Use v0.1.0 for the initial project setup and requirements milestone.
- Use later v0.x.0 tags for development milestones.
- Use v1.0.0 for the first complete release.
- Do not create duplicate files with names such as final_v2
  to represent different versions.

### Repository Privacy

- Do not commit passwords, credentials, private files,
  or personal scan results.
- Use synthetic files and data for demonstrations and tests.
