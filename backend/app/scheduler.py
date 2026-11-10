import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from app.database import get_setting, set_setting
from app.scrapers.aggregator import run_scraping_pipeline

class JobScheduler:
    def __init__(self):
        self.enabled = False
        self.interval_seconds = 2 * 3600 # 2 hours
        self.last_run: Optional[str] = None
        self.next_run_epoch: Optional[float] = None
        self.is_running = False
        self.last_result: Optional[str] = None
        self._task: Optional[asyncio.Task] = None

    def load_state(self):
        saved = get_setting("scheduler_state", {})
        self.enabled = bool(saved.get("enabled", False))
        self.interval_seconds = float(saved.get("interval_seconds", 2 * 3600))
        self.last_run = saved.get("last_run")
        self.last_result = saved.get("last_result")
        if self.enabled:
            # Set next run
            self.next_run_epoch = time.time() + self.interval_seconds

    def save_state(self):
        next_run_iso = datetime.utcfromtimestamp(self.next_run_epoch).isoformat() if self.next_run_epoch else None
        state = {
            "enabled": self.enabled,
            "interval_seconds": self.interval_seconds,
            "last_run": self.last_run,
            "next_run": next_run_iso,
            "last_result": self.last_result
        }
        set_setting("scheduler_state", state)

    def get_status(self) -> Dict[str, Any]:
        next_run_iso = datetime.utcfromtimestamp(self.next_run_epoch).isoformat() if (self.enabled and self.next_run_epoch) else None
        saved_config = get_setting("scraper_config", {})
        return {
            "enabled": self.enabled,
            "interval_hours": self.interval_seconds / 3600,
            "last_run": self.last_run,
            "next_run": next_run_iso,
            "is_running": self.is_running,
            "last_result": self.last_result,
            "saved_config": saved_config
        }

    def toggle(self, enable: bool, scraper_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.enabled = enable
        if scraper_config:
            set_setting("scraper_config", scraper_config)
            
        if self.enabled:
            self.next_run_epoch = time.time() + self.interval_seconds
        else:
            self.next_run_epoch = None
            
        self.save_state()
        return self.get_status()

    async def execute_scrape_job(self):
        if self.is_running:
            return
        self.is_running = True
        try:
            config = get_setting("scraper_config", {})
            keywords = config.get("keywords", ["Python Developer"])
            locations = config.get("locations", ["Bengaluru"])
            open_to_all = bool(config.get("open_to_all_india", False))
            sources = config.get("sources", ["linkedin", "instahyre", "indeed", "remoteok"])
            date_range = config.get("date_posted_range", "24h") # default to fresh 24h for auto-scrapes!
            exp_ranges = config.get("exp_ranges", ["all"])
            count = int(config.get("results_per_source", 10))
            li_cookie = config.get("linkedin_cookie", "")
            nk_cookie = config.get("naukri_cookie", "")

            loop = asyncio.get_event_loop()
            stats = await loop.run_in_executor(
                None,
                lambda: run_scraping_pipeline(
                    keywords=keywords,
                    locations=locations,
                    open_to_all_india=open_to_all,
                    sources=sources,
                    results_per_source=count,
                    date_posted_range=date_range,
                    exp_ranges=exp_ranges,
                    linkedin_cookie=li_cookie,
                    naukri_cookie=nk_cookie
                )
            )

            self.last_run = datetime.utcnow().isoformat()
            self.last_result = f"Auto-scraped {stats['total_scraped']} jobs ({stats['new_inserted']} new)"
            self.next_run_epoch = time.time() + self.interval_seconds
            self.save_state()
            print(f"[Scheduler] {self.last_result}")
        except Exception as e:
            self.last_result = f"Error during auto-scrape: {e}"
            print(f"[Scheduler Error] {e}")
        finally:
            self.is_running = False

    async def run_loop(self):
        while True:
            try:
                if self.enabled and self.next_run_epoch and time.time() >= self.next_run_epoch:
                    await self.execute_scrape_job()
            except Exception as e:
                print(f"[Scheduler Loop Error] {e}")
            await asyncio.sleep(15)

scheduler = JobScheduler()
