from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLabel,
    QLineEdit, QCheckBox, QDialogButtonBox)
from .i18n import t
from .security import Protection


class ProtectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t('Protect PDF'))
        self.setMinimumWidth(510)
        layout = QVBoxLayout(self)
        note = QLabel(t('Save a separate PDF with AES-256 encryption. Keep the owner password to unlock editing.'))
        note.setWordWrap(True)
        layout.addWidget(note)
        self.require_open = QCheckBox(t('Require a password to open the document'))
        layout.addWidget(self.require_open)
        form = QFormLayout()
        self.open_password = self.password_field()
        self.open_confirm = self.password_field()
        self.owner_password = self.password_field()
        self.owner_confirm = self.password_field()
        for label, control in [('Opening password', self.open_password),
                               ('Confirm opening password', self.open_confirm),
                               ('Owner password for editing', self.owner_password),
                               ('Confirm owner password', self.owner_confirm)]:
            form.addRow(t(label), control)
        layout.addLayout(form)
        self.allow_print = QCheckBox(t('Allow printing'))
        self.allow_copy = QCheckBox(t('Allow copying text and images'))
        for control in (self.allow_print, self.allow_copy):
            control.setChecked(True)
            layout.addWidget(control)
        self.show_passwords = QCheckBox(t('Show passwords'))
        self.show_passwords.toggled.connect(self.toggle_passwords)
        layout.addWidget(self.show_passwords)
        warning = QLabel(t('Editing, form filling and page changes will be restricted. Some PDF tools can bypass permissions. An opening password protects contents before access; it cannot prevent screenshots or OCR after opening. Passwords cannot be recovered by Paperlight. Use long, unique passwords.'))
        warning.setWordWrap(True)
        layout.addWidget(warning)
        self.validation = QLabel()
        self.validation.setWordWrap(True)
        self.validation.setStyleSheet('color:#b3261e;')
        layout.addWidget(self.validation)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(t('Save protected copy'))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.require_open.toggled.connect(self.update_open_fields)
        self.update_open_fields(False)

    @staticmethod
    def password_field():
        field = QLineEdit()
        field.setEchoMode(QLineEdit.EchoMode.Password)
        return field

    def update_open_fields(self, required):
        self.open_password.setEnabled(required)
        self.open_confirm.setEnabled(required)

    def toggle_passwords(self, visible):
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        for field in (self.open_password, self.open_confirm, self.owner_password, self.owner_confirm):
            field.setEchoMode(mode)

    def protection(self):
        owner = self.owner_password.text()
        opening = self.open_password.text() if self.require_open.isChecked() else ''
        if owner != self.owner_confirm.text():
            raise ValueError('Owner passwords do not match.')
        if self.require_open.isChecked():
            if not opening:
                raise ValueError('Enter an opening password or turn off the opening password requirement.')
            if opening != self.open_confirm.text():
                raise ValueError('Opening passwords do not match.')
        result = Protection(owner, opening, self.allow_print.isChecked(), self.allow_copy.isChecked())
        result.validate()
        return result

    def accept(self):
        try:
            self.protection()
        except ValueError as exc:
            self.validation.setText(t(str(exc)))
            return
        super().accept()
