#
# This file is part of SickGear.
#
# SickGear is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickGear is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickGear.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import functools
import locale
import re
import sys

import sickgear
from dateutil import tz

from six import integer_types, string_types

# noinspection PyUnreachableCode
if False:
    from typing import Optional, Union

date_presets = ('%Y-%m-%d',
                '%a, %Y-%m-%d',
                '%A, %Y-%m-%d',
                '%y-%m-%d',
                '%a, %y-%m-%d',
                '%A, %y-%m-%d',
                '%m/%d/%Y',
                '%a, %m/%d/%Y',
                '%A, %m/%d/%Y',
                '%m/%d/%y',
                '%a, %m/%d/%y',
                '%A, %m/%d/%y',
                '%m-%d-%Y',
                '%a, %m-%d-%Y',
                '%A, %m-%d-%Y',
                '%m-%d-%y',
                '%a, %m-%d-%y',
                '%A, %m-%d-%y',
                '%m.%d.%Y',
                '%a, %m.%d.%Y',
                '%A, %m.%d.%Y',
                '%m.%d.%y',
                '%a, %m.%d.%y',
                '%A, %m.%d.%y',
                '%d-%m-%Y',
                '%a, %d-%m-%Y',
                '%A, %d-%m-%Y',
                '%d-%m-%y',
                '%a, %d-%m-%y',
                '%A, %d-%m-%y',
                '%d/%m/%Y',
                '%a, %d/%m/%Y',
                '%A, %d/%m/%Y',
                '%d/%m/%y',
                '%a, %d/%m/%y',
                '%A, %d/%m/%y',
                '%d.%m.%Y',
                '%a, %d.%m.%Y',
                '%A, %d.%m.%Y',
                '%d.%m.%y',
                '%a, %d.%m.%y',
                '%A, %d.%m.%y',
                '%d. %b %Y',
                '%a, %d. %b %Y',
                '%A, %d. %b %Y',
                '%d. %b %y',
                '%a, %d. %b %y',
                '%A, %d. %b %y',
                '%d. %B %Y',
                '%a, %d. %B %Y',
                '%A, %d. %B %Y',
                '%d. %B %y',
                '%a, %d. %B %y',
                '%A, %d. %B %y',
                '%b %d, %Y',
                '%a, %b %d, %Y',
                '%A, %b %d, %Y',
                '%B %d, %Y',
                '%a, %B %d, %Y',
                '%A, %B %d, %Y')

time_presets = ('%I:%M:%S %p',
                '%I:%M:%S %P',
                '%H:%M:%S')

is_win = 'win32' == sys.platform


# helper decorator class
# noinspection PyPep8Naming
class static_or_instance(object):
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):
        return functools.partial(self.func, instance)


# subclass datetime.datetime to add function to display custom date and time formats
class SGDatetime(datetime.datetime):
    has_locale = True

    @static_or_instance
    def is_locale_eng(self):
        today = SGDatetime.sbfdate(SGDatetime.now(), '%A').lower()
        return ('day' == today[-3::] and today[0:-3:] in ['sun', 'mon', 'tues', 'wednes', 'thurs', 'fri', 'satur']
                and SGDatetime.sbfdate(SGDatetime.now(), '%B').lower() in [
                    'january', 'february', 'march', 'april', 'may', 'june',
                    'july', 'august', 'september', 'october', 'november', 'december'])

    @static_or_instance
    def convert_to_setting(self, dt=None, force_local=False):
        # type: (Optional[datetime.datetime, SGDatetime], bool) -> Union[SGDatetime, datetime.datetime]
        obj = (dt, self)[self is not None]  # type: datetime.datetime
        try:
            if force_local or 'local' == sickgear.TIMEZONE_DISPLAY:
                from sickgear.network_timezones import SG_TIMEZONE
                return obj.astimezone(SG_TIMEZONE)
        except (BaseException, Exception):
            pass

        return obj

    @static_or_instance
    def setlocale(self, setlocale=True, use_has_locale=None, locale_str=''):
        if setlocale:
            try:
                if None is use_has_locale or use_has_locale:
                    locale.setlocale(locale.LC_TIME, locale_str)
            except locale.Error:
                if None is not use_has_locale:
                    SGDatetime.has_locale = False
                pass

    # display Time in SickGear Format
    @static_or_instance
    def sbftime(self, dt=None, show_seconds=False, t_preset=None, setlocale=True, markup=False):

        SGDatetime.setlocale(setlocale=setlocale, use_has_locale=SGDatetime.has_locale, locale_str='us_US')

        strt = ''

        obj = (dt, self)[self is not None]  # type: datetime.datetime
        if None is not obj:
            tmpl = (((sickgear.TIME_PRESET, sickgear.TIME_PRESET_W_SECONDS)[show_seconds]),
                    t_preset)[None is not t_preset]
            tmpl = (tmpl.replace(':%S', ''), tmpl)[show_seconds]

            strt = SGDatetime.sbstrftime(obj, tmpl.replace('%P', '%p'))

            if sickgear.TRIM_ZERO:
                strt = re.sub(r'^0(\d:\d\d)', r'\1', strt)

            if re.search(r'(?im)%p$', tmpl):
                if '%p' in tmpl:
                    strt = strt.upper()
                elif '%P' in tmpl:
                    strt = strt.lower()

                if sickgear.TRIM_ZERO:
                    strt = re.sub(r'(?im)^(\d+)(?::00)?(\s?[ap]m)', r'\1\2', strt)

            if markup:
                match = re.search(r'(?im)(\d{1,2})(?:(.)(\d\d)(?:(.)(\d\d))?)?(?:\s?([ap]m))?$', strt)
                if match:
                    strt = ('%s%s%s%s%s%s' % (
                        ('<span class="time-hr">%s</span>' % match.group(1), '')[None is match.group(1)],
                        ('<span class="time-hr-min">%s</span>' % match.group(2), '')[None is match.group(2)],
                        ('<span class="time-min">%s</span>' % match.group(3), '')[None is match.group(3)],
                        ('<span class="time-min-sec">%s</span>' % match.group(4), '')[None is match.group(4)],
                        ('<span class="time-sec">%s</span>' % match.group(5), '')[None is match.group(5)],
                        ('<span class="time-am-pm">%s</span>' % match.group(6), '')[None is match.group(6)]))

        SGDatetime.setlocale(setlocale=setlocale, use_has_locale=SGDatetime.has_locale)
        return strt

    # display Date in SickGear Format
    @static_or_instance
    def sbfdate(self, dt=None, d_preset=None, setlocale=True):

        SGDatetime.setlocale(setlocale=setlocale)

        strd = ''
        try:
            obj = (dt, self)[self is not None]  # type: datetime.datetime
            if None is not obj:
                strd = SGDatetime.sbstrftime(obj, (sickgear.DATE_PRESET, d_preset)[None is not d_preset])

        finally:
            SGDatetime.setlocale(setlocale=setlocale)
            return strd

    # display Datetime in SickGear Format
    @static_or_instance
    def sbfdatetime(self, dt=None, show_seconds=False, d_preset=None, t_preset=None, markup=False):

        SGDatetime.setlocale()

        strd = ''
        obj = (dt, self)[self is not None]  # type: datetime.datetime
        try:
            if None is not obj:
                strd = '%s, %s' % (
                    SGDatetime.sbstrftime(obj, (sickgear.DATE_PRESET, d_preset)[None is not d_preset]),
                    SGDatetime.sbftime(dt, show_seconds, t_preset, False, markup))

        finally:
            SGDatetime.setlocale(use_has_locale=SGDatetime.has_locale)
            return strd

    @staticmethod
    def sbstrftime(obj, str_format):
        try:
            result = obj.strftime(str_format),
        except ValueError:
            result = obj.replace(tzinfo=None).strftime(str_format)
        return result if isinstance(result, string_types) else \
            isinstance(result, tuple) and 1 == len(result) and '%s' % result[0] or ''

    @static_or_instance
    def to_file_timestamp(self, dt=None):
        # type: (Optional[SGDatetime, datetime.datetime]) -> Union[float, integer_types]
        """
        convert datetime to filetime
        special handling for windows filetime issues
        for pre Windows 7 this can result in an exception for pre-1970 dates
        """
        obj = (dt, self)[self is not None]  # type: datetime.datetime
        if is_win:
            from .network_timezones import EPOCH_START_WIN
            return (obj.replace(tzinfo=tz.tzwinlocal()) - EPOCH_START_WIN).total_seconds()
        return SGDatetime.timestamp_far(obj)

    @staticmethod
    def from_timestamp(ts, local_time=True, tz_aware=False, tzinfo=None):
        # type: (Union[float, integer_types], bool, bool, datetime.tzinfo) -> datetime.datetime
        """
        convert timestamp to datetime.datetime obj
        :param ts: timestamp integer, float
        :param local_time: return as local timezone (SG_TIMEZONE)
        :param tz_aware: return tz aware datetime
        :param tzinfo: tzinfo to be used
        """
        from .network_timezones import EPOCH_START, SG_TIMEZONE
        result = EPOCH_START + datetime.timedelta(seconds=ts)
        if local_time and SG_TIMEZONE:
            result = result.astimezone(SG_TIMEZONE)
        if isinstance(tzinfo, datetime.tzinfo):
            result = result.astimezone(tzinfo)
        if not tz_aware:
            return result.replace(tzinfo=None)
        return result

    @static_or_instance
    def timestamp_far(self,
                      dt=None,  # type: Optional[SGDatetime, datetime.datetime]
                      default=None  # type: Optional[float, integer_types]
                      ):
        # type: (...) -> Union[float, integer_types, None]
        """
        Use `timestamp_far` for a timezone aware UTC timestamp in far future or far past
        """
        obj = (dt, self)[self is not None]  # type: datetime.datetime
        if isinstance(obj, datetime.datetime) and not isinstance(getattr(obj, 'tzinfo', None), datetime.tzinfo):
            from sickgear.network_timezones import SG_TIMEZONE
            obj = obj.replace(tzinfo=SG_TIMEZONE)
        from .network_timezones import EPOCH_START
        timestamp = default
        try:
            timestamp = (obj - EPOCH_START).total_seconds()
        finally:
            return (default, timestamp)[isinstance(timestamp, (float, integer_types))]


# noinspection PyUnreachableCode
if False:
    # just to trick pycharm in correct type detection
    # noinspection PyUnusedLocal
    def timestamp_near(d_t):
        # type: (datetime.datetime) -> float
        pass


# py3 native timestamp uses milliseconds
# noinspection PyRedeclaration
timestamp_near = datetime.datetime.timestamp
