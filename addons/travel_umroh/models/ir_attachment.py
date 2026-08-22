from contextlib import contextmanager
from contextvars import ContextVar

from odoo import _, api, models
from odoo.exceptions import AccessError

from .travel_security import is_travel_manager_or_admin


_travel_attachment_audit_suppressed = ContextVar(
    "travel_umroh_attachment_audit_suppressed", default=False
)


@contextmanager
def suppress_travel_attachment_audit():
    token = _travel_attachment_audit_suppressed.set(True)
    try:
        yield
    finally:
        _travel_attachment_audit_suppressed.reset(token)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    _travel_jamaah_document_fields = {"ktp_file", "passport_file"}

    @api.model
    def _travel_document_jamaah(self, values, attachment=None):
        res_model = values.get(
            "res_model", attachment.res_model if attachment else False
        )
        res_id = values.get("res_id", attachment.res_id if attachment else 0)
        res_field = values.get(
            "res_field", attachment.res_field if attachment else False
        )
        if (
            res_model != "travel.jamaah"
            or res_field not in self._travel_jamaah_document_fields
            or not res_id
        ):
            return self.env["travel.jamaah"]
        return self.env["travel.jamaah"].sudo().browse(res_id).exists()

    @api.model
    def _travel_check_verified_document_mutation(self, values, attachment=None):
        if is_travel_manager_or_admin(self.env):
            return
        jamaah = self._travel_document_jamaah(values, attachment=attachment)
        if jamaah.filtered(lambda record: record.document_status == "verified"):
            raise AccessError(
                _(
                    "Hanya Manager Travel Umroh yang dapat mengubah lampiran "
                    "dokumen Jamaah terverifikasi."
                )
            )

    @api.model
    def _travel_post_verified_document_audit(
        self, jamaah, res_fields, operation
    ):
        if _travel_attachment_audit_suppressed.get() or not jamaah:
            return
        field_labels = {
            "ktp_file": _("File KTP"),
            "passport_file": _("File Paspor"),
        }
        document_labels = ", ".join(
            field_labels[field_name]
            for field_name in sorted(
                field_name
                for field_name in res_fields
                if field_name in field_labels
            )
        )
        audit_records = (
            jamaah
            if self.env.is_admin()
            else jamaah.with_user(self.env.user)
        )
        for record in audit_records:
            record.message_post(
                body=_(
                    "Lampiran dokumen Jamaah terverifikasi dikoreksi oleh "
                    "%(user)s. Dokumen: %(documents)s. Operasi: %(operation)s.",
                    user=self.env.user.display_name,
                    documents=document_labels,
                    operation=operation,
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            self._travel_check_verified_document_mutation(values)
        attachments = super().create(vals_list)
        for attachment, values in zip(attachments, vals_list):
            jamaah = self._travel_document_jamaah(
                values, attachment=attachment
            ).filtered(lambda record: record.document_status == "verified")
            self._travel_post_verified_document_audit(
                jamaah,
                {values.get("res_field", attachment.res_field)},
                _("ditambahkan"),
            )
        return attachments

    def write(self, values):
        audit_jamaah = self.env["travel.jamaah"].sudo()
        audit_fields = set()
        for attachment in self:
            self._travel_check_verified_document_mutation({}, attachment)
            self._travel_check_verified_document_mutation(values, attachment)
            source = self._travel_document_jamaah(
                {}, attachment=attachment
            ).filtered(lambda record: record.document_status == "verified")
            target = self._travel_document_jamaah(
                values, attachment=attachment
            ).filtered(lambda record: record.document_status == "verified")
            audit_jamaah |= source | target
            audit_fields.update(
                {attachment.res_field, values.get("res_field")}
            )
        write_records = self.sudo() if self.env.is_admin() else self
        result = super(IrAttachment, write_records).write(values)
        operation = (
            _("dipindahkan")
            if {"res_model", "res_id", "res_field"}.intersection(values)
            else _("diperbarui")
        )
        self._travel_post_verified_document_audit(
            audit_jamaah, audit_fields, operation
        )
        return result

    def unlink(self):
        audit_jamaah = self.env["travel.jamaah"].sudo()
        audit_fields = set()
        for attachment in self:
            self._travel_check_verified_document_mutation({}, attachment)
            audit_jamaah |= self._travel_document_jamaah(
                {}, attachment=attachment
            ).filtered(lambda record: record.document_status == "verified")
            audit_fields.add(attachment.res_field)
        unlink_records = self.sudo() if self.env.is_admin() else self
        result = super(IrAttachment, unlink_records).unlink()
        self._travel_post_verified_document_audit(
            audit_jamaah, audit_fields, _("dihapus")
        )
        return result
