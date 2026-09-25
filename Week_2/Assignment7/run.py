import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent / "sources"))

from runner import run_source
from storage import DB_PATH, init_db
from iiser_pune import SOURCE     # uses saved fixture or live site

init_db(DB_PATH)
result = run_source(SOURCE)
print(result)