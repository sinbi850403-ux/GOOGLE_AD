"""GUI 실행 진입점 - 프로젝트 루트에서 실행: python run_gui.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from gui import main
main()
