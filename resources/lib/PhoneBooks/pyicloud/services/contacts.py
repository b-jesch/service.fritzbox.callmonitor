from __future__ import absolute_import

class Contact(object):
    def __init__(self, contact, session, params):
        self.contact = contact
        self.session = session
        self.params = params

    @property
    def id(self):
        return self.contact.contactId;

    @property
    def firstName(self):
        return self.contact.get('firstName')

    @property
    def lastName(self):
        return self.contact.get('lastName')

    @property
    def phones(self):
        return self.contact.get('phones')

    @property
    def photo_url(self):
        photo = self.contact.get('photo')
        return None if photo is None else photo.get('url')

    @property
    def hasPicture(self):
        return self.photo_url is not None

    def download(self):
        if self.photo_url is None: return None
        return self.session.get(
            self.photo_url,
            stream=True
        )


class ContactsService(object):
    """
    The 'Contacts' iCloud service, connects to iCloud and returns contacts.
    """

    def __init__(self, service_root, session, params):
        self.session = session
        self.params = params
        self._service_root = service_root
        self._contacts_endpoint = '%s/co' % self._service_root
        self._contacts_refresh_url = '%s/startup' % self._contacts_endpoint
        self._contacts_changeset_url = '%s/changeset' % self._contacts_endpoint

    def refresh_client(self, from_dt=None, to_dt=None):
        """
        Refreshes the ContactsService endpoint, ensuring that the
        contacts data is up-to-date.
        """
        params_contacts = dict(self.params)
        params_contacts.update({
            'clientVersion': '2.1',
            'locale': 'en_US',
            'order': 'last,first',
        })
        req = self.session.get(
            self._contacts_refresh_url,
            params=params_contacts
        )
        self.response = req.json()
        params_refresh = dict(self.params)
        params_refresh.update({
            'prefToken': req.json()["prefToken"],
            'syncToken': req.json()["syncToken"],
        })
        self.session.post(self._contacts_changeset_url, params=params_refresh)
        req = self.session.get(
            self._contacts_refresh_url,
            params=params_contacts
        )
        self.response = req.json()

    def all(self):
        """
        Retrieves all contacts.
        """
        self.refresh_client()
        return [Contact(c, self.session, self.params) for c in self.response['contacts']]
