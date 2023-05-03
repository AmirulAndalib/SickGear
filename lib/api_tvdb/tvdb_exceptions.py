# encoding:utf-8
# author:dbr/Ben
# project:tvdb_api
# repository:http://github.com/dbr/tvdb_api
# license:unlicense (http://unlicense.org/)

"""Custom exceptions used or raised by tvdb_api
"""

__author__ = 'dbr/Ben'
__version__ = '1.9'

__all__ = ['TvdbException', 'TvdbError', 'TvdbUserabort', 'TvdbShownotfound',
           'TvdbSeasonnotfound', 'TvdbEpisodenotfound', 'TvdbAttributenotfound', 'TvdbTokenexpired', 'TvdbTokenFailure']

from lib.tvinfo_base.exceptions import *


class TvdbException(BaseTVinfoException):
    """Any exception generated by tvdb_api
    """
    pass


class TvdbError(BaseTVinfoError, TvdbException):
    """An error with thetvdb.com (Cannot connect, for example)
    """
    pass


class TvdbUserabort(BaseTVinfoUserabort, TvdbError):
    """User aborted the interactive selection (via
    the q command, ^c etc)
    """
    pass


class TvdbShownotfound(BaseTVinfoShownotfound, TvdbError):
    """Show cannot be found on thetvdb.com (non-existant show)
    """
    pass


class TvdbSeasonnotfound(BaseTVinfoSeasonnotfound, TvdbError):
    """Season cannot be found on thetvdb.com
    """
    pass


class TvdbEpisodenotfound(BaseTVinfoEpisodenotfound, TvdbError):
    """Episode cannot be found on thetvdb.com
    """
    pass


class TvdbAttributenotfound(BaseTVinfoAttributenotfound, TvdbError):
    """Raised if an episode does not have the requested
    attribute (such as a episode name)
    """
    pass


class TvdbTokenexpired(BaseTVinfoAuthenticationerror, TvdbError):
    """token expired or missing thetvdb.com
    """
    pass


class TvdbTokenFailure(BaseTVinfoAuthenticationerror, TvdbError):
    """getting token failed
    """
    pass
