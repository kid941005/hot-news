from backend.api import main


class DummyScheduler:
    def __init__(self, running=False):
        self.running = running
        self.jobs = []
        self.started = 0
        self.shutdowns = 0

    def add_job(self, *args, **kwargs):
        self.jobs.append((args, kwargs))

    def start(self):
        self.started += 1
        self.running = True

    def shutdown(self, wait=False):
        self.shutdowns += 1
        self.running = False


def test_start_scheduler_skips_when_already_running(monkeypatch):
    scheduler = DummyScheduler(running=True)
    monkeypatch.setattr(main, "scheduler", scheduler)

    main.start_scheduler()

    assert scheduler.jobs == []
    assert scheduler.started == 0


def test_start_scheduler_registers_jobs_with_replace_existing(monkeypatch):
    scheduler = DummyScheduler(running=False)
    monkeypatch.setattr(main, "scheduler", scheduler)

    main.start_scheduler()

    assert scheduler.started == 1
    assert len(scheduler.jobs) == 2
    assert all(job[1]["replace_existing"] is True for job in scheduler.jobs)


def test_stop_scheduler_skips_when_not_running(monkeypatch):
    scheduler = DummyScheduler(running=False)
    monkeypatch.setattr(main, "scheduler", scheduler)

    main.stop_scheduler()

    assert scheduler.shutdowns == 0
