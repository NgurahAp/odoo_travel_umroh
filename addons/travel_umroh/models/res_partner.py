from odoo import _, models
from odoo.exceptions import AccessError


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
        verified_jamaah = self.env["travel.jamaah"]
        if changed_fields:
            verified_jamaah = self.env["travel.jamaah"].sudo().search(
                [
                    ("partner_id", "in", self.ids),
                    ("document_status", "=", "verified"),
                ]
            )
            if verified_jamaah and not self.env.user.has_group(
                "travel_umroh.group_travel_manager"
            ):
                raise AccessError(
                    _(
                        "Hanya Manager Travel Umroh yang dapat mengoreksi kontak "
                        "Jamaah terverifikasi."
                    )
                )

        result = super().write(values)
        if verified_jamaah:
            field_labels = ", ".join(
                self._fields[field_name].string
                for field_name in sorted(changed_fields)
                if field_name in self._fields
            )
            for jamaah in verified_jamaah.with_user(self.env.user):
                jamaah.message_post(
                    body=_(
                        "Kontak Jamaah terverifikasi dikoreksi oleh %(user)s. "
                        "Field: %(fields)s.",
                        user=self.env.user.display_name,
                        fields=field_labels,
                    )
                )
        return result
