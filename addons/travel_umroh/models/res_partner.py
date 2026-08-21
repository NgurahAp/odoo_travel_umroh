from odoo import _, models
from odoo.exceptions import AccessError


class ResPartner(models.Model):
    _inherit = "res.partner"

    _travel_jamaah_contact_fields = {
        "name",
        "phone",
        "email",
        "street",
        "street2",
        "city",
        "state_id",
        "zip",
        "country_id",
    }

    def write(self, values):
        changed_fields = self._travel_jamaah_contact_fields.intersection(values)
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
