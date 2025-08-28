from api.annotator import annotate_code
from api.verifier import verify_code
from utils.file_handler import save_temp_file
from utils.dependency import extract_includes, classify_dependencies, resolve_internal_dependencies
from ui.results import format_results

import os

def run_pipeline(source_code: str, project_root: str = ".") -> str:
    """
    Run the full annotation → verification pipeline.
    Steps:
      1. Extract and classify dependencies.
      2. Inline internal dependencies (assume externals are verified).
      3. Call annotation API (#1).
      4. Save annotated code to a temporary file.
      5. Call verification API (#2).
      6. Format results for frontend consumption.
    """

    # Step 1: Dependency extraction
    includes = extract_includes(source_code)
    deps = classify_dependencies(includes, project_root)
    internal_sources = resolve_internal_dependencies(deps["internal"], project_root)

    # Step 2: Inline internal dependencies (append their code)
    # NOTE: This is a naive approach – ideally you'd parse the AST and merge headers safely
    combined_code = ""
    for fname, content in internal_sources.items():
        combined_code += f"\n/* Inlined from {fname} */\n"
        combined_code += content + "\n"

    combined_code += "\n/* Original source file */\n" + source_code

    # Step 3: Annotate via API #1 (stubbed)
    annotated_code = annotate_code(combined_code)

    # Step 4: Save annotated version to temp file
    temp_file = save_temp_file(annotated_code)

    # Step 5: Verify via API #2 (stubbed)
    verification_result = verify_code(annotated_code)

    # Step 6: Format results
    return format_results(verification_result)
