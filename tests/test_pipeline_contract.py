import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))

import aggregate_chunks  # noqa: E402
import main  # noqa: E402


class PipelineContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = {
            "keywords_include": ["chief of staff", "strategy and operations", "business operations"],
            "keywords_exclude": ["clinical operations"],
            "validate_job_links": False,
            "link_check_delay_seconds": 0.0,
            "max_job_age_days": 30,
            "keep_missing_dates": True,
            "strict_chief_title_required": True,
            "include_adjacent_roles": True,
        }
        self.raw_jobs = [
            {
                "platform": "greenhouse",
                "company": "alpha",
                "title": "Chief of Staff",
                "location": "New York, NY",
                "department": "Office of the CEO",
                "team": "Executive",
                "employment_type": "Full-time",
                "description": "Chief of staff role",
                "posted_at": "2026-03-10T00:00:00Z",
                "updated_at": "2026-03-10T00:00:00Z",
                "url": "https://example.com/chief",
            },
            {
                "platform": "lever",
                "company": "beta",
                "title": "Strategy and Operations Lead",
                "location": "Remote",
                "department": "Business Operations",
                "team": "Strategy",
                "employment_type": "Full-time",
                "description": "Strategy and operations role",
                "posted_at": "2026-03-11T00:00:00Z",
                "updated_at": "2026-03-11T00:00:00Z",
                "url": "https://example.com/strategy",
            },
            {
                "platform": "greenhouse",
                "company": "alpha",
                "title": "Chief of Staff",
                "location": "San Francisco, CA",
                "department": "Office of the CEO",
                "team": "Executive",
                "employment_type": "Full-time",
                "description": "Chief of staff role with longer description for dedupe",
                "posted_at": "2026-03-09T00:00:00Z",
                "updated_at": "2026-03-12T00:00:00Z",
                "url": "https://example.com/chief",
            },
        ]

    def test_process_jobs_pipeline_sets_expected_flags(self) -> None:
        result = main.process_jobs_pipeline(self.raw_jobs, self.cfg, previous_jobs=[], run_at="2026-03-13T12:00:00Z")

        self.assertEqual(len(result.jobs), 2)
        self.assertEqual(len(result.chief_jobs), 1)
        self.assertEqual(len(result.strategy_ops_jobs), 2)
        self.assertEqual(result.run_stats["new_count"], 2)

        chief_job = next(job for job in result.jobs if job["title"] == "Chief of Staff")
        strategy_job = next(job for job in result.jobs if job["title"] == "Strategy and Operations Lead")

        self.assertTrue(chief_job["is_chief_of_staff"])
        self.assertTrue(chief_job["is_strategy_ops"])
        self.assertTrue(strategy_job["is_strategy_ops"])
        self.assertFalse(strategy_job["is_chief_of_staff"])
        self.assertIn("New York, NY", chief_job["location"])
        self.assertIn("San Francisco, CA", chief_job["location"])

    def test_aggregate_chunk_loader_skips_invalid_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            chunks_dir = Path(temp_dir)
            (chunks_dir / "jobs_greenhouse_0.json").write_text(json.dumps(self.raw_jobs[:1]), encoding="utf-8")
            (chunks_dir / "jobs_lever_0.json").write_text("{not json", encoding="utf-8")
            (chunks_dir / "jobs_ashby_0.json").write_text(json.dumps({"unexpected": "shape"}), encoding="utf-8")

            jobs, platform_jobs, platform_files, invalid_files = aggregate_chunks._load_chunk_jobs(chunks_dir)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(platform_jobs["greenhouse"], 1)
        self.assertEqual(platform_files["lever"], 1)
        self.assertCountEqual(invalid_files, ["jobs_lever_0.json", "jobs_ashby_0.json"])

    def test_write_outputs_signature_matches_aggregate_usage(self) -> None:
        result = main.process_jobs_pipeline(self.raw_jobs, self.cfg, previous_jobs=[], run_at="2026-03-13T12:00:00Z")
        with tempfile.TemporaryDirectory() as temp_dir:
            original_root = main.ROOT
            original_jobs_json = main.JOBS_JSON
            original_jobs_csv = main.JOBS_CSV
            original_docs_html = main.DOCS_HTML
            original_jobs_chief_json = main.JOBS_CHIEF_JSON
            original_jobs_chief_csv = main.JOBS_CHIEF_CSV
            original_jobs_strategy_json = main.JOBS_STRATEGY_OPS_JSON
            original_jobs_strategy_csv = main.JOBS_STRATEGY_OPS_CSV
            try:
                temp_root = Path(temp_dir)
                main.ROOT = temp_root
                main.JOBS_JSON = temp_root / "jobs.json"
                main.JOBS_CSV = temp_root / "jobs.csv"
                main.DOCS_HTML = temp_root / "docs" / "index.html"
                main.JOBS_CHIEF_JSON = temp_root / "jobs_chief_of_staff.json"
                main.JOBS_CHIEF_CSV = temp_root / "jobs_chief_of_staff.csv"
                main.JOBS_STRATEGY_OPS_JSON = temp_root / "jobs_strategy_ops.json"
                main.JOBS_STRATEGY_OPS_CSV = temp_root / "jobs_strategy_ops.csv"

                main.write_outputs(result.jobs, result.chief_jobs, result.strategy_ops_jobs, github_pages_url="")

                self.assertTrue(main.JOBS_JSON.exists())
                self.assertTrue(main.JOBS_CHIEF_JSON.exists())
                self.assertTrue(main.JOBS_STRATEGY_OPS_JSON.exists())
                self.assertTrue(main.DOCS_HTML.exists())
            finally:
                main.ROOT = original_root
                main.JOBS_JSON = original_jobs_json
                main.JOBS_CSV = original_jobs_csv
                main.DOCS_HTML = original_docs_html
                main.JOBS_CHIEF_JSON = original_jobs_chief_json
                main.JOBS_CHIEF_CSV = original_jobs_chief_csv
                main.JOBS_STRATEGY_OPS_JSON = original_jobs_strategy_json
                main.JOBS_STRATEGY_OPS_CSV = original_jobs_strategy_csv


if __name__ == "__main__":
    unittest.main()
