from odoo import Command, api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    travel_umroh_role = fields.Selection(
        [
            ("staff", "Staff"),
            ("finance", "Finance"),
            ("manager", "Manager"),
        ],
        string="Travel Umroh Role",
        compute="_compute_travel_umroh_role",
        inverse="_inverse_travel_umroh_role",
        groups="base.group_system",
        help=(
            "Select one Travel Umroh role. Existing users with both Staff and "
            "Finance assigned directly remain unselected until an administrator "
            "chooses the intended role."
        ),
    )

    @api.depends("groups_id")
    def _compute_travel_umroh_role(self):
        staff_group = self.env.ref("travel_umroh.group_travel_staff")
        finance_group = self.env.ref("travel_umroh.group_travel_finance")
        manager_group = self.env.ref("travel_umroh.group_travel_manager")
        for user in self:
            has_staff = staff_group in user.groups_id
            has_finance = finance_group in user.groups_id
            if manager_group in user.groups_id:
                user.travel_umroh_role = "manager"
            elif has_staff and not has_finance:
                user.travel_umroh_role = "staff"
            elif has_finance and not has_staff:
                user.travel_umroh_role = "finance"
            else:
                user.travel_umroh_role = False

    def _inverse_travel_umroh_role(self):
        role_groups = {
            "staff": self.env.ref("travel_umroh.group_travel_staff"),
            "finance": self.env.ref("travel_umroh.group_travel_finance"),
            "manager": self.env.ref("travel_umroh.group_travel_manager"),
        }
        travel_groups = tuple(role_groups.values())
        sales_group = self.env.ref("sales_team.group_sale_salesman")
        contact_manager_group = self.env.ref("base.group_partner_manager")
        for user in self:
            role = user.travel_umroh_role
            commands = [Command.unlink(group.id) for group in travel_groups]
            commands.append(Command.unlink(contact_manager_group.id))
            if role not in ("staff", "manager"):
                commands.append(Command.unlink(sales_group.id))
            if role:
                commands.append(Command.link(role_groups[role].id))
            user.groups_id = commands
