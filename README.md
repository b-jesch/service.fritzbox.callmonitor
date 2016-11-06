<h1>Fritz!Box Call Monitor</h1>
This service addon displays incoming and outgoing calls from the popular german ADSL Router called "Fritz!Box", connecting to port 1012 of the box. This addon also features a number to name and picture resolving against the internal phonebook and external phonebook (Google Contacts) of the Fritz!Box and Apple iCloud. Furthermore, reverse search phone numbers via the API of the company 'klicktel' is implemented. Certain telephone numbers can be excluded from monitoring.

You must enable your Listenport 1012 on the box. To enable or disable this, enter the following code into your telephone:

    #96*5* Callmonitor-Support enabled.
    #96*4* Callmonitor-Support disabled.

Some notes

* If you want to exclude numbers from monitoring enter these numbers (only numbers, no spaces or special chars within are allowed) separated by comma and/or space in the provided field. Leave this field blank if you don't want to exclude any numbers.
  Example: 08154711, 08154712
   
* A full qualified authentication against the box (user, password) is strongly recommended.