import sys
from utils.file_handler import read_file, save_temp_file
from api.annotator import annotate_code
from api.verifier import verify_code
from pipeline import run_pipeline

def main():
    if len(sys.argv) < 2:
        print("No file provided.")
        sys.exit(1)

    file_path = sys.argv[1]
    source_code = read_file(file_path)

    results = run_pipeline(source_code)
    print(results)

if __name__ == "__main__":
    main()
