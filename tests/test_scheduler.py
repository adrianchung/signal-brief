from unittest.mock import MagicMock, patch, call

from src.pipeline import run_pipeline
from src.scheduler import start


def make_config(times="08:00,17:00"):
    cfg = MagicMock()
    cfg.schedule_time_list = [t.strip() for t in times.split(",") if t.strip()]
    return cfg


class TestStart:
    def test_adds_job_for_each_valid_time(self):
        config = make_config("08:00,17:00")
        with patch("src.scheduler.BlockingScheduler") as mock_sched_cls, \
             patch("src.scheduler.CronTrigger"):
            mock_sched = mock_sched_cls.return_value
            mock_sched.get_jobs.return_value = ["job1", "job2"]
            start(config, provider="gemini")

        assert mock_sched.add_job.call_count == 2

    def test_cron_trigger_uses_correct_hour_and_minute(self):
        config = make_config("09:30")
        with patch("src.scheduler.BlockingScheduler") as mock_sched_cls, \
             patch("src.scheduler.CronTrigger") as mock_trigger_cls:
            mock_sched = mock_sched_cls.return_value
            mock_sched.get_jobs.return_value = ["job1"]
            start(config, provider="gemini")

        mock_trigger_cls.assert_called_once_with(hour=9, minute=30)

    def test_invalid_time_format_skipped(self):
        config = make_config("bad-time,08:00")
        with patch("src.scheduler.BlockingScheduler") as mock_sched_cls, \
             patch("src.scheduler.CronTrigger"):
            mock_sched = mock_sched_cls.return_value
            mock_sched.get_jobs.return_value = ["job1"]
            start(config, provider="gemini")

        assert mock_sched.add_job.call_count == 1

    def test_no_valid_times_does_not_start_scheduler(self):
        config = make_config("bad-time")
        with patch("src.scheduler.BlockingScheduler") as mock_sched_cls:
            mock_sched = mock_sched_cls.return_value
            mock_sched.get_jobs.return_value = []
            start(config, provider="gemini")

        mock_sched.start.assert_not_called()

    def test_scheduler_starts_when_jobs_configured(self):
        config = make_config("08:00")
        with patch("src.scheduler.BlockingScheduler") as mock_sched_cls, \
             patch("src.scheduler.CronTrigger"):
            mock_sched = mock_sched_cls.return_value
            mock_sched.get_jobs.return_value = ["job1"]
            start(config, provider="gemini")

        mock_sched.start.assert_called_once()

    def test_run_pipeline_is_the_scheduled_job(self):
        config = make_config("08:00")
        with patch("src.scheduler.BlockingScheduler") as mock_sched_cls, \
             patch("src.scheduler.CronTrigger"):
            mock_sched = mock_sched_cls.return_value
            mock_sched.get_jobs.return_value = ["job1"]
            start(config, provider="gemini")

        scheduled_func = mock_sched.add_job.call_args[0][0]
        assert scheduled_func is run_pipeline

    def test_provider_passed_as_job_arg(self):
        config = make_config("08:00")
        with patch("src.scheduler.BlockingScheduler") as mock_sched_cls, \
             patch("src.scheduler.CronTrigger"):
            mock_sched = mock_sched_cls.return_value
            mock_sched.get_jobs.return_value = ["job1"]
            start(config, provider="claude")

        job_args = mock_sched.add_job.call_args[1]["args"]
        assert "claude" in job_args

    def test_config_passed_as_job_arg(self):
        config = make_config("08:00")
        with patch("src.scheduler.BlockingScheduler") as mock_sched_cls, \
             patch("src.scheduler.CronTrigger"):
            mock_sched = mock_sched_cls.return_value
            mock_sched.get_jobs.return_value = ["job1"]
            start(config, provider="gemini")

        job_args = mock_sched.add_job.call_args[1]["args"]
        assert config in job_args

    def test_empty_schedule_list_does_not_start_scheduler(self):
        config = make_config("")
        config.schedule_time_list = []
        with patch("src.scheduler.BlockingScheduler") as mock_sched_cls:
            mock_sched = mock_sched_cls.return_value
            mock_sched.get_jobs.return_value = []
            start(config, provider="gemini")

        mock_sched.start.assert_not_called()
