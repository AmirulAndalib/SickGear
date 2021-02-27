# encoding:utf-8

"""Custom exceptions used or raised by tvmaze_api
"""

__author__ = 'Prinz23'
__version__ = '1.0'

__all__ = ['TvMazeException', 'TvMazeError', 'TvMazeUserabort', 'TvMazeShownotfound',
           'TvMazeSeasonnotfound', 'TvMazeEpisodenotfound', 'TvMazeAttributenotfound', 'TvMazeTokenexpired']

from lib.tvinfo_base.exceptions import *


class TvMazeException(BaseTVinfoException):
    """Any exception generated by tvdb_api
    """
    pass


class TvMazeError(BaseTVinfoError, TvMazeException):
    """An error with thetvdb.com (Cannot connect, for example)
    """
    pass


class TvMazeUserabort(BaseTVinfoUserabort, TvMazeError):
    """User aborted the interactive selection (via
    the q command, ^c etc)
    """
    pass


class TvMazeShownotfound(BaseTVinfoShownotfound, TvMazeError):
    """Show cannot be found on thetvdb.com (non-existant show)
    """
    pass


class TvMazeSeasonnotfound(BaseTVinfoSeasonnotfound, TvMazeError):
    """Season cannot be found on thetvdb.com
    """
    pass


class TvMazeEpisodenotfound(BaseTVinfoEpisodenotfound, TvMazeError):
    """Episode cannot be found on thetvdb.com
    """
    pass


class TvMazeAttributenotfound(BaseTVinfoAttributenotfound, TvMazeError):
    """Raised if an episode does not have the requested
    attribute (such as a episode name)
    """
    pass


class TvMazeTokenexpired(BaseTVinfoAuthenticationerror, TvMazeError):
    """token expired or missing thetvdb.com
    """
    pass
