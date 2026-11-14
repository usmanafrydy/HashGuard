# HashGuard Course Alignment

This document maps the Software Construction and Development course
topics to planned work in HashGuard. These mappings are plans, not
claims that the features have already been implemented.

Web scraping is mandatory based on the instructor's explicit instruction.
Other mappings will be refined as development progresses and further
project instructions are received.

| Week | Course Topic | Planned Application in HashGuard |
| --- | --- | --- |
| 1 | Clean code and meaningful names | Use descriptive names and small, readable functions. |
| 2 | Programming language constructs | Use appropriate conditions, loops, collections, functions, and classes. |
| 3 | Reusability, coupling, and cohesion | Separate responsibilities and reuse hashing and comparison functions. |
| 4 | Tech stack, COTS, and versioning | Document library choices and track improvements through Git and versioned releases. |
| 5 | Regular expressions | Extract CVE identifiers from advisory text where present. |
| 6 | File handling and data interchange | Read files in binary mode, store baselines in JSON, and export CSV reports. |
| 7 | Exceptions and defensive programming | Handle invalid inputs, unreadable files, invalid baselines, and retrieval failures. |
| 8 | Concurrency | Run scanning and advisory retrieval in background tasks while keeping the interface responsive. |
| 9 | Web scraping | Extract advisory information from a configured website's HTML. |
| 10 | Creational and structural patterns | Evaluate a report exporter factory and an adapter for scraped advisory data. |
| 11 | Behavioral patterns | Evaluate observer-style progress notifications for the interface. |
| 12 | Code smells and refactoring | Remove duplication and improve code structure while preserving tested behavior. |
| 13 | APIs and productivity automation | Consider an API lookup for advisory details if included in the agreed scope. |
| 14 | Secure coding | Validate inputs, protect baseline handling, and treat downloaded content as data. |
| 15 | AI-augmented construction | Use assistance for learning, review, and debugging according to the instructor's policy. |
| 16 | Presentation and evaluation | Demonstrate the application and explain the implementation and its limitations. |

## Tracking Progress

As each topic is implemented, add references to the relevant code,
tests, or documentation. Design pattern choices and the API extension
remain provisional until their need and scope are established.
