"""
Peptide任务参数的数据库操作类
"""
import logging
from typing import Optional
from database.db import get_connection
from database.models.peptide_task_params import PeptideTaskParams

logger = logging.getLogger("peptide_task_params_repository")


class PeptideTaskParamsRepository:
    """Peptide任务参数的数据库操作类"""
    
    @staticmethod
    def create_table_if_not_exists():
        """创建peptide_task_params表（如果不存在）"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS peptide_task_params (
                id CHAR(32) NOT NULL PRIMARY KEY,
                task_id CHAR(32) NOT NULL,
                peptide_sequence TEXT NOT NULL,
                peptide_length INT NOT NULL,
                n_iterations INT NOT NULL,
                n_rosetta_runs INT NOT NULL,
                total_calculations INT NOT NULL,
                complexity_factor DECIMAL(15,6) NOT NULL,
                total_compute_units DECIMAL(20,6) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_task_id (task_id),
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            cursor.execute(create_table_sql)
            conn.commit()
            logger.info("Table peptide_task_params created or already exists")
        except Exception as e:
            logger.error("Failed to create peptide_task_params table: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def create(params: PeptideTaskParams) -> None:
        """创建新的peptide任务参数记录"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            sql = """
            INSERT INTO peptide_task_params (
                id, task_id, peptide_sequence, peptide_length,
                n_iterations, n_rosetta_runs, total_calculations,
                complexity_factor, total_compute_units
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                params.id, params.task_id, params.peptide_sequence, params.peptide_length,
                params.n_iterations, params.n_rosetta_runs, params.total_calculations,
                params.complexity_factor, params.total_compute_units
            ))
            conn.commit()
            logger.debug("Peptide task params created: %s", params.id)
        except Exception as e:
            logger.error("Failed to create peptide task params: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_by_task_id(task_id: str) -> Optional[PeptideTaskParams]:
        """根据任务ID获取参数"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            sql = """
            SELECT id, task_id, peptide_sequence, peptide_length,
                   n_iterations, n_rosetta_runs, total_calculations,
                   complexity_factor, total_compute_units,
                   created_at, updated_at
            FROM peptide_task_params WHERE task_id = %s
            """
            cursor.execute(sql, (task_id,))
            row = cursor.fetchone()
            
            if row:
                return PeptideTaskParams(
                    id=row[0], task_id=row[1], peptide_sequence=row[2], peptide_length=row[3],
                    n_iterations=row[4], n_rosetta_runs=row[5], total_calculations=row[6],
                    complexity_factor=row[7], total_compute_units=row[8],
                    created_at=row[9], updated_at=row[10]
                )
            return None
        except Exception as e:
            logger.error("Failed to get peptide task params by task_id %s: %s", task_id, e)
            return None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def delete_by_task_id(task_id: str) -> None:
        """根据任务ID删除参数"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            sql = "DELETE FROM peptide_task_params WHERE task_id = %s"
            cursor.execute(sql, (task_id,))
            conn.commit()
            logger.debug("Deleted peptide task params for task: %s", task_id)
        except Exception as e:
            logger.error("Failed to delete peptide task params for task %s: %s", task_id, e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_all_by_date_range(start_date: str, end_date: str) -> list:
        """根据日期范围获取所有记录"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            sql = """
            SELECT id, task_id, peptide_sequence, peptide_length,
                   n_iterations, n_rosetta_runs, total_calculations,
                   complexity_factor, total_compute_units,
                   created_at, updated_at
            FROM peptide_task_params 
            WHERE DATE(created_at) BETWEEN %s AND %s
            ORDER BY created_at DESC
            """
            cursor.execute(sql, (start_date, end_date))
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append(PeptideTaskParams(
                    id=row[0], task_id=row[1], peptide_sequence=row[2], peptide_length=row[3],
                    n_iterations=row[4], n_rosetta_runs=row[5], total_calculations=row[6],
                    complexity_factor=row[7], total_compute_units=row[8],
                    created_at=row[9], updated_at=row[10]
                ))
            return results
        except Exception as e:
            logger.error("Failed to get peptide task params by date range: %s", e)
            return []
        finally:
            cursor.close()
            conn.close()
