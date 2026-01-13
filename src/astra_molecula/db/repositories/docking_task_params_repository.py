import logging
from datetime import datetime
from typing import Optional

from astra_molecula.db.db import get_connection
from astra_molecula.db.models.docking_task_params import DockingTaskParams

logger = logging.getLogger("database.docking_task_params_repository")


class DockingTaskParamsRepository:
    
    @staticmethod
    def create_table_if_not_exists():
        """创建docking_task_params表（如果不存在）"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS docking_task_params (
                id CHAR(36) PRIMARY KEY,
                task_id CHAR(36) NOT NULL,
                n_ligands INT NOT NULL,
                min_ph DECIMAL(3,1) NOT NULL,
                max_ph DECIMAL(3,1) NOT NULL,
                ph_factor DECIMAL(3,1) NOT NULL DEFAULT 1.5,
                center_x DECIMAL(10,3) NOT NULL,
                center_y DECIMAL(10,3) NOT NULL,
                center_z DECIMAL(10,3) NOT NULL,
                box_size_x DECIMAL(10,3) NOT NULL,
                box_size_y DECIMAL(10,3) NOT NULL,
                box_size_z DECIMAL(10,3) NOT NULL,
                box_volume DECIMAL(15,3) NOT NULL,
                exhaustiveness INT NOT NULL,
                n_poses INT NOT NULL,
                n_jobs INT NOT NULL,
                total_molecules DECIMAL(10,3) NOT NULL,
                core_docking_factor DECIMAL(15,6) NOT NULL,
                pose_generation_factor DECIMAL(10,6) NOT NULL,
                total_compute_units DECIMAL(20,6) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_docking_task_id ON docking_task_params(task_id);
            """
            cursor.execute(create_table_sql)
            conn.commit()
            logger.info("Table docking_task_params created or already exists")
        except Exception as e:
            logger.error("Failed to create docking_task_params table: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def create(params: DockingTaskParams) -> None:
        """创建新的docking任务参数记录"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            sql = """
            INSERT INTO docking_task_params (
                id, task_id, n_ligands, min_ph, max_ph, ph_factor,
                center_x, center_y, center_z, box_size_x, box_size_y, box_size_z, box_volume,
                exhaustiveness, n_poses, n_jobs, total_molecules,
                core_docking_factor, pose_generation_factor, total_compute_units
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                params.id, params.task_id, params.n_ligands, params.min_ph, params.max_ph, params.ph_factor,
                params.center_x, params.center_y, params.center_z,
                params.box_size_x, params.box_size_y, params.box_size_z, params.box_volume,
                params.exhaustiveness, params.n_poses, params.n_jobs, params.total_molecules,
                params.core_docking_factor, params.pose_generation_factor, params.total_compute_units
            ))
            conn.commit()
            logger.debug("Docking task params created: %s", params.id)
        except Exception as e:
            logger.error("Failed to create docking task params: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_by_task_id(task_id: str) -> Optional[DockingTaskParams]:
        """根据任务ID获取参数"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            sql = """
            SELECT id, task_id, n_ligands, min_ph, max_ph, ph_factor,
                   center_x, center_y, center_z, box_size_x, box_size_y, box_size_z, box_volume,
                   exhaustiveness, n_poses, n_jobs, total_molecules,
                   core_docking_factor, pose_generation_factor, total_compute_units,
                   created_at, updated_at
            FROM docking_task_params WHERE task_id = %s
            """
            cursor.execute(sql, (task_id,))
            row = cursor.fetchone()
            
            if row:
                return DockingTaskParams(
                    id=row[0], task_id=row[1], n_ligands=row[2], min_ph=row[3], max_ph=row[4], ph_factor=row[5],
                    center_x=row[6], center_y=row[7], center_z=row[8],
                    box_size_x=row[9], box_size_y=row[10], box_size_z=row[11], box_volume=row[12],
                    exhaustiveness=row[13], n_poses=row[14], n_jobs=row[15], total_molecules=row[16],
                    core_docking_factor=row[17], pose_generation_factor=row[18], total_compute_units=row[19],
                    created_at=row[20], updated_at=row[21]
                )
            return None
        except Exception as e:
            logger.error("Failed to get docking task params by task_id %s: %s", task_id, e)
            return None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def delete_by_task_id(task_id: str) -> bool:
        """根据任务ID删除参数记录"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            sql = "DELETE FROM docking_task_params WHERE task_id = %s"
            cursor.execute(sql, (task_id,))
            conn.commit()
            logger.debug("Docking task params deleted for task: %s", task_id)
            return True
        except Exception as e:
            logger.error("Failed to delete docking task params for task %s: %s", task_id, e)
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()
