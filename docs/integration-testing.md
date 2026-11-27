# Milestone 4 integration testing

HashGuard needs to give the same account of a file change after saving a baseline, reloading it, and producing a report. These tests follow data across those boundaries. They also check what the desktop worker returns to its caller and whether local monitoring still works when advisory retrieval fails.

## Running the tests

Run from the repository root. The verified Windows environment used Python 3.14.10 with Tkinter available, requests 2.34.2 and beautifulsoup4 4.15.0 for advisory retrieval and parsing, and pytest 9.2.0 as the test runner. These are the versions used for this run. The core monitoring pipeline uses the Python standard library. The temporary filesystem must support hard links for baseline publication and expose file identities for verification.

Run the complete suite with:

```shell
python -B -m pytest tests -q -p no:cacheprovider
```

To run only the 21 Milestone 4 scenarios:

```shell
python -B -m pytest tests/test_end_to_end_integration.py tests/test_desktop_integration.py tests/test_advisory_integration.py -q -p no:cacheprovider
```

Pytest collects both the project's unittest.TestCase methods and its existing standalone advisory test functions. The flags above suppress Python bytecode and pytest's cache. Filesystem scenarios use temporary directories.

## Verified results

The full suite on Windows passed 144 tests, skipped 2, and reported 46 passing subtests, with zero failures. All 21 scenarios below passed. The subtests are reported separately from the test count.

The skipped cases were the immediate scanner's symbolic link to a file and the recursive scanner's symbolic link to an external folder. Windows denied the privilege to create those links (WinError 1314), so those two assertions were not exercised on this machine. Run on a Windows environment permitted to create symbolic links to exercise them.

## Core monitoring, phases 1–3

Each row describes the input and the outcome asserted in [the seven core tests](../tests/test_end_to_end_integration.py).

| Scenario | Expected and verified outcome |
| --- | --- |
| 1. Successful saved-baseline workflow | Real SHA-256 hashes survive JSON storage. A rescan finds one added, modified, deleted and unchanged file each. A changed excluded log stays excluded. Text and CSV agree with the comparison. The baseline bytes and report inputs are preserved. |
| 2. Incomplete baseline, successful rescan | A single failed hash is saved as a file error. When the file is readable again, both reports classify it as unverified and identify the original baseline error. Its healthy sibling is unchanged. |
| 3. Complete baseline, inaccessible current folder | Two previously recorded nested files become unverified. An accessible edited file is modified. Text and CSV count three files and report the current folder error separately. |
| 4. Empty folder | Both scans are complete. The text has zero results and no warning. CSV contains exactly the two scan completion records. |
| 5. Unicode and spreadsheet-sensitive filenames | Original names survive saving, comparison and text formatting. CSV preserves the Unicode name and prefixes the leading equals and at-sign names with an apostrophe. Export preserves the comparison data. |
| 6. Replacement during verification | A real replacement with matching size and modification time produces a current file error. Both reports show the target as unverified and its healthy sibling as unchanged. |
| 7. CSV publication failure and retry | A simulated publication error preserves the previous CSV and removes temporary output. Retrying exports the modified file and both completion records. The baseline and comparison remain intact. |

## Desktop workers, phase 4

The [eight worker tests](../tests/test_desktop_integration.py) call the production save, load and comparison workers directly. Each verifies that a real queue receives exactly one result.

| Scenario | Expected and verified outcome |
| --- | --- |
| 8. Save a complete baseline | The queue carries a success message and a complete baseline. Reloading the saved JSON returns the same data, including the expected file hash. |
| 9. Save an incomplete baseline | Denying a read for one document preserves the healthy file, the incomplete flag and the document's error in the queued and saved baseline. |
| 10. Save to an existing destination | The queue carries an empty payload and an error naming the destination. Its existing contents survive. |
| 11. Load a saved baseline | The queue carries the expected baseline and a success message identifying the source. |
| 12. Load corrupted JSON | The worker catches the parsing error and queues an empty payload with a load error. |
| 13. Load for a different folder | The worker rejects the folder mismatch and queues the reason. |
| 14. Compare after an edit and an addition | The worker returns the comparison and a text report identifying both changes and the correct total. |
| 15. Compare with a denied read | The report warns of incomplete verification, identifies the unverified document and records the read error. The healthy file remains unchanged. |

## Security advisories, phase 5

The [six advisory tests](../tests/test_advisory_integration.py) supply local responses or exceptions at the HTTP request boundary. Refresh uses the production fetch function, HTML parser and advisory manager.

| Scenario | Expected and verified outcome |
| --- | --- |
| 16. Successful retrieval | The manager returns success, extracts titles, dates when present and absolute source URLs, and records a UTC retrieval time. |
| 17. HTTP error after success | A 503 response records the HTTP error and preserves the previous advisories and retrieval time. |
| 18. Timeout after success | A request timeout returns a failed refresh with a timeout message and preserves the previous data and time. |
| 19. Unexpected HTML | An HTTP-success page without valid advisories produces an extraction error and preserves the last successful refresh. |
| 20. Recovery | A successful refresh after a 502 error replaces the old advisory list and clears the error. |
| 21. Local monitoring during an advisory outage | After a connection failure, a real folder can still be scanned, saved, reloaded and compared. Text and CSV identify the local edit, and the baseline bytes survive. |

## Milestone 3 error handling and limits

- **Interrupted baseline saves.** JSON is written, flushed and closed in a temporary file before publication with a hard link. A concurrent destination creation cannot overwrite an existing baseline. Tests cover partial writes, interruption, publication and cleanup failures, including preserving the original error when cleanup also fails. A forcibly terminated process can leave a temporary file. [Baseline manager tests](../tests/test_baseline_manager.py)
- **Malformed baseline errors.** Validation rejects unsafe error paths and invalid kinds before comparison. It accepts file, folder and entry kinds, the root marker `.`, and legacy records without a kind. Tests cover rejection before scanning and legacy records through CSV export. [Validation regressions](../tests/test_baseline_manager.py)
- **Files changing during verification.** The hasher checks the opened file's identity, size and modification time and checks the path again after reading. Observed replacement, disappearance or unavailable identity produces a failed verification. A file can still change after the final check. [File verification tests](../tests/test_file_verification.py)

Advisory tests run offline. They verify behavior for the supplied HTML and simulated transport failures, so live site availability and compatibility with future site layouts require separate checks. Desktop tests run without a graphical display. Their scope ends at the worker queue; Tk event-loop scheduling, button states, rendering and responsiveness require a separate UI check. Permission and publication failures are selectively injected so results do not depend on the machine's access permissions.
