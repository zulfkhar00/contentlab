"""Unit tests for hypothesis domain rules."""
import pytest

from app.domain.errors import DomainError
from app.domain.hypothesis import assert_can_approve, assert_can_patch, assert_can_reject

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))


def test_approve_from_generated():
    assert_can_approve("generated")  # no exception


def test_approve_from_draft():
    assert_can_approve("draft")  # no exception


def test_approve_from_approved_rejected():
    for s in ("approved", "rejected", "testing", "tested"):
        with pytest.raises(DomainError):
            assert_can_approve(s)


def test_reject_from_approvable():
    for s in ("generated", "draft", "approved"):
        assert_can_reject(s)  # no exception


def test_reject_from_terminal():
    for s in ("testing", "tested", "rejected"):
        with pytest.raises(DomainError):
            assert_can_reject(s)


def test_patch_blocked_after_testing():
    for s in ("testing", "tested"):
        with pytest.raises(DomainError):
            assert_can_patch(s)


def test_patch_allowed_before_testing():
    for s in ("generated", "draft", "approved", "rejected"):
        assert_can_patch(s)  # no exception
