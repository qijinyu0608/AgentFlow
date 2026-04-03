"""
Initialize test data for development
"""

from datetime import datetime, timedelta
from .database import db_manager
from .models import Task, TaskStatus


def init_test_data():
    """Initialize test data in database"""
    
    # Sample test tasks
    test_tasks = [
        {
            "task_id": "task_001",
            "task_status": TaskStatus.RUNNING,
            "task_name": "数据分析任务",
            "task_content": "分析用户行为数据，生成报告",
            "submit_time": datetime.now() - timedelta(hours=2)
        },
        {
            "task_id": "task_002",
            "task_status": TaskStatus.SUCCESS,
            "task_name": "文档生成任务",
            "task_content": "根据模板生成用户手册",
            "submit_time": datetime.now() - timedelta(hours=4)
        },
        {
            "task_id": "task_003",
            "task_status": TaskStatus.FAILED,
            "task_name": "邮件发送任务",
            "task_content": "批量发送营销邮件",
            "submit_time": datetime.now() - timedelta(hours=6)
        },
        {
            "task_id": "task_004",
            "task_status": TaskStatus.SUCCESS,
            "task_name": "AI模型训练",
            "task_content": "训练新的机器学习模型",
            "submit_time": datetime.now() - timedelta(hours=8)
        },
        {
            "task_id": "task_005",
            "task_status": TaskStatus.PAUSED,
            "task_name": "数据备份任务",
            "task_content": "备份系统数据到云端",
            "submit_time": datetime.now() - timedelta(hours=10)
        }
    ]
    
    # Insert test data
    from ..service.task_service import task_service
    
    for task_data in test_tasks:
        task = Task(**task_data)
        success = task_service.create_task(task)
        if success:
            print(f"Created test task: {task.task_id}")
        else:
            print(f"Failed to create test task: {task.task_id}")


if __name__ == "__main__":
    init_test_data() 