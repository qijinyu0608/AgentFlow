from typing import List, Optional
from datetime import datetime
import sqlite3

from ..common.database import conversation_db_manager
from ..common.models import Task, TaskQueryRequest, TaskQueryResponse, TaskStatus


class TaskService:
    """Task service for business logic"""
    
    def __init__(self):
        self.db_manager = conversation_db_manager
    
    def query_tasks(self, request: TaskQueryRequest) -> TaskQueryResponse:
        """Query tasks with pagination and filters"""
        # Build query conditions
        conditions = []
        params = []
        
        if request.status:
            conditions.append("task_status = ?")
            params.append(request.status.value)
        
        if request.task_name:
            conditions.append("task_name LIKE ?")
            params.append(f"%{request.task_name}%")
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # Count total records
        count_query = f"SELECT COUNT(*) FROM tasks WHERE {where_clause}"
        total_result = self.db_manager.execute_query(count_query, tuple(params))
        total = total_result[0][0] if total_result else 0
        
        # Calculate offset
        offset = (request.page - 1) * request.page_size
        
        # Query tasks with pagination
        query = f"""
            SELECT task_id, task_status, task_name, task_content, submit_time
            FROM tasks 
            WHERE {where_clause}
            ORDER BY submit_time DESC
            LIMIT ? OFFSET ?
        """
        params.extend([request.page_size, offset])
        
        results = self.db_manager.execute_query(query, tuple(params))
        
        # Convert to Task objects
        tasks = []
        for row in results:
            task = Task(
                task_id=row['task_id'],
                task_status=TaskStatus(row['task_status']),
                task_name=row['task_name'],
                task_content=row['task_content'],
                submit_time=datetime.fromisoformat(row['submit_time'])
            )
            tasks.append(task)
        
        return TaskQueryResponse(
            total=total,
            page=request.page,
            page_size=request.page_size,
            tasks=tasks
        )
    
    def create_task(self, task: Task) -> bool:
        """Create a new task"""
        query = """
            INSERT INTO tasks (task_id, task_status, task_name, task_content, submit_time)
            VALUES (?, ?, ?, ?, ?)
        """
        params = (
            task.task_id,
            task.task_status.value,
            task.task_name,
            task.task_content,
            task.submit_time.isoformat()
        )
        
        try:
            affected_rows = self.db_manager.execute_update(query, params)
            return affected_rows > 0
        except sqlite3.IntegrityError:
            # Task ID already exists
            return False
    
    def update_task_status(self, task_id: str, status: TaskStatus) -> bool:
        """Update task status"""
        query = """
            UPDATE tasks 
            SET task_status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
        """
        params = (status.value, task_id)
        
        affected_rows = self.db_manager.execute_update(query, params)
        return affected_rows > 0
    
    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        query = """
            SELECT task_id, task_status, task_name, task_content, submit_time
            FROM tasks 
            WHERE task_id = ?
        """
        
        results = self.db_manager.execute_query(query, (task_id,))
        
        if not results:
            return None
        
        row = results[0]
        return Task(
            task_id=row['task_id'],
            task_status=TaskStatus(row['task_status']),
            task_name=row['task_name'],
            task_content=row['task_content'],
            submit_time=datetime.fromisoformat(row['submit_time'])
        )


# Global task service instance
task_service = TaskService() 