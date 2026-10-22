from task2a import run_2a
from task2b import run_2b
from task2c import run_2c
 
 
if __name__ == "__main__":
    autonomy = run_2a()
    sim = run_2b()
    run_2c(sim, autonomy)