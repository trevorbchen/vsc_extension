# vsc_extension
---

## 🚀 Usage

1. Open VS Code, and load this extension in `development mode`.
2. Open any `.c` source file.
3. Run the command **"Run Full Verification Pipeline"** from the Command Palette.
4. The extension will:
   - Grab the file content.
   - Resolve dependencies.
   - Send code to **API #1** (annotation).
   - Send annotated version to **API #2** (verification).
   - Show results inside VS Code.

---

## ⚠️ Notes

- APIs (`api/annotator.py` and `api/verifier.py`) are **stubs**. Replace them with actual calls once the APIs are ready.
- Dependency resolution assumes external libraries are already verified. The `dependency.py` module currently just tracks which imports are internal vs external.

# VS Code Formal Verifier Extension (Prototype)

This project is a prototype of a **VS Code extension** that integrates with external APIs to perform **formal verification of C programs** using ACSL annotations and tools like **Frama-C**.

---

## ✅ Current Features

- Reads the active file in VS Code.
- Parses and classifies dependencies:
  - Internal (`"myfile.h"`) → loaded and inlined into the verification pipeline.
  - External (`<stdio.h>`) → ignored (assumed pre-verified).
- Calls **Annotation API (API #1)** (currently stubbed).
- Calls **Verification API (API #2)** (currently stubbed).
- Saves annotated code to a temporary file for debugging.
- Displays verification results back to the user (simple formatted text).

This project is **not production-ready**. Key gaps include:

### 1. **API Integration**
- **Annotator API (#1):**
  - Currently just returns `"/* ACSL annotations here */" + code`.
  - Needs actual implementation once the annotation service is available.
  - Open question: Will this be a REST API, local binary, or another service?
- **Verifier API (#2):**
  - Currently returns a hardcoded failure message.
  - Needs actual integration with Frama-C or chosen verification backend.
  - Define expected response schema (e.g., JSON `{ verified: bool, errors: [str] }`).

---

### 2. **Dependency Handling**
- Current implementation:
  - Extracts `#include` lines.
  - Splits into "internal" (in-project `.h` files) and "external" (assumed verified).
  - Naively inlines internal file contents into one blob of code.
- Issues:
  - This may cause double definitions if multiple files define the same function.
  - No AST-level merging → could break in complex projects.
- Future improvements:
  - Use `pycparser` to properly parse and merge C files.
  - Track dependency graphs across multiple files instead of naive concatenation.
  - Cache already-verified internal modules.

---

### 3. **Error Reporting & UI**
- Currently results are printed as plain text to VS Code.
- Needs:
  - Diagnostics integration (red squiggles under failing lines).
  - A webview or custom panel for structured results.
  - Clear mapping from verification errors → source code locations.

---

### 4. **Config & Flexibility**
- API endpoints are hardcoded placeholders.
- Should move to:
  - `settings.json` → configurable endpoints.
  - Environment variables for auth tokens, etc.
- User should be able to toggle:
  - Whether dependencies are inlined or skipped.
  - Whether temporary files are preserved for debugging.

---

### 5. **Testing & Reliability**
- No automated tests yet.
- Next steps:
  - Unit tests for `dependency.py`.
  - Mock APIs for `annotator` and `verifier`.
  - Integration test: run pipeline on a simple C file and assert expected verification output.

---

## 🚀 Next Steps

1. Define the **real APIs** (spec: input/output format, REST vs CLI, error cases).
2. Replace `annotator.py` and `verifier.py` stubs with actual implementations.
3. Improve dependency handling:
   - Start with project-local `.h` files.
   - Move toward AST-level parsing with `pycparser`.
4. Enhance VS Code UI:
   - Use diagnostics to highlight failed verification lines.
   - Add status bar feedback (`Verifying… ✅/❌`).
5. Add tests and CI.

---

## 🛠 Example Run (Current State)

C file `main.c`:
```c
#include <stdio.h>
#include "math_utils.h"

int main() {
    return add(2, 3);
}