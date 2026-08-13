import os
import zipfile

output_zip = "TeamTrau_Downloader_Anime_portable.zip"

exclusions_dir = {
    ".git",
    ".venv",
    "downloads",
    "log-test",
    "logs",
    ".pytest_cache",
    ".ruff_cache",
    ".vscode",
    "scratch",
    ".codegraph",
    ".context-builder",
    "joyful_babbage.egg-info",
    "__pycache__",
    "Ling Cage",
    "The Villager of Level 999"
}

exclusions_files = {
    output_zip,
    "download_subtitle_portable.zip"
}

count = 0

with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in exclusions_dir and not d.endswith(".egg-info")]
        for f in files:
            if f in exclusions_files or f.endswith(".zip"):
                continue
            filepath = os.path.join(root, f)
            arcname = os.path.relpath(filepath, ".")
            zf.write(filepath, arcname)
            count += 1

zip_size = os.path.getsize(output_zip)
print(f"File: {output_zip} | Files: {count} | Size: {zip_size / (1024*1024):.2f} MB")
