import json
import shutil
import time
from pathlib import Path
from database.services import TaskService
from database.models.task import Task
from utils.tools import run_generate_runner
from Vina.vina_workflow import vina_docking_from_list
from config import ROOT
from utils.log import get_logger

logger = get_logger("task_worker", str(ROOT / "logs" / "worker.log"), isMain=True)


def process_generate(task: Task):
    logger.info("Start generate task %s", task.id)
    job_dir = Path(task.job_dir)
    input_json = job_dir / "input.json"
    with open(input_json, "r", encoding="utf-8") as f:
        params = json.load(f)
    req_list = params.get("generateRequestList", [])
    results = []
    for req in req_list:
        res = run_generate_runner(
            req["constSmiles"],
            req["varSmiles"],
            req["mainCls"],
            req["minorCls"],
            req["deltaValue"],
            req["num"],
        )
        results.extend(res)
    with open(job_dir / "output.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info("Finished generate task %s", task.id)


def process_docking(task: Task):
    logger.info("Start docking task %s", task.id)
    job_dir = Path(task.job_dir)
    with open(job_dir / "input.json", "r", encoding="utf-8") as f:
        params = json.load(f)
    run_dir = vina_docking_from_list(
        ligands=params["ligands"],
        receptor_pdbqt=params["receptor_pdbqt"],
        min_ph=params.get("min_ph", 6.0),
        max_ph=params.get("max_ph", 8.0),
        n_jobs=params.get("n_jobs", 8),
    )
    for item in Path(run_dir).iterdir():
        shutil.move(str(item), str(job_dir / item.name))
    Path(run_dir).rmdir()
    logger.info("Finished docking task %s", task.id)


def main_loop():
    while True:
        tasks = TaskService.fetch_pending()
        logger.debug("Fetched %d pending tasks", len(tasks))
        if not tasks:
            time.sleep(5)
            continue
        for task in tasks:
            try:
                TaskService.finish_task(task.id, status="running")
                if task.task_type == "generate":
                    process_generate(task)
                elif task.task_type == "docking":
                    process_docking(task)
                TaskService.finish_task(task.id, status="finished")
            except Exception:
                logger.exception("Task %s failed", task.id)
                TaskService.finish_task(task.id, status="failed")
        time.sleep(1)

if __name__ == "__main__":
    main_loop()
