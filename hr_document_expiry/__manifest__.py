{
    'name': 'Employee Document Expiry Tracker',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Employees',
    'summary': 'Track Iqama, visa, passport and other employee document expiry dates with automatic alerts',
    'description': """
Track employee documents (Iqama, passport, visa, medical card, driving licence ...),
get automatic reminders at 90, 60, 30 and 7 days before expiry, and keep renewal history.
    """,
    'author': 'Nayana Bandihal',
    'depends': ['hr', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/hr_employee_document_views.xml',
        'views/hr_employee_views.xml',
        'views/menu.xml',
        'data/ir_cron.xml',
    ],
    'demo': [
        'data/demo.xml',
    ],
    'license': 'OPL-1',
    'price': 49.0,
    'currency': 'USD',
    'installable': True,
    'application': False,
}
