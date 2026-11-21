from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    document_ids = fields.One2many('hr.employee.document', 'employee_id', string='Documents')
    document_count = fields.Integer(compute='_compute_document_count', string='Documents')

    def _compute_document_count(self):
        data = self.env['hr.employee.document']._read_group(
            [('employee_id', 'in', self.ids), ('renewed', '=', False)],
            ['employee_id'], ['__count'])
        counts = {employee.id: count for employee, count in data}
        for emp in self:
            emp.document_count = counts.get(emp.id, 0)

    def action_open_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'hr.employee.document',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
