from odoo import _, models
from odoo.exceptions import AccessError

from .travel_security import is_travel_manager_or_admin


class ResPartner(models.Model):
    _inherit = "res.partner"

    def write(self, values):
        if self.env.user.has_group("travel_umroh.group_travel_staff"):
            protected_internal_partners = self.filtered(
                lambda partner: partner != self.env.user.partner_id
                and partner.user_ids.filtered(lambda user: not user.share)
            )
            if protected_internal_partners:
                raise AccessError(
                    _(
                        "Role Travel tidak dapat mengubah kontak milik user "
                        "internal lain."
                    )
                )

        changed_fields = set(values)
        trusted_signup_metadata_write = (
            self.env.is_admin() and changed_fields == {"signup_type"}
        )
        verified_jamaah = self.env["travel.jamaah"]
        if changed_fields:
            verified_jamaah = self.env["travel.jamaah"].sudo().search(
                [
                    ("partner_id", "in", self.ids),
                    ("document_status", "=", "verified"),
                ]
            )
            if (
                verified_jamaah
                and not trusted_signup_metadata_write
                and not is_travel_manager_or_admin(self.env)
            ):
                raise AccessError(
                    _(
                        "Hanya Manager Travel Umroh yang dapat mengoreksi kontak "
                        "Jamaah terverifikasi."
                    )
                )

        result = super().write(values)
        if verified_jamaah and not trusted_signup_metadata_write:
            field_labels = ", ".join(
                self._fields[field_name].string
                for field_name in sorted(changed_fields)
                if field_name in self._fields
            )
            audit_records = (
                verified_jamaah
                if self.env.is_admin()
                else verified_jamaah.with_user(self.env.user)
            )
            for jamaah in audit_records:
                jamaah.message_post(
                    body=_(
                        "Kontak Jamaah terverifikasi dikoreksi oleh %(user)s. "
                        "Field: %(fields)s.",
                        user=self.env.user.display_name,
                        fields=field_labels,
                    )
                )
        return result
