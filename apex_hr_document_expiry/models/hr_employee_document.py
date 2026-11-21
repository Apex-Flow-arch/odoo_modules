from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

# Days before expiry at which a reminder is sent (0 = on/after expiry)
REMINDER_DAYS = (90, 60, 30, 7, 0)
# Documents are shown as "Expiring Soon" inside this window
EXPIRING_DAYS = 30

DOCUMENT_TYPES = [
    ('iqama', 'Iqama / Residence Permit'),
    ('passport', 'Passport'),
    ('visa', 'Visa'),
    ('national_id', 'National / Emirates ID'),
    ('medical', 'Medical Card / Insurance'),
    ('driving', 'Driving Licence'),
    ('work_permit', 'Work / Labour Permit'),
    ('other', 'Other'),
]


class HrEmployeeDocument(models.Model):
    _name = 'hr.employee.document'
    _description = 'Employee Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expiry_date asc, id'

    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, ondelete='cascade',
        tracking=True, index=True)
    company_id = fields.Many2one(
        related='employee_id.company_id', store=True, readonly=True, index=True)
    document_type = fields.Selection(
        DOCUMENT_TYPES, string='Document Type', required=True, default='iqama', tracking=True)
    document_number = fields.Char(string='Document Number', tracking=True)
    issue_date = fields.Date(string='Issue Date')
    expiry_date = fields.Date(string='Expiry Date', required=True, tracking=True)
    days_left = fields.Integer(string='Days Left', compute='_compute_days_left')
    state = fields.Selection(
        [('valid', 'Valid'),
         ('expiring', 'Expiring Soon'),
         ('expired', 'Expired'),
         ('renewed', 'Renewed')],
        string='Status', compute='_compute_state', store=True, index=True)
    renewed = fields.Boolean(string='Renewed', copy=False)
    renewed_from_id = fields.Many2one(
        'hr.employee.document', string='Renewal Of', copy=False, readonly=True)
    last_reminder_days = fields.Integer(copy=False, default=-1)
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Attachments',
        help="Scanned copy of the document.")
    note = fields.Text(string='Notes')
    active = fields.Boolean(default=True)

    @api.depends('employee_id', 'document_type')
    def _compute_display_name(self):
        labels = dict(DOCUMENT_TYPES)
        for rec in self:
            rec.display_name = '%s - %s' % (
                rec.employee_id.name or '', labels.get(rec.document_type, ''))

    def _compute_days_left(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.days_left = (rec.expiry_date - today).days if rec.expiry_date else 0

    @api.depends('expiry_date', 'renewed')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.renewed:
                rec.state = 'renewed'
            elif not rec.expiry_date:
                rec.state = 'valid'
            else:
                days = (rec.expiry_date - today).days
                if days < 0:
                    rec.state = 'expired'
                elif days <= EXPIRING_DAYS:
                    rec.state = 'expiring'
                else:
                    rec.state = 'valid'

    @api.constrains('issue_date', 'expiry_date')
    def _check_dates(self):
        for rec in self:
            if rec.issue_date and rec.expiry_date and rec.expiry_date < rec.issue_date:
                raise ValidationError(_("The expiry date cannot be before the issue date."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # A document created through "Renew" closes the old one
        records.renewed_from_id.write({'renewed': True})
        return records

    def write(self, vals):
        if 'expiry_date' in vals:
            vals['last_reminder_days'] = -1  # restart reminders for the new date
        return super().write(vals)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_renew(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Renew Document'),
            'res_model': self._name,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_employee_id': self.employee_id.id,
                'default_document_type': self.document_type,
                'default_document_number': self.document_number,
                'default_renewed_from_id': self.id,
            },
        }

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_check_expiry(self):
        today = fields.Date.context_today(self)
        docs = self.search([('renewed', '=', False), ('expiry_date', '!=', False)])
        docs._compute_state()  # statuses change as time passes
        for doc in docs:
            days_left = (doc.expiry_date - today).days
            due = [d for d in REMINDER_DAYS if days_left <= d]
            if not due:
                continue
            threshold = min(due)
            if doc.last_reminder_days == -1 or doc.last_reminder_days > threshold:
                doc._send_reminder(days_left)
                doc.last_reminder_days = threshold

    def _get_hr_managers(self):
        group = self.env.ref('hr.group_hr_manager')
        users = group.user_ids if 'user_ids' in group._fields else group.users
        return users.filtered(lambda u: u.active and not u.share)

    def _send_reminder(self, days_left):
        self.ensure_one()
        labels = dict(DOCUMENT_TYPES)
        doc_label = labels.get(self.document_type, '')
        if days_left < 0:
            title = _("%(doc)s of %(emp)s expired %(days)s days ago",
                      doc=doc_label, emp=self.employee_id.name, days=abs(days_left))
        elif days_left == 0:
            title = _("%(doc)s of %(emp)s expires today",
                      doc=doc_label, emp=self.employee_id.name)
        else:
            title = _("%(doc)s of %(emp)s expires in %(days)s days",
                      doc=doc_label, emp=self.employee_id.name, days=days_left)
        managers = self._get_hr_managers()
        for user in managers:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=fields.Date.context_today(self),
                user_id=user.id,
                summary=title,
            )
        self.message_post(
            subject=title,
            body=_("%(title)s. Expiry date: %(date)s.", title=title, date=self.expiry_date),
            partner_ids=managers.partner_id.ids,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
        )
