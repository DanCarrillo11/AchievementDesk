"""Package a verified portable build and its corresponding source tree."""
from pathlib import Path
import shutil
import sys
import zipfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from workspace import VERSION
build = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
version = "AchievementDesk-" + VERSION
portable = output / (version + "-Portable")
if portable.exists():
    raise SystemExit("Choose a fresh release output folder.")
output.mkdir(parents=True, exist_ok=True)
shutil.copytree(build, portable)
documents = ["README.md", "LICENSE", "THIRD_PARTY_NOTICES.txt", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md"]
for name in documents:
    shutil.copy2(root / name, portable / name)
shutil.copytree(root / "licenses", portable / "licenses")
if (root / "docs").is_dir():
    shutil.copytree(root / "docs", portable / "docs")

with zipfile.ZipFile(output / (version + "-Portable.zip"), "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(portable.rglob("*")):
        if path.is_file():
            archive.write(path, path.relative_to(output))

source = sorted(root.glob("*.py")) + [root / name for name in documents]
source += [root / name for name in ("AchievementDesk.spec", "requirements.txt", "requirements-build.txt", ".gitignore", ".gitattributes", ".editorconfig", "installer.iss", "version_info.txt")]
for folder, pattern in (("tests", "*.py"), ("tools", "*.py"), ("licenses", "*.txt"), ("assets", "*.json"), ("assets", "*.ico"), ("assets", "*.png")):
    source += sorted((root / folder).glob(pattern))
source += [p for p in (root / "docs").rglob("*") if p.is_file()]
source += [p for p in (root / ".github").rglob("*") if p.is_file()]
with zipfile.ZipFile(output / (version + "-source.zip"), "w", zipfile.ZIP_DEFLATED) as archive:
    for path in source:
        archive.write(path, Path("achievement-desk") / path.relative_to(root))
print("Portable and source archives created.")
