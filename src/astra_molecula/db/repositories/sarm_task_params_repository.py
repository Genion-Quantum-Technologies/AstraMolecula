"""
SARM 任务参数的数据库操作类
"""
import json
import logging
from typing import Optional

from astra_molecula.db.db import get_connection
from astra_molecula.db.models.sarm_task_params import SarmTaskParams

logger = logging.getLogger("sarm_task_params_repository")


class SarmTaskParamsRepository:
    """SARM 任务参数的数据库操作类"""

    @staticmethod
    def create_table_if_not_exists():
        """创建 sarm_task_params 表（如果不存在）"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS sarm_task_params (
                id CHAR(32) NOT NULL,
                task_id CHAR(36) NOT NULL,
                task_subtype VARCHAR(20) NOT NULL DEFAULT 'sarm',

                -- SARM 矩阵生成参数
                csv_filename VARCHAR(255) DEFAULT 'compounds.csv',
                analysis_type VARCHAR(20) DEFAULT 'smiles',
                value_columns TEXT DEFAULT '[]',
                log_transform BOOLEAN DEFAULT FALSE,
                minimum_site1 DECIMAL(10,2) DEFAULT 3,
                minimum_site2 DECIMAL(10,2) DEFAULT 3,
                n_jobs INT DEFAULT 8,
                csv2excel BOOLEAN DEFAULT FALSE,

                -- SAR 树生成参数
                fragment_core VARCHAR(1024) DEFAULT NULL,
                root_title VARCHAR(255) DEFAULT NULL,
                input_file VARCHAR(255) DEFAULT 'input.csv',
                tree_content TEXT DEFAULT '["double-cut"]',
                highlight_dict TEXT DEFAULT '[]',
                max_level INT DEFAULT 5,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                PRIMARY KEY (id),
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_sarm_task_params_task_id ON sarm_task_params(task_id);
            CREATE INDEX IF NOT EXISTS idx_sarm_task_params_subtype ON sarm_task_params(task_subtype);
            """
            cursor.execute(create_table_sql)
            conn.commit()
            logger.info("Table sarm_task_params created or already exists")
        except Exception as e:
            logger.error("Failed to create sarm_task_params table: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def create(params: SarmTaskParams) -> None:
        """创建新的 SARM 任务参数记录"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            sql = """
            INSERT INTO sarm_task_params (
                id, task_id, task_subtype,
                csv_filename, analysis_type, value_columns, log_transform,
                minimum_site1, minimum_site2, n_jobs, csv2excel,
                fragment_core, root_title, input_file,
                tree_content, highlight_dict, max_level
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                params.id, params.task_id, params.task_subtype,
                params.csv_filename, params.analysis_type, params.value_columns,
                params.log_transform, params.minimum_site1, params.minimum_site2,
                params.n_jobs, params.csv2excel,
                params.fragment_core, params.root_title, params.input_file,
                params.tree_content, params.highlight_dict, params.max_level
            ))
            conn.commit()
            logger.debug("SARM task params created: id=%s, task_id=%s, subtype=%s",
                        params.id, params.task_id, params.task_subtype)
        except Exception as e:
            logger.error("Failed to create sarm task params: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_by_task_id(task_id: str) -> Optional[SarmTaskParams]:
        """根据任务 ID 获取参数"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            sql = """
            SELECT id, task_id, task_subtype,
                   csv_filename, analysis_type, value_columns, log_transform,
                   minimum_site1, minimum_site2, n_jobs, csv2excel,
                   fragment_core, root_title, input_file,
                   tree_content, highlight_dict, max_level,
                   created_at, updated_at
            FROM sarm_task_params WHERE task_id = %s
            """
            cursor.execute(sql, (task_id,))
            row = cursor.fetchone()

            if row:
                return SarmTaskParams(
                    id=row[0], task_id=row[1], task_subtype=row[2],
                    csv_filename=row[3], analysis_type=row[4], value_columns=row[5],
                    log_transform=row[6], minimum_site1=row[7], minimum_site2=row[8],
                    n_jobs=row[9], csv2excel=row[10],
                    fragment_core=row[11], root_title=row[12], input_file=row[13],
                    tree_content=row[14], highlight_dict=row[15], max_level=row[16],
                    created_at=row[17], updated_at=row[18]
                )
            return None
        except Exception as e:
            logger.error("Failed to get sarm task params by task_id %s: %s", task_id, e)
            return None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def delete_by_task_id(task_id: str) -> bool:
        """根据任务 ID 删除参数记录"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            sql = "DELETE FROM sarm_task_params WHERE task_id = %s"
            cursor.execute(sql, (task_id,))
            conn.commit()
            logger.debug("SARM task params deleted for task: %s", task_id)
            return True
        except Exception as e:
            logger.error("Failed to delete sarm task params for task %s: %s", task_id, e)
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()
