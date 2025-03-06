"""
Scheduler for executing actions at specified intervals.
"""
import asyncio
import time
from datetime import datetime
from loguru import logger
from typing import Dict, Any, Callable, List, Optional


class Scheduler:
    """
    Scheduler for executing actions at specified intervals.
    """
    def __init__(self):
        self.tasks = {}
        self.running = False
        
    async def start(self):
        """
        Start the scheduler.
        """
        self.running = True
        logger.info("Scheduler started")
        
    async def stop(self):
        """
        Stop the scheduler and cancel all tasks.
        """
        self.running = False
        
        # Cancel all running tasks
        for task_id, task_info in list(self.tasks.items()):
            if task_info["task"] and not task_info["task"].done():
                task_info["task"].cancel()
                
        self.tasks = {}
        logger.info("Scheduler stopped")
        
    async def add_task(self, 
                      task_id: str, 
                      callback: Callable, 
                      interval_minutes: int,
                      args: Optional[List] = None,
                      kwargs: Optional[Dict[str, Any]] = None):
        """
        Add a task to be executed at the specified interval.
        
        Args:
            task_id: Unique identifier for the task
            callback: Function to call
            interval_minutes: Interval in minutes
            args: Positional arguments to pass to the callback
            kwargs: Keyword arguments to pass to the callback
        """
        if task_id in self.tasks:
            logger.warning(f"Task {task_id} already exists, removing old task")
            await self.remove_task(task_id)
            
        task_info = {
            "callback": callback,
            "interval_seconds": interval_minutes * 60,
            "args": args or [],
            "kwargs": kwargs or {},
            "last_run": None,
            "next_run": time.time(),
            "task": None
        }
        
        self.tasks[task_id] = task_info
        
        # Start the task
        if self.running:
            task_info["task"] = asyncio.create_task(
                self._run_task(task_id)
            )
            
        logger.info(f"Added task {task_id} with interval {interval_minutes} minutes")
        
    async def remove_task(self, task_id: str):
        """
        Remove a task from the scheduler.
        
        Args:
            task_id: Unique identifier for the task
        """
        if task_id not in self.tasks:
            logger.warning(f"Task {task_id} does not exist")
            return
            
        task_info = self.tasks[task_id]
        
        if task_info["task"] and not task_info["task"].done():
            task_info["task"].cancel()
            
        del self.tasks[task_id]
        logger.info(f"Removed task {task_id}")
        
    async def _run_task(self, task_id: str):
        """
        Run a task at the specified interval.
        
        Args:
            task_id: Unique identifier for the task
        """
        if task_id not in self.tasks:
            logger.error(f"Task {task_id} does not exist")
            return
            
        task_info = self.tasks[task_id]
        
        while self.running:
            # Wait until next run time
            now = time.time()
            wait_time = max(0, task_info["next_run"] - now)
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                
            if not self.running or task_id not in self.tasks:
                break
                
            # Update last run and next run times
            task_info["last_run"] = time.time()
            task_info["next_run"] = task_info["last_run"] + task_info["interval_seconds"]
            
            # Execute the task
            try:
                logger.info(f"Executing task {task_id}")
                await task_info["callback"](
                    *task_info["args"],
                    **task_info["kwargs"]
                )
            except Exception as e:
                logger.exception(f"Error executing task {task_id}: {e}")
                
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a task.
        
        Args:
            task_id: Unique identifier for the task
            
        Returns:
            Dictionary with task information or None if task does not exist
        """
        if task_id not in self.tasks:
            return None
            
        task_info = self.tasks[task_id]
        
        return {
            "task_id": task_id,
            "interval_seconds": task_info["interval_seconds"],
            "last_run": datetime.fromtimestamp(task_info["last_run"]).isoformat() if task_info["last_run"] else None,
            "next_run": datetime.fromtimestamp(task_info["next_run"]).isoformat() if task_info["next_run"] else None,
            "is_running": task_info["task"] is not None and not task_info["task"].done() if task_info["task"] else False
        }
        
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all tasks.
        
        Returns:
            Dictionary mapping task IDs to task information
        """
        return {
            task_id: self.get_task_info(task_id)
            for task_id in self.tasks
        }
