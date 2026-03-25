# 调度器模块：协调各模块按流程顺序执行任务

from douyin_automation.scheduler.celery_app import celery_app

__all__ = ["celery_app"]
