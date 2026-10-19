"""PDF password protection. Permission flags depend on reader enforcement."""
from dataclasses import dataclass, field
import pymupdf as fitz


EDIT_PERMISSIONS = (fitz.PDF_PERM_MODIFY | fitz.PDF_PERM_ANNOTATE |
                    fitz.PDF_PERM_FORM | fitz.PDF_PERM_ASSEMBLE)


@dataclass(frozen=True)
class Protection:
    owner_password: str = field(repr=False)
    open_password: str = field(default='', repr=False)
    allow_print: bool = True
    allow_copy: bool = True

    def validate(self):
        if not self.owner_password:
            raise ValueError('Enter an owner password to control editing.')
        for password in (self.owner_password, self.open_password):
            if len(password.encode('utf-8')) > 40 or '\x00' in password:
                raise ValueError('Passwords must contain at most 40 UTF-8 bytes and no null characters.')
        if self.open_password == self.owner_password:
            raise ValueError('Use different opening and owner passwords.')

    def save_options(self):
        self.validate()
        permissions = fitz.PDF_PERM_ACCESSIBILITY
        if self.allow_print:
            permissions |= fitz.PDF_PERM_PRINT | fitz.PDF_PERM_PRINT_HQ
        if self.allow_copy:
            permissions |= fitz.PDF_PERM_COPY
        return dict(encryption=fitz.PDF_ENCRYPT_AES_256,
                    owner_pw=self.owner_password, user_pw=self.open_password,
                    permissions=permissions)


def access(doc, password=''):
    """Return original security before normalizing the session's working file."""
    # MuPDF's needs_pass probes an empty password. Read it BEFORE authentication:
    # probing it afterwards can replace the active AES key and corrupt reads.
    needs_password = doc.needs_pass
    authentication = doc.authenticate(password)
    if needs_password and not authentication:
        raise ValueError('This PDF needs the correct password.')
    encrypted = bool(doc.metadata and doc.metadata.get('encryption'))
    owner = bool(authentication & 4)
    readonly = encrypted and not owner and (doc.permissions & EDIT_PERMISSIONS != EDIT_PERMISSIONS)
    copy_allowed = not encrypted or owner or bool(doc.permissions & fitz.PDF_PERM_COPY)
    return encrypted, readonly, copy_allowed
