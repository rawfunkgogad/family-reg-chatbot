# -*- coding: utf-8 -*-
"""
Test Suite for 5 Advanced Quality Architectures:
1. Sub-Query Decomposition & CRAG (Multi-Angle Retrieval)
2. Chain-of-Verification (CoVe) Judicial Fact-Checking Guardrail
3. Decision Tree / Branching Matrix Prompt Verification
4. Actionable Artifacts Binding (36 Supreme Court Form Matching & Zip Extraction)
5. In-App Citation Hover Preview & Judicial Confidence
"""

import os
import sys
import unittest

from pathlib import Path

# Add backend directory and project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
backend_dir = PROJECT_ROOT / "backend"
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(PROJECT_ROOT))

from rag.rag_service import RAGService
from rag.rig_engine import (
    FormArtifactMatcher,
    JudicialFactChecker,
    DualTierLawCache
)


class TestSubQueryDecomposition(unittest.TestCase):
    """Test Architecture 1: Sub-Query Decomposition & CRAG"""

    def setUp(self):
        self.rag = RAGService()

    def test_decompose_compound_query(self):
        query = "출생신고 기간과 과태료는 어떻게 되고 혼외자 출생신고 방법은?"
        sub_queries = self.rag.decompose_query(query)
        self.assertIsInstance(sub_queries, list)
        self.assertGreaterEqual(len(sub_queries), 2)
        # Verify original query or primary theme is included
        self.assertTrue(any("출생신고" in sq for sq in sub_queries))

    def test_decompose_single_query(self):
        query = "가족관계등록부 열람 권한"
        sub_queries = self.rag.decompose_query(query)
        self.assertIsInstance(sub_queries, list)
        self.assertGreaterEqual(len(sub_queries), 1)
        self.assertEqual(sub_queries[0], query)


class TestActionableArtifactsBinding(unittest.TestCase):
    """Test Architecture 4: 36 Official Forms & E-Family Portal Deep-linking"""

    def test_match_birth_registration(self):
        query = "아이 출생신고 서식 양식 다운로드 및 온라인 신청"
        res = FormArtifactMatcher.match(query)
        self.assertIsNotNone(res)
        forms = res if isinstance(res, list) else res.get("forms", [])
        self.assertGreaterEqual(len(forms), 1)
        self.assertTrue(any("출생신고서" in f["name"] for f in forms))
        self.assertIn("efamily_url", forms[0])

    def test_match_divorce_form(self):
        query = "협의이혼의사확인신청서 양식이 필요합니다"
        res = FormArtifactMatcher.match(query)
        self.assertIsNotNone(res)
        forms = res if isinstance(res, list) else res.get("forms", [])
        self.assertTrue(any("이혼" in f["name"] for f in forms))

    def test_get_form_file_info_from_zip(self):
        # Match birth form and verify it can extract bytes from zip
        res = FormArtifactMatcher.match("출생신고서")
        forms = res if isinstance(res, list) else res.get("forms", [])
        self.assertGreaterEqual(len(forms), 1)
        target_file = forms[0]["filename"]
        file_info = FormArtifactMatcher.get_form_file_info(target_file)
        self.assertIsNotNone(file_info)
        fname, data = file_info
        self.assertTrue(fname.endswith(".pdf") or fname.endswith(".hwp"))
        self.assertGreater(len(data), 100)  # non-empty binary file


class TestJudicialFactChecker(unittest.TestCase):
    """Test Architecture 2: CoVe / Judicial Fact-Check Guardrail"""

    def test_compliant_response(self):
        # Perfectly compliant text based on statutory rules
        text = (
            "출생신고는 출생 후 1개월 이내에 하여야 하며, "
            "정당한 사유 없이 기간 내 신고를 해태한 때에는 5만원 이하의 과태료가 부과됩니다. "
            "신고의무자는 동거하는 친족 등입니다."
        )
        report = JudicialFactChecker.audit_response(text)
        self.assertIsInstance(report, dict)
        self.assertGreaterEqual(report["confidence_score"], 85)
        self.assertIn(report["verdict"], ["passed", "verified"])

    def test_flag_penalty_conflict(self):
        # Factually incorrect penalty (100만원 is false for family registry delay)
        text = "신고 기간을 넘기면 과태료 100만원이 즉시 부과되니 주의하세요."
        report = JudicialFactChecker.audit_response(text)
        # Should flag a warning or conflict in audit findings
        self.assertGreater(len(report["findings"]), 0)
        self.assertTrue(any(f["severity"] in ["conflict", "warning"] for f in report["findings"]))

    def test_flag_deadline_conflict(self):
        # Incorrect deadline (3년 is absurd for birth registration)
        text = "출생신고는 3년 이내에 관할 법원에 신청해야 합니다."
        report = JudicialFactChecker.audit_response(text)
        self.assertGreater(len(report["findings"]), 0)


class TestDualTierLawPreview(unittest.TestCase):
    """Test Architecture 5: Instant Law Preview Tooltip API Data"""

    def setUp(self):
        self.cache = DualTierLawCache()

    def test_law_preview_extraction(self):
        preview = self.cache.get_article_preview("가족관계의 등록 등에 관한 법률", 44)
        self.assertIsNotNone(preview)
        self.assertIn("출생신고의 기재사항", preview.get("title", ""))
        self.assertTrue(len(preview.get("snippet", "")) > 10)

    def test_civil_law_preview_extraction(self):
        preview = self.cache.get_article_preview("민법", 781)
        self.assertIsNotNone(preview)
        self.assertIn("자의 성과 본", preview.get("title", ""))


if __name__ == "__main__":
    unittest.main()
