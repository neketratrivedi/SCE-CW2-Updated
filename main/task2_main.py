import os
import runpy
from task2a import run_2a
from task2b import run_2b
from task2c import run_2c


if __name__ == "__main__":
    autonomy = run_2a()
    sim = run_2b()
    run_2c(sim, autonomy)
    # Task 2c report figures (Figures 1-3)
    runpy.run_path(os.path.join(os.path.dirname(__file__), "task2c_figures.py"))
