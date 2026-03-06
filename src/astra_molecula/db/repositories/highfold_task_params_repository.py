"""
HighFold-C2C 任务参数的数据库操作类
"""
import logging
from typing import Optional

from astra_molecula.db.db import get_connection
from astra_molecula.db.models.highfold_task_params import HighFoldTaskParams

logger = logging.getLogger("highfold_task_params_repository")


class HighFoldTaskParamsRepository:
    """HighFold-C2C 任务参数的数据库操作类"""

    @staticmethod
    def create_table_if_not_exists():
        """创建 highfold_task_params 表（如果不存在）"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS highfold_task_params (
                id CHAR(32) NOT NULL,
                task_id CHAR(36) NOT NULL,

                -- C2C 序列生成参数 (Stage 1)
                core_sequence VARCHAR(50) DEFAULT NULL,
                span_len INT DEFAULT 5,
                num_sample INT DEFAULT 20,
                temperature DECIMAL(4,2) DEFAULT 1.0,
                top_p DECIMAL(4,2) DEFAULT 0.9,
                seed INT DEFAULT 42,

                -- HighFold 结构预测参数 (Stage 2)
                model_type VARCHAR(50) DEFAULT 'alphafold2',
                msa_mode VARCHAR(50) DEFAULT 'single_sequence',
                disulfide_bond_pairs VARCHAR(255) DEFAULT NULL,
                num_models INT DEFAULT 5,
                num_recycle INT DEFAULT NULL,
                use_templates BOOLEAN DEFAULT FALSE,
                amber BOOLEAN DEFAULT FALSE,
                num_relax INT DEFAULT 0,

                -- 阶段控制
                skip_generate BOOLEAN DEFAULT FALSE,
                skip_predict BOOLEAN DEFAULT FALSE,
                skip_evaluate BOOLEAN DEFAULT FALSE,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                PRIMARY KEY (id),
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_highfold_task_params_task_id ON highfold_task_params(task_id);
            """
            cursor.execute(create_table_sql)
            conn.commit()
            logger.info("Table highfold_task_params created or already exists")
        except Exception as e:
            logger.error("Failed to create highfold_task_params table: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def create(params: HighFoldTaskParams) -> None:
        """创建新的 HighFold-C2C 任务参数记录"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            sql = """
            INSERT INTO highfold_task_params (
                id, task_id,
                core_sequence, span_len, num_sample,
                temperature, top_p, seed,
                model_type, msa_mode, disulfide_bond_pairs,
                num_models, num_recycle, use_templates,
                amber, num_relax,
                skip_generate, skip_predict, skip_evaluate
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                params.id, params.task_id,
                params.core_sequence, params.span_len, params.num_sample,
                params.temperature, params.top_p, params.seed,
                params.model_type, params.msa_mode, params.disulfide_bond_pairs,
                params.num_models, params.num_recycle, params.use_templates,
                params.amber, params.num_relax,
                params.skip_generate, params.skip_predict, params.skip_evaluate
            ))
            conn.commit()
            logger.debug("HighFold task params created: id=%s, task_id=%s, core=%s",
                         params.id, params.task_id, params.core_sequence)
        except Exception as e:
            logger.error("Failed to create highfold task params: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_by_task_id(task_id: str) -> Optional[HighFoldTaskParams]:
        """根据任务 ID 获取参数"""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            sql = """
            SELECT id, task_id,
                   core_sequence, span_len, num_sample,
                   temperature, top_p, seed,
                   model_type, msa_mode, disulfide_bond_pairs,
                   num_models, num_recycle, use_templates,
                   amber, num_relax,
                   skip_generate, skip_predict, skip_evaluate,
                   created_at, updated_at
            FROM highfold_task_params WHERE task_id = %s
            """
            cursor.execute(sql, (task_id,))
            row = cursor.fetchone()

            if row:
                return HighFoldTaskParams(
                    id=row[0], task_id=row[1],
                    core_sequence=row[2], span_len=row[3], num_sample=row[4],
                    temperature=float(row[5]) if row[5] is not None else 1.0,
                    top_p=float(row[6]) if row[6] is not None else 0.9,
                    seed=row[7],
                    model_type=row[8], msa_mode=row[9], disulfide_bond_pairs=row[10],
                    num_models=row[11], num_recycle=row[12], use_templates=row[13],
                    amber=row[14], num_relax=row[15],
                    skip_generate=row[16], skip_predict=row[17], skip_evaluate=row[18],
                    created_at=row[19], updated_at=row[20]
                )
            return None
        except Exception as e:
            logger.error("Failed to get highfold task params by task_id %s: %s", task_id, e)
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
            sql = "DELETE FROM highfold_task_params WHERE task_id = %s"
            cursor.execute(sql, (task_id,))
            conn.commit()
            logger.debug("HighFold task params deleted for task: %s", task_id)
            return True
        except Exception as e:
            logger.error("Failed to delete highfold task params for task %s: %s", task_id, e)
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()
