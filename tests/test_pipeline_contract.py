import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))

import aggregate_chunks  # noqa: E402
import main  # noqa: E402
import scrapers  # noqa: E402


class PipelineContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = {
            "keywords_include": ["chief of staff", "strategy and operations", "business operations", "learning and development"],
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
        self.assertEqual(len(result.focused_jobs), 2)
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

    def test_learning_and_development_flag_is_set(self) -> None:
        raw_jobs = [
            {
                "platform": "lever",
                "company": "gamma",
                "title": "Learning and Development Manager",
                "location": "Remote",
                "department": "People",
                "team": "Learning and Development",
                "employment_type": "Full-time",
                "description": "Own the learning and development strategy.",
                "posted_at": "2026-03-11T00:00:00Z",
                "updated_at": "2026-03-11T00:00:00Z",
                "url": "https://example.com/ld",
            }
        ]

        result = main.process_jobs_pipeline(raw_jobs, self.cfg, previous_jobs=[], run_at="2026-03-13T12:00:00Z")

        self.assertTrue(result.jobs[0]["is_learning_and_development"])
        self.assertEqual(len(result.focused_jobs), 1)

    def test_aggregate_chunk_loader_skips_invalid_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            chunks_dir = Path(temp_dir)
            (chunks_dir / "jobs_greenhouse_0.json").write_text(json.dumps(self.raw_jobs[:1]), encoding="utf-8")
            (chunks_dir / "jobs_lever_0.json").write_text("{not json", encoding="utf-8")
            (chunks_dir / "jobs_unknown_0.json").write_text(json.dumps({"unexpected": "shape"}), encoding="utf-8")

            jobs, platform_jobs, platform_files, invalid_files = aggregate_chunks._load_chunk_jobs(chunks_dir)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(platform_jobs["greenhouse"], 1)
        self.assertEqual(platform_files["lever"], 1)
        self.assertCountEqual(invalid_files, ["jobs_lever_0.json", "jobs_unknown_0.json"])

    def test_write_outputs_signature_matches_aggregate_usage(self) -> None:
        result = main.process_jobs_pipeline(self.raw_jobs, self.cfg, previous_jobs=[], run_at="2026-03-13T12:00:00Z")
        with tempfile.TemporaryDirectory() as temp_dir:
            original_root = main.ROOT
            original_jobs_json = main.JOBS_JSON
            original_jobs_csv = main.JOBS_CSV
            original_jobs_chief_json = main.JOBS_CHIEF_JSON
            original_jobs_chief_csv = main.JOBS_CHIEF_CSV
            original_jobs_strategy_json = main.JOBS_STRATEGY_OPS_JSON
            original_jobs_strategy_csv = main.JOBS_STRATEGY_OPS_CSV
            original_docs_data_dir = main.DOCS_DATA_DIR
            try:
                temp_root = Path(temp_dir)
                main.ROOT = temp_root
                main.JOBS_JSON = temp_root / "jobs.json"
                main.JOBS_CSV = temp_root / "jobs.csv"
                main.JOBS_CHIEF_JSON = temp_root / "jobs_chief_of_staff.json"
                main.JOBS_CHIEF_CSV = temp_root / "jobs_chief_of_staff.csv"
                main.JOBS_STRATEGY_OPS_JSON = temp_root / "jobs_strategy_ops.json"
                main.JOBS_STRATEGY_OPS_CSV = temp_root / "jobs_strategy_ops.csv"
                main.DOCS_DATA_DIR = temp_root / "docs" / "data"

                main.write_outputs(result.focused_jobs, result.chief_jobs, result.strategy_ops_jobs)

                self.assertTrue(main.JOBS_JSON.exists())
                self.assertTrue(main.JOBS_CHIEF_JSON.exists())
                self.assertTrue(main.JOBS_STRATEGY_OPS_JSON.exists())
                self.assertTrue((main.DOCS_DATA_DIR / "jobs.json").exists())
                focused_jobs = json.loads(main.JOBS_JSON.read_text(encoding="utf-8"))
                self.assertEqual(len(focused_jobs), 2)
                self.assertTrue(all(job["summary"] for job in focused_jobs))
            finally:
                main.ROOT = original_root
                main.JOBS_JSON = original_jobs_json
                main.JOBS_CSV = original_jobs_csv
                main.JOBS_CHIEF_JSON = original_jobs_chief_json
                main.JOBS_CHIEF_CSV = original_jobs_chief_csv
                main.JOBS_STRATEGY_OPS_JSON = original_jobs_strategy_json
                main.JOBS_STRATEGY_OPS_CSV = original_jobs_strategy_csv
                main.DOCS_DATA_DIR = original_docs_data_dir

    def test_fetch_lever_maps_live_style_fields(self) -> None:
        raw_job = {
            "id": "dbc3d287-2085-4329-abca-d1d85a4f0860",
            "text": "Senior Legal Counsel - Financial Services",
            "categories": {
                "department": "Legal",
                "team": "Legal",
                "commitment": "Permanent",
                "location": "Melbourne, Australia",
                "allLocations": ["Melbourne, Australia"],
            },
            "createdAt": 1773187200000,
            "descriptionPlain": "About the role",
            "openingPlain": "We are hiring.",
            "descriptionBodyPlain": "Senior legal counsel responsibilities.",
            "additionalPlain": "Benefits.",
            "hostedUrl": "https://jobs.lever.co/myob-2/dbc3d287-2085-4329-abca-d1d85a4f0860",
            "applyUrl": "https://jobs.lever.co/myob-2/dbc3d287-2085-4329-abca-d1d85a4f0860/apply",
            "workplaceType": "hybrid",
        }

        with mock.patch.object(scrapers, "_fetch_json", return_value=[raw_job]):
            jobs = scrapers.fetch_lever("myob-2")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "Senior Legal Counsel - Financial Services")
        self.assertEqual(jobs[0]["department"], "Legal")
        self.assertEqual(jobs[0]["team"], "Legal")
        self.assertEqual(jobs[0]["work_mode"], "hybrid")
        self.assertEqual(jobs[0]["url"], raw_job["hostedUrl"])
        self.assertEqual(jobs[0]["posted_at"], "2026-03-11T00:00:00Z")
        self.assertEqual(jobs[0]["updated_at"], "2026-03-11T00:00:00Z")

    def test_fetch_lever_infers_title_when_text_is_missing(self) -> None:
        raw_job = {
            "id": "a32ca7c2-43e5-404f-aab8-a01e43db69cc",
            "text": "",
            "categories": {
                "department": "Operations",
                "location": "Argentina",
                "commitment": "Remote Full Time",
            },
            "createdAt": 1773422033575,
            "descriptionPlain": "We're looking for a Data Engineer to help take our expertise to the next level.",
            "hostedUrl": "https://jobs.lever.co/muttdata/dd6fe048-650e-417f-8669-3afafa7a8c6b",
            "workplaceType": "remote",
        }

        with mock.patch.object(scrapers, "_fetch_json", return_value=[raw_job]):
            jobs = scrapers.fetch_lever("muttdata")

        self.assertEqual(jobs[0]["title"], "Data Engineer")


if __name__ == "__main__":
    unittest.main()
