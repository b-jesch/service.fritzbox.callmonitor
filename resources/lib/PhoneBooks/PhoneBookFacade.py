#!/usr/bin/env python
# -*- coding: utf-8 -*-

import inspect
import os
import re

from PhoneBookBase import PhoneBookBase


def _find_phone_book_classes():
    directory = os.path.dirname(os.path.abspath(__file__))
    for module in os.listdir(directory):
        if module in ('__init__.py', 'PhoneBookFacade.py', 'PhoneBookBase.py') \
                or module[-3:] != '.py':
            continue
        imported_module = __import__('resources.lib.PhoneBooks.'+module[:-3], locals(), globals(), ['object'])
        return _find_phone_book_classes_in_module(imported_module)


def _find_phone_book_classes_in_module(module):
    for name in dir(module):
        symbol = getattr(module, name)
        try:
            if symbol != PhoneBookBase \
                    and issubclass(symbol, PhoneBookBase) \
                    and not inspect.isabstract(symbol):
                yield symbol
        except TypeError:
            pass


class PhoneBookFacade(PhoneBookBase):
    def __init__(self, imagepath):
        PhoneBookBase.__init__(self, imagepath)
        self._phoneBooks = []
        for phone_book in _find_phone_book_classes():
            self._phoneBooks.append(phone_book(imagepath))

    def set_settings(self, settings):
        for phone_book in self._phoneBooks:
            phone_book.set_settings(settings)

    def get_setting_keys(self):
        merged_settings = {}
        for phone_book in self._phoneBooks:
            merged_settings.update(phone_book.get_setting_keys())
        return merged_settings

    def imagecount(self):
        count = 0
        for phone_book in self._phoneBooks:
            count += phone_book.imagecount()
        return count

    def compareNumbers(self, a, b, ccode='0049'):

        a = str(re.sub('[^0-9\+\*]|((?<!\A)\+)', '', a))
        b = str(re.sub('[^0-9\+\*]|((?<!\A)\+)', '', b))

        if a.startswith(ccode): a = '0' + a[len(ccode):]
        if a.startswith('+'): a = '0' + a[3:]

        if b.startswith(ccode): b = '0' + b[len(ccode):]
        if b.startswith('+'): b = '0' + b[3:]

        # a = a[-len(b):]
        # b = b[-len(a):]

        return (a == b)

    def getPhonebook(self):
        phone_books = {}
        for phone_book in self._phoneBooks:
            phone_books.update(phone_book.getPhonebook())
        return phone_books
