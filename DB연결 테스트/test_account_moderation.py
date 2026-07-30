import unittest
from datetime import datetime

from pydantic import ValidationError

from account_moderation import (
    DELETED_NICKNAME,
    build_soft_delete_fields,
    serialize_report,
)
from models import (
    AccountWithdrawalSchema,
    CommunityReportSchema,
    WarningCreateSchema,
    WarningResolutionSchema,
)


class AccountModerationTests(unittest.TestCase):
    def test_soft_delete_fields_remove_personal_account_values(self):
        now = datetime(2026, 7, 23, 12, 0, 0)

        fields = build_soft_delete_fields(
            "507f1f77bcf86cd799439011",
            reason="requested",
            deleted_by="self",
            now=now,
        )

        self.assertEqual(fields["account_status"], "deleted")
        self.assertEqual(fields["nickname"], DELETED_NICKNAME)
        self.assertTrue(fields["account_id"].startswith("deleted_"))
        self.assertIsNone(fields["email"])
        self.assertIsNone(fields["phone"])
        self.assertIsNone(fields["password"])
        self.assertIsNone(fields["provider_id"])
        self.assertIsNone(fields["social_info"])
        self.assertEqual(fields["deleted_at"], now)

    def test_report_serializer_does_not_expose_internal_fields(self):
        serialized = serialize_report(
            {
                "_id": "report-id",
                "reporter_account_id": "reporter",
                "target_type": "post",
                "target_id": "post-id",
                "reason": "spam",
                "status": "pending",
                "internal_note": "must not leak",
            }
        )

        self.assertNotIn("internal_note", serialized)
        self.assertEqual(serialized["status"], "pending")

    def test_report_schema_requires_supported_target(self):
        with self.assertRaises(ValidationError):
            CommunityReportSchema(
                target_type="story",
                target_id="id",
                reason="invalid target",
            )

    def test_warning_and_withdrawal_schemas(self):
        warning = WarningCreateSchema(reason="반복적인 부적절한 댓글")
        resolution = WarningResolutionSchema(status="resolved")
        withdrawal = AccountWithdrawalSchema(password="password", reason="requested")

        self.assertEqual(warning.severity, "notice")
        self.assertEqual(resolution.status, "resolved")
        self.assertEqual(withdrawal.reason, "requested")


if __name__ == "__main__":
    unittest.main()
