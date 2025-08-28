def format_results(result: dict) -> str:
    if result["verified"]:
        return "✅ Verification successful! No errors found."
    else:
        errors = "\n".join(f"- {e}" for e in result["errors"])
        return f"❌ Verification failed:\n{errors}"
