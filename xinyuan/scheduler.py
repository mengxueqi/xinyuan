from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from tasks.pipeline import run_scheduled_pipeline
from tasks.report import generate_daily_report


TIMEZONE = "Asia/Shanghai"


def configure_jobs(scheduler) -> None:
    scheduler.add_job(
        run_scheduled_pipeline,
        CronTrigger(hour=9, minute=0, timezone=TIMEZONE),
        id="pipeline_morning",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_scheduled_pipeline,
        CronTrigger(hour=16, minute=0, timezone=TIMEZONE),
        id="pipeline_afternoon",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        generate_daily_report,
        CronTrigger(hour=8, minute=30, timezone=TIMEZONE),
        id="daily_report",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone=TIMEZONE)
    configure_jobs(scheduler)
    return scheduler


def print_job_summary(scheduler: BlockingScheduler) -> None:
    print("Configured jobs:")
    for job in scheduler.get_jobs():
        next_run_time = getattr(job, "next_run_time", None)
        print(f"- {job.id}: next run at {next_run_time}")


if __name__ == "__main__":
    scheduler = build_scheduler()
    print_job_summary(scheduler)
    print("Scheduler started. Press Ctrl+C to stop.")
    scheduler.start()
