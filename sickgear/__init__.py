﻿#
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
from collections import OrderedDict
from threading import Lock

import copy
import datetime
import io
import os
import re
import signal
import socket
import time
import webbrowser

# apparently py2exe won't build these unless they're imported somewhere
import os.path
import sys
import threading
import uuid
import zlib

from . import classes, db, helpers, image_cache, indexermapper, logger, metadata, naming, people_queue, providers, \
    scene_exceptions, scene_numbering, scheduler, search_backlog, search_propers, search_queue, search_recent, \
    show_queue, show_updater, subtitles, trakt_helpers, version_checker, watchedstate_queue
from . import auto_media_process, properFinder  # must come after the above imports
from .common import SD, SKIPPED, USER_AGENT
from .config import check_section, check_setting_int, check_setting_str, ConfigMigrator, minimax
from .databases import cache_db, failed_db, mainDB
from .event_queue import ConfigEvents
from .indexers.indexer_api import TVInfoAPI
from .indexers.indexer_config import TVINFO_IMDB, TVINFO_TVDB, TmdbIndexer
from .providers.generic import GenericProvider
from .providers.newznab import NewznabConstants
from .tv import TVidProdid
from .watchedstate import EmbyWatchedStateUpdater, PlexWatchedStateUpdater
from .webserve import History

from adba.aniDBerrors import AniDBError
# noinspection PyProtectedMember
from browser_ua import get_ua
from configobj import ConfigObj
from api_trakt import TraktAPI

from _23 import b64encodestring, decode_bytes, scandir
from sg_helpers import remove_file_perm
from six import iteritems, string_types
import sg_helpers

# noinspection PyUnreachableCode
if False:
    from typing import AnyStr, Dict, List, Optional
    from adba import Connection
    from .event_queue import Events
    from .tv import TVShow
    from lib.api_trakt.trakt import TraktAccount

PID = None
ENV = {}

# noinspection PyTypeChecker
CFG = None  # type: ConfigObj
CONFIG_FILE = ''
CONFIG_VERSION = None
CONFIG_OLD = None
CONFIG_LOADED = False

# Default encryption version (0 for None)
ENCRYPTION_VERSION = 0

PROG_DIR = '.'
MY_FULLNAME = None
MY_ARGS = []
SYS_ENCODING = ''
DATA_DIR = ''

# system events
# noinspection PyTypeChecker
events = None  # type: Events
config_events = None  # type: ConfigEvents

show_queue_scheduler = None  # type: Optional[scheduler.Scheduler]
search_queue_scheduler = None  # type: Optional[scheduler.Scheduler]
people_queue_scheduler = None  # type: Optional[scheduler.Scheduler]
watched_state_queue_scheduler = None  # type: Optional[scheduler.Scheduler]
update_software_scheduler = None  # type: Optional[scheduler.Scheduler]
update_packages_scheduler = None  # type: Optional[scheduler.Scheduler]
update_show_scheduler = None  # type: Optional[scheduler.Scheduler]
update_release_mappings_scheduler = None  # type: Optional[scheduler.Scheduler]
search_recent_scheduler = None  # type: Optional[scheduler.Scheduler]
search_backlog_scheduler = None  # type: Optional[search_backlog.BacklogSearchScheduler]
search_propers_scheduler = None  # type: Optional[scheduler.Scheduler]
search_subtitles_scheduler = None  # type: Optional[scheduler.Scheduler]
emby_watched_state_scheduler = None  # type: Optional[scheduler.Scheduler]
plex_watched_state_scheduler = None  # type: Optional[scheduler.Scheduler]
process_media_scheduler = None  # type: Optional[scheduler.Scheduler]
# noinspection PyTypeChecker
background_mapping_task = None  # type: threading.Thread
# deprecated
# trakt_checker_scheduler = None

provider_ping_thread_pool = {}

showList = []  # type: List[TVShow]
showDict = {}  # type: Dict[int, TVShow]
switched_shows = {}  # type: Dict[AnyStr, AnyStr]
UPDATE_SHOWS_ON_START = False
SHOW_UPDATE_HOUR = 3

# non ui settings
REMOVE_FILENAME_CHARS = None
IMPORT_DEFAULT_CHECKED_SHOWS = 0
# /non ui settings

provider_list = []
newznab_providers = []
torrent_rss_providers = []
metadata_provider_dict = {}

MODULE_UPDATE_STRING = None
NEWEST_VERSION_STRING = None

MIN_UPDATE_INTERVAL = 1
DEFAULT_UPDATE_INTERVAL = 12
UPDATE_NOTIFY = False
UPDATE_AUTO = False
UPDATE_INTERVAL = DEFAULT_UPDATE_INTERVAL
NOTIFY_ON_UPDATE = False

MIN_UPDATE_PACKAGES_INTERVAL = 1
MAX_UPDATE_PACKAGES_INTERVAL = 9999
DEFAULT_UPDATE_PACKAGES_INTERVAL = 24
UPDATE_PACKAGES_NOTIFY = False
UPDATE_PACKAGES_AUTO = False
UPDATE_PACKAGES_MENU = False
UPDATE_PACKAGES_INTERVAL = DEFAULT_UPDATE_PACKAGES_INTERVAL

CUR_COMMIT_HASH = None
EXT_UPDATES = False
BRANCH = ''
GIT_REMOTE = ''
CUR_COMMIT_BRANCH = ''

INIT_LOCK = Lock()
started = False

ACTUAL_LOG_DIR = None
LOG_DIR = None
FILE_LOGGING_PRESET = 'DEBUG'

SOCKET_TIMEOUT = None

WEB_PORT = None
WEB_LOG = 0
WEB_ROOT = None
WEB_USERNAME = None
WEB_PASSWORD = None
WEB_HOST = None
WEB_IPV6 = 0
WEB_IPV64 = 0

HANDLE_REVERSE_PROXY = False
SEND_SECURITY_HEADERS = True
ALLOWED_HOSTS = None
ALLOW_ANYIP = True
PROXY_SETTING = None
PROXY_INDEXERS = True

CPU_PRESET = 'DISABLED'

ANON_REDIRECT = None

USE_API = False
API_KEYS = []

ENABLE_HTTPS = False
HTTPS_CERT = None
HTTPS_KEY = None

LAUNCH_BROWSER = False
CACHE_DIR = None
ACTUAL_CACHE_DIR = None
ZONEINFO_DIR = None
ROOT_DIRS = None
TRASH_REMOVE_SHOW = False
TRASH_ROTATE_LOGS = False
HOME_SEARCH_FOCUS = True
DISPLAY_FREESPACE = True
SORT_ARTICLE = False
DEBUG = False
SHOW_TAGS = []
SHOW_TAG_DEFAULT = ''
SHOWLIST_TAGVIEW = ''

METADATA_XBMC = None
METADATA_XBMC_12PLUS = None
METADATA_MEDIABROWSER = None
METADATA_PS3 = None
METADATA_WDTV = None
METADATA_TIVO = None
METADATA_MEDE8ER = None
METADATA_KODI = None

RESULTS_SORTBY = None

TVINFO_DEFAULT = 0
TVINFO_TIMEOUT = 20
QUALITY_DEFAULT = SD
WANTED_BEGIN_DEFAULT = 0
WANTED_LATEST_DEFAULT = 0
PAUSE_DEFAULT = False
STATUS_DEFAULT = SKIPPED
SCENE_DEFAULT = False
SUBTITLES_DEFAULT = False
FLATTEN_FOLDERS_DEFAULT = False
ANIME_DEFAULT = False
USE_IMDB_INFO = True
IMDB_ACCOUNTS = []
IMDB_DEFAULT_LIST_ID = '64552276'
IMDB_DEFAULT_LIST_NAME = 'SickGear'
PROVIDER_ORDER = []
PROVIDER_HOMES = {}

NAMING_MULTI_EP = False
NAMING_ANIME_MULTI_EP = False
NAMING_PATTERN = None
NAMING_ABD_PATTERN = None
NAMING_CUSTOM_ABD = False
NAMING_SPORTS_PATTERN = None
NAMING_CUSTOM_SPORTS = False
NAMING_ANIME_PATTERN = None
NAMING_CUSTOM_ANIME = False
NAMING_FORCE_FOLDERS = False
NAMING_STRIP_YEAR = False
NAMING_ANIME = 3

USE_NZBS = False
USE_TORRENTS = False

NZB_METHOD = None
NZB_DIR = None
USENET_RETENTION = 500
TORRENT_METHOD = None
TORRENT_DIR = None
DOWNLOAD_PROPERS = False
PROPERS_WEBDL_ONEGRP = True
WEBDL_TYPES = []
ALLOW_HIGH_PRIORITY = False
NEWZNAB_DATA = ''

DEFAULT_MEDIAPROCESS_INTERVAL = 10
DEFAULT_BACKLOG_PERIOD = 21
DEFAULT_RECENTSEARCH_INTERVAL = 40
DEFAULT_WATCHEDSTATE_INTERVAL = 10

MEDIAPROCESS_INTERVAL = DEFAULT_MEDIAPROCESS_INTERVAL
BACKLOG_PERIOD = DEFAULT_BACKLOG_PERIOD
BACKLOG_LIMITED_PERIOD = 7
RECENTSEARCH_INTERVAL = DEFAULT_RECENTSEARCH_INTERVAL

RECENTSEARCH_STARTUP = False
BACKLOG_NOFULL = False

MIN_MEDIAPROCESS_INTERVAL = 1
MIN_RECENTSEARCH_INTERVAL = 10
MIN_BACKLOG_PERIOD = 7
MAX_BACKLOG_PERIOD = 42
MIN_WATCHEDSTATE_INTERVAL = 10
MAX_WATCHEDSTATE_INTERVAL = 60

SEARCH_UNAIRED = False
UNAIRED_RECENT_SEARCH_ONLY = True
FLARESOLVERR_HOST = None

ADD_SHOWS_WO_DIR = False
ADD_SHOWS_METALANG = 'en'
CREATE_MISSING_SHOW_DIRS = False
SHOW_DIRS_WITH_DOTS = False
RENAME_EPISODES = False
RENAME_TBA_EPISODES = True
RENAME_NAME_CHANGED_EPISODES = False
AIRDATE_EPISODES = False
PROCESS_AUTOMATICALLY = False
KEEP_PROCESSED_DIR = False
PROCESS_LAST_DIR = None
PROCESS_LAST_METHOD = None
PROCESS_LAST_CLEANUP = False
PROCESS_METHOD = None
MOVE_ASSOCIATED_FILES = False
POSTPONE_IF_SYNC_FILES = True
PROCESS_POSITIVE_LOG = True
NFO_RENAME = True
TV_DOWNLOAD_DIR = None
UNPACK = False
SKIP_REMOVED_FILES = False

NZBGET_USERNAME = None
NZBGET_PASSWORD = None
NZBGET_CATEGORY = None
NZBGET_HOST = None
NZBGET_USE_HTTPS = False
NZBGET_PRIORITY = 100
NZBGET_SCRIPT_VERSION = None
NZBGET_MAP = None
NZBGET_SKIP_PM = False

SAB_USERNAME = None
SAB_PASSWORD = None
SAB_APIKEY = None
SAB_CATEGORY = None
SAB_HOST = ''

TORRENT_USERNAME = None
TORRENT_PASSWORD = None
TORRENT_HOST = ''
TORRENT_PATH = ''
TORRENT_SEED_TIME = 0
TORRENT_PAUSED = False
TORRENT_HIGH_BANDWIDTH = False
TORRENT_LABEL = ''
TORRENT_LABEL_VAR = 1
TORRENT_VERIFY_CERT = False

USE_EMBY = False
EMBY_UPDATE_LIBRARY = False
EMBY_PARENT_MAPS = None
EMBY_HOST = None
EMBY_APIKEY = None
EMBY_WATCHEDSTATE_SCHEDULED = False
EMBY_WATCHEDSTATE_INTERVAL = DEFAULT_WATCHEDSTATE_INTERVAL

USE_KODI = False
KODI_ALWAYS_ON = True
KODI_NOTIFY_ONSNATCH = False
KODI_NOTIFY_ONDOWNLOAD = False
KODI_NOTIFY_ONSUBTITLEDOWNLOAD = False
KODI_UPDATE_LIBRARY = False
KODI_UPDATE_FULL = False
KODI_UPDATE_ONLYFIRST = False
KODI_PARENT_MAPS = None
KODI_HOST = ''
KODI_USERNAME = None
KODI_PASSWORD = None

USE_PLEX = False
PLEX_NOTIFY_ONSNATCH = False
PLEX_NOTIFY_ONDOWNLOAD = False
PLEX_NOTIFY_ONSUBTITLEDOWNLOAD = False
PLEX_UPDATE_LIBRARY = False
PLEX_PARENT_MAPS = None
PLEX_SERVER_HOST = None
PLEX_HOST = None
PLEX_USERNAME = None
PLEX_PASSWORD = None
PLEX_WATCHEDSTATE_SCHEDULED = False
PLEX_WATCHEDSTATE_INTERVAL = DEFAULT_WATCHEDSTATE_INTERVAL

USE_XBMC = False
XBMC_ALWAYS_ON = True
XBMC_NOTIFY_ONSNATCH = False
XBMC_NOTIFY_ONDOWNLOAD = False
XBMC_NOTIFY_ONSUBTITLEDOWNLOAD = False
XBMC_UPDATE_LIBRARY = False
XBMC_UPDATE_FULL = False
XBMC_UPDATE_ONLYFIRST = False
XBMC_HOST = ''
XBMC_USERNAME = None
XBMC_PASSWORD = None

QUEUE_UPDATE_LIBRARY = []

USE_NMJ = False
NMJ_HOST = None
NMJ_DATABASE = None
NMJ_MOUNT = None

USE_NMJv2 = False
NMJv2_HOST = None
NMJv2_DATABASE = None
NMJv2_DBLOC = None

USE_SYNOINDEX = False
SYNOINDEX_UPDATE_LIBRARY = True

USE_SYNOLOGYNOTIFIER = False
SYNOLOGYNOTIFIER_NOTIFY_ONSNATCH = False
SYNOLOGYNOTIFIER_NOTIFY_ONDOWNLOAD = False
SYNOLOGYNOTIFIER_NOTIFY_ONSUBTITLEDOWNLOAD = False

USE_PYTIVO = False
PYTIVO_HOST = ''
PYTIVO_SHARE_NAME = ''
PYTIVO_TIVO_NAME = ''

USE_BOXCAR2 = False
BOXCAR2_NOTIFY_ONSNATCH = False
BOXCAR2_NOTIFY_ONDOWNLOAD = False
BOXCAR2_NOTIFY_ONSUBTITLEDOWNLOAD = False
BOXCAR2_ACCESSTOKEN = None
BOXCAR2_SOUND = None

USE_PUSHBULLET = False
PUSHBULLET_NOTIFY_ONSNATCH = False
PUSHBULLET_NOTIFY_ONDOWNLOAD = False
PUSHBULLET_NOTIFY_ONSUBTITLEDOWNLOAD = False
PUSHBULLET_ACCESS_TOKEN = None
PUSHBULLET_DEVICE_IDEN = None

USE_PUSHOVER = False
PUSHOVER_NOTIFY_ONSNATCH = False
PUSHOVER_NOTIFY_ONDOWNLOAD = False
PUSHOVER_NOTIFY_ONSUBTITLEDOWNLOAD = False
PUSHOVER_USERKEY = None
PUSHOVER_APIKEY = None
PUSHOVER_PRIORITY = '0'
PUSHOVER_DEVICE = None
PUSHOVER_SOUND = None

USE_GROWL = False
GROWL_NOTIFY_ONSNATCH = False
GROWL_NOTIFY_ONDOWNLOAD = False
GROWL_NOTIFY_ONSUBTITLEDOWNLOAD = False
GROWL_HOST = ''

USE_PROWL = False
PROWL_NOTIFY_ONSNATCH = False
PROWL_NOTIFY_ONDOWNLOAD = False
PROWL_NOTIFY_ONSUBTITLEDOWNLOAD = False
PROWL_API = None
PROWL_PRIORITY = '0'

USE_LIBNOTIFY = False
LIBNOTIFY_NOTIFY_ONSNATCH = False
LIBNOTIFY_NOTIFY_ONDOWNLOAD = False
LIBNOTIFY_NOTIFY_ONSUBTITLEDOWNLOAD = False

USE_PUSHALOT = False
PUSHALOT_NOTIFY_ONSNATCH = False
PUSHALOT_NOTIFY_ONDOWNLOAD = False
PUSHALOT_NOTIFY_ONSUBTITLEDOWNLOAD = False
PUSHALOT_AUTHORIZATIONTOKEN = None

USE_TRAKT = False
TRAKT_REMOVE_WATCHLIST = False
TRAKT_REMOVE_SERIESLIST = False
TRAKT_USE_WATCHLIST = False
TRAKT_METHOD_ADD = 0
TRAKT_START_PAUSED = False
TRAKT_SYNC = False
TRAKT_DEFAULT_INDEXER = None
TRAKT_UPDATE_COLLECTION = {}

USE_SLACK = False
SLACK_NOTIFY_ONSNATCH = False
SLACK_NOTIFY_ONDOWNLOAD = False
SLACK_NOTIFY_ONSUBTITLEDOWNLOAD = False
SLACK_CHANNEL = None
SLACK_AS_AUTHED = False
SLACK_BOT_NAME = None
SLACK_ICON_URL = None
SLACK_ACCESS_TOKEN = None

USE_DISCORD = False
DISCORD_NOTIFY_ONSNATCH = False
DISCORD_NOTIFY_ONDOWNLOAD = False
DISCORD_NOTIFY_ONSUBTITLEDOWNLOAD = False
DISCORD_AS_AUTHED = False
DISCORD_USERNAME = None
DISCORD_ICON_URL = None
DISCORD_AS_TTS = 0
DISCORD_ACCESS_TOKEN = None

USE_GITTER = False
GITTER_NOTIFY_ONSNATCH = False
GITTER_NOTIFY_ONDOWNLOAD = False
GITTER_NOTIFY_ONSUBTITLEDOWNLOAD = False
GITTER_ROOM = None
GITTER_ACCESS_TOKEN = None

USE_TELEGRAM = False
TELEGRAM_NOTIFY_ONSNATCH = False
TELEGRAM_NOTIFY_ONDOWNLOAD = False
TELEGRAM_NOTIFY_ONSUBTITLEDOWNLOAD = False
TELEGRAM_SEND_IMAGE = True
TELEGRAM_QUIET = False
TELEGRAM_ACCESS_TOKEN = None
TELEGRAM_CHATID = None

USE_EMAIL = False
EMAIL_OLD_SUBJECTS = False
EMAIL_NOTIFY_ONSNATCH = False
EMAIL_NOTIFY_ONDOWNLOAD = False
EMAIL_NOTIFY_ONSUBTITLEDOWNLOAD = False
EMAIL_HOST = None
EMAIL_PORT = 25
EMAIL_TLS = False
EMAIL_USER = None
EMAIL_PASSWORD = None
EMAIL_FROM = None
EMAIL_LIST = None

USE_ANIDB = False
ANIDB_USERNAME = None
ANIDB_PASSWORD = None
ANIDB_USE_MYLIST = False
# noinspection PyTypeChecker
ADBA_CONNECTION = None  # type: Connection
ANIME_TREAT_AS_HDTV = False

GUI_NAME = ''
DEFAULT_HOME = None
FANART_LIMIT = None
FANART_PANEL = None
FANART_RATINGS = {}
HOME_LAYOUT = None
FOOTER_TIME_LAYOUT = 0
POSTER_SORTBY = None
POSTER_SORTDIR = None
DISPLAY_SHOW_GLIDE = {}
DISPLAY_SHOW_GLIDE_SLIDETIME = 3000
DISPLAY_SHOW_VIEWMODE = 0
DISPLAY_SHOW_BACKGROUND = False
DISPLAY_SHOW_BACKGROUND_TRANSLUCENT = False
DISPLAY_SHOW_VIEWART = 0
DISPLAY_SHOW_MINIMUM = True
DISPLAY_SHOW_SPECIALS = False
EPISODE_VIEW_VIEWMODE = 0
EPISODE_VIEW_BACKGROUND = False
EPISODE_VIEW_BACKGROUND_TRANSLUCENT = False
EPISODE_VIEW_LAYOUT = None
EPISODE_VIEW_SORT = None
EPISODE_VIEW_DISPLAY_PAUSED = 0
EPISODE_VIEW_POSTERS = True
EPISODE_VIEW_MISSED_RANGE = 7
HISTORY_LAYOUT = None
BROWSELIST_HIDDEN = []
BROWSELIST_MRU = {}

FUZZY_DATING = False
TRIM_ZERO = False
DATE_PRESET = None
TIME_PRESET = None
TIME_PRESET_W_SECONDS = None
TIMEZONE_DISPLAY = None
THEME_NAME = None

USE_SUBTITLES = False
SUBTITLES_LANGUAGES = []
SUBTITLES_DIR = ''
SUBTITLES_OS_HASH = True
SUBTITLES_SERVICES_LIST = []
SUBTITLES_SERVICES_ENABLED = []
SUBTITLES_SERVICES_AUTH = [['', '']]
SUBTITLES_HISTORY = False
SUBTITLES_FINDER_INTERVAL = 1

USE_FAILED_DOWNLOADS = False
DELETE_FAILED = False

BACKUP_DB_PATH = ''  # type: AnyStr
BACKUP_DB_ONEDAY = False  # type: bool
BACKUP_DB_MAX_COUNT = 14  # type: int
BACKUP_DB_DEFAULT_COUNT = 14  # type: int

UPDATES_TODO = {}

EXTRA_SCRIPTS = []
SG_EXTRA_SCRIPTS = []

GIT_PATH = None

IGNORE_WORDS = {
    r'^(?=.*?\bspanish\b)((?!spanish.?princess).)*$',
    'core2hd', 'hevc', 'MrLss', 'reenc', 'x265', 'danish', 'deutsch', 'dutch', 'flemish', 'french',
    'german', 'italian', 'nordic', 'norwegian', 'portuguese', 'spanish', 'swedish', 'turkish'
}
IGNORE_WORDS_REGEX = True
REQUIRE_WORDS = set()
REQUIRE_WORDS_REGEX = False

WANTEDLIST_CACHE = None

CALENDAR_UNPROTECTED = False

TMDB_API_KEY = TmdbIndexer.API_KEY
FANART_API_KEY = '3728ca1a2a937ba0c93b6e63cc86cecb'

# to switch between staging and production TRAKT environment
TRAKT_STAGING = False

TRAKT_TIMEOUT = 60
TRAKT_VERIFY = True
TRAKT_CONNECTED_ACCOUNT = None
TRAKT_ACCOUNTS = {}  # type: Dict[int, TraktAccount]
TRAKT_MRU = ''

if TRAKT_STAGING:
    # staging trakt values:
    TRAKT_CLIENT_ID = '2aae3052f90b14235d184cc8f709b12b4fd8ae35f339a060a890c70db92be87a'
    TRAKT_CLIENT_SECRET = '900e03471220503843d4a856bfbef17080cddb630f2b7df6a825e96e3ff3c39e'
    TRAKT_PIN_URL = 'https://staging.trakt.tv/pin/638'
    TRAKT_BASE_URL = 'http' + '://api.staging.trakt.tv/'
else:
    # production trakt values:
    TRAKT_CLIENT_ID = 'f1c453c67d81f1307f9118172c408a883eb186b094d5ea33080d59ddedb7fc7c'
    TRAKT_CLIENT_SECRET = '12efb6fb6e863a08934d9904032a90008325df7e23514650cade55e7e7c118c5'
    TRAKT_PIN_URL = 'https://trakt.tv/pin/6314'
    TRAKT_BASE_URL = 'https://api.trakt.tv/'

IMDB_MRU = ''
MC_MRU = ''
NE_MRU = ''
TMDB_MRU = ''
TVC_MRU = ''
TVDB_MRU = ''
TVM_MRU = ''

COOKIE_SECRET = b64encodestring(uuid.uuid4().bytes + uuid.uuid4().bytes)

CACHE_IMAGE_URL_LIST = classes.ImageUrlList()

__INITIALIZED__ = False
__INIT_STAGE__ = 0

# don't reassign MEMCACHE var without reassigning sg_helpers.MEMCACHE
# and scene_exceptions.MEMCACHE
# as long as the pointer is the same (dict only modified) all is fine
MEMCACHE = {}
sg_helpers.MEMCACHE = MEMCACHE
scene_exceptions.MEMCACHE = MEMCACHE
MEMCACHE_FLAG_IMAGES = {}


def get_backlog_cycle_time():
    cycletime = RECENTSEARCH_INTERVAL * 2 + 7
    return max([cycletime, 720])


def initialize(console_logging=True):
    with INIT_LOCK:

        # Misc
        global __INITIALIZED__, __INIT_STAGE__

        if __INITIALIZED__:
            return False

        __INIT_STAGE__ += 1

        if 1 == __INIT_STAGE__:
            init_stage_1(console_logging)
        else:
            return init_stage_2()


def init_stage_1(console_logging):

    # Misc
    global showList, showDict, switched_shows, provider_list, newznab_providers, torrent_rss_providers, \
        WEB_HOST, WEB_ROOT, ACTUAL_CACHE_DIR, CACHE_DIR, ZONEINFO_DIR, ADD_SHOWS_WO_DIR, ADD_SHOWS_METALANG, \
        CREATE_MISSING_SHOW_DIRS, SHOW_DIRS_WITH_DOTS, \
        RECENTSEARCH_STARTUP, NAMING_FORCE_FOLDERS, SOCKET_TIMEOUT, DEBUG, TVINFO_DEFAULT, \
        CONFIG_FILE, CONFIG_VERSION, CONFIG_OLD, CONFIG_LOADED, \
        REMOVE_FILENAME_CHARS, IMPORT_DEFAULT_CHECKED_SHOWS, WANTEDLIST_CACHE, MODULE_UPDATE_STRING, EXT_UPDATES
    # Add Show Search
    global RESULTS_SORTBY
    # Add Show Defaults
    global QUALITY_DEFAULT, WANTED_BEGIN_DEFAULT, WANTED_LATEST_DEFAULT, SHOW_TAG_DEFAULT, PAUSE_DEFAULT, \
        STATUS_DEFAULT, SCENE_DEFAULT, SUBTITLES_DEFAULT, FLATTEN_FOLDERS_DEFAULT, ANIME_DEFAULT
    # Post-processing
    global KEEP_PROCESSED_DIR, PROCESS_LAST_DIR, PROCESS_LAST_METHOD, PROCESS_LAST_CLEANUP
    # Views
    global GUI_NAME, HOME_LAYOUT, FOOTER_TIME_LAYOUT, POSTER_SORTBY, POSTER_SORTDIR, DISPLAY_SHOW_SPECIALS, \
        EPISODE_VIEW_LAYOUT, EPISODE_VIEW_SORT, EPISODE_VIEW_DISPLAY_PAUSED, \
        EPISODE_VIEW_MISSED_RANGE, EPISODE_VIEW_POSTERS, FANART_PANEL, FANART_RATINGS, \
        EPISODE_VIEW_VIEWMODE, EPISODE_VIEW_BACKGROUND, EPISODE_VIEW_BACKGROUND_TRANSLUCENT, \
        DISPLAY_SHOW_GLIDE, DISPLAY_SHOW_GLIDE_SLIDETIME, \
        DISPLAY_SHOW_VIEWMODE, DISPLAY_SHOW_BACKGROUND, DISPLAY_SHOW_BACKGROUND_TRANSLUCENT, \
        DISPLAY_SHOW_VIEWART, DISPLAY_SHOW_MINIMUM, DISPLAY_SHOW_SPECIALS, HISTORY_LAYOUT, \
        BROWSELIST_HIDDEN, BROWSELIST_MRU
    # Gen Config/Misc
    global LAUNCH_BROWSER, UPDATE_SHOWS_ON_START, SHOW_UPDATE_HOUR, \
        TRASH_REMOVE_SHOW, TRASH_ROTATE_LOGS, ACTUAL_LOG_DIR, LOG_DIR, TVINFO_TIMEOUT, ROOT_DIRS, \
        UPDATE_NOTIFY, UPDATE_AUTO, UPDATE_INTERVAL, NOTIFY_ON_UPDATE,\
        UPDATE_PACKAGES_NOTIFY, UPDATE_PACKAGES_AUTO, UPDATE_PACKAGES_MENU, UPDATE_PACKAGES_INTERVAL
    # Gen Config/Interface
    global THEME_NAME, DEFAULT_HOME, FANART_LIMIT, SHOWLIST_TAGVIEW, SHOW_TAGS, \
        HOME_SEARCH_FOCUS, USE_IMDB_INFO, IMDB_ACCOUNTS, DISPLAY_FREESPACE, SORT_ARTICLE, FUZZY_DATING, TRIM_ZERO, \
        DATE_PRESET, TIME_PRESET, TIME_PRESET_W_SECONDS, TIMEZONE_DISPLAY, \
        WEB_USERNAME, WEB_PASSWORD, CALENDAR_UNPROTECTED, USE_API, API_KEYS, WEB_PORT, WEB_LOG, \
        ENABLE_HTTPS, HTTPS_CERT, HTTPS_KEY, WEB_IPV6, WEB_IPV64, HANDLE_REVERSE_PROXY, \
        SEND_SECURITY_HEADERS, ALLOWED_HOSTS, ALLOW_ANYIP
    # Gen Config/Advanced
    global BRANCH, CUR_COMMIT_BRANCH, GIT_REMOTE, CUR_COMMIT_HASH, GIT_PATH, CPU_PRESET, ANON_REDIRECT, \
        ENCRYPTION_VERSION, PROXY_SETTING, PROXY_INDEXERS, FILE_LOGGING_PRESET
    # Search Settings/Episode
    global DOWNLOAD_PROPERS, PROPERS_WEBDL_ONEGRP, WEBDL_TYPES, RECENTSEARCH_INTERVAL, \
        BACKLOG_LIMITED_PERIOD, BACKLOG_NOFULL, BACKLOG_PERIOD, USENET_RETENTION, IGNORE_WORDS, REQUIRE_WORDS, \
        IGNORE_WORDS, IGNORE_WORDS_REGEX, REQUIRE_WORDS, REQUIRE_WORDS_REGEX, \
        ALLOW_HIGH_PRIORITY, SEARCH_UNAIRED, UNAIRED_RECENT_SEARCH_ONLY, FLARESOLVERR_HOST
    # Search Settings/NZB search
    global USE_NZBS, NZB_METHOD, NZB_DIR, SAB_HOST, SAB_USERNAME, SAB_PASSWORD, SAB_APIKEY, SAB_CATEGORY, \
        NZBGET_USE_HTTPS, NZBGET_HOST, NZBGET_USERNAME, NZBGET_PASSWORD, NZBGET_CATEGORY, NZBGET_PRIORITY, \
        NZBGET_SCRIPT_VERSION, NZBGET_MAP, NZBGET_SKIP_PM
    # Search Settings/Torrent search
    global USE_TORRENTS, TORRENT_METHOD, TORRENT_DIR, TORRENT_HOST, TORRENT_USERNAME, TORRENT_PASSWORD, \
        TORRENT_LABEL, TORRENT_LABEL_VAR, TORRENT_PATH, TORRENT_SEED_TIME, TORRENT_PAUSED, \
        TORRENT_HIGH_BANDWIDTH, TORRENT_VERIFY_CERT
    # Media Providers
    global PROVIDER_ORDER, NEWZNAB_DATA, PROVIDER_HOMES
    # Subtitles
    global USE_SUBTITLES, SUBTITLES_LANGUAGES, SUBTITLES_DIR, SUBTITLES_FINDER_INTERVAL, SUBTITLES_OS_HASH, \
        SUBTITLES_HISTORY, SUBTITLES_SERVICES_LIST, SUBTITLES_SERVICES_ENABLED, SUBTITLES_SERVICES_AUTH
    # Media Process/Post-Processing
    global TV_DOWNLOAD_DIR, PROCESS_METHOD, PROCESS_AUTOMATICALLY, MEDIAPROCESS_INTERVAL, \
        POSTPONE_IF_SYNC_FILES, PROCESS_POSITIVE_LOG, EXTRA_SCRIPTS, SG_EXTRA_SCRIPTS, \
        DEFAULT_MEDIAPROCESS_INTERVAL, MIN_MEDIAPROCESS_INTERVAL, \
        UNPACK, SKIP_REMOVED_FILES, MOVE_ASSOCIATED_FILES, NFO_RENAME, \
        RENAME_EPISODES, RENAME_TBA_EPISODES, RENAME_NAME_CHANGED_EPISODES, \
        AIRDATE_EPISODES, USE_FAILED_DOWNLOADS, DELETE_FAILED
    # Media Process/Episode Naming
    global NAMING_PATTERN, NAMING_MULTI_EP, NAMING_STRIP_YEAR, NAMING_CUSTOM_ABD, NAMING_ABD_PATTERN, \
        NAMING_CUSTOM_SPORTS, NAMING_SPORTS_PATTERN, \
        NAMING_CUSTOM_ANIME, NAMING_ANIME_PATTERN, NAMING_ANIME_MULTI_EP, NAMING_ANIME
    # Media Process/Metadata
    global METADATA_KODI, METADATA_MEDE8ER, METADATA_XBMC, METADATA_MEDIABROWSER, \
        METADATA_PS3, METADATA_TIVO, METADATA_WDTV, METADATA_XBMC_12PLUS
    # Notification Settings/HT and NAS
    global USE_EMBY, EMBY_UPDATE_LIBRARY, EMBY_PARENT_MAPS, EMBY_HOST, EMBY_APIKEY, \
        EMBY_WATCHEDSTATE_SCHEDULED, EMBY_WATCHEDSTATE_INTERVAL, \
        USE_KODI, KODI_ALWAYS_ON, KODI_UPDATE_LIBRARY, KODI_UPDATE_FULL, KODI_UPDATE_ONLYFIRST, \
        KODI_PARENT_MAPS, KODI_HOST, KODI_USERNAME, KODI_PASSWORD, KODI_NOTIFY_ONSNATCH, \
        KODI_NOTIFY_ONDOWNLOAD, KODI_NOTIFY_ONSUBTITLEDOWNLOAD, \
        USE_XBMC, XBMC_ALWAYS_ON, XBMC_NOTIFY_ONSNATCH, XBMC_NOTIFY_ONDOWNLOAD, XBMC_NOTIFY_ONSUBTITLEDOWNLOAD, \
        XBMC_UPDATE_LIBRARY, XBMC_UPDATE_FULL, XBMC_UPDATE_ONLYFIRST, XBMC_HOST, XBMC_USERNAME, XBMC_PASSWORD, \
        USE_PLEX, PLEX_USERNAME, PLEX_PASSWORD, PLEX_UPDATE_LIBRARY, PLEX_PARENT_MAPS, PLEX_SERVER_HOST, \
        PLEX_NOTIFY_ONSNATCH, PLEX_NOTIFY_ONDOWNLOAD, PLEX_NOTIFY_ONSUBTITLEDOWNLOAD, PLEX_HOST, \
        PLEX_WATCHEDSTATE_SCHEDULED, PLEX_WATCHEDSTATE_INTERVAL, \
        USE_NMJ, NMJ_HOST, NMJ_DATABASE, NMJ_MOUNT, \
        USE_NMJv2, NMJv2_HOST, NMJv2_DATABASE, NMJv2_DBLOC, \
        USE_SYNOINDEX, \
        USE_SYNOLOGYNOTIFIER, SYNOLOGYNOTIFIER_NOTIFY_ONSNATCH, \
        SYNOLOGYNOTIFIER_NOTIFY_ONDOWNLOAD, SYNOLOGYNOTIFIER_NOTIFY_ONSUBTITLEDOWNLOAD, \
        USE_PYTIVO, PYTIVO_HOST, PYTIVO_SHARE_NAME, PYTIVO_TIVO_NAME
    # Notification Settings/Devices
    global USE_GROWL, GROWL_NOTIFY_ONSNATCH, GROWL_NOTIFY_ONDOWNLOAD, GROWL_NOTIFY_ONSUBTITLEDOWNLOAD, \
        GROWL_HOST, \
        USE_PROWL, PROWL_NOTIFY_ONSNATCH, PROWL_NOTIFY_ONDOWNLOAD, PROWL_NOTIFY_ONSUBTITLEDOWNLOAD, \
        PROWL_API, PROWL_PRIORITY, \
        USE_LIBNOTIFY, LIBNOTIFY_NOTIFY_ONSNATCH, LIBNOTIFY_NOTIFY_ONDOWNLOAD, \
        LIBNOTIFY_NOTIFY_ONSUBTITLEDOWNLOAD, \
        USE_PUSHOVER, PUSHOVER_NOTIFY_ONSNATCH, PUSHOVER_NOTIFY_ONDOWNLOAD, PUSHOVER_NOTIFY_ONSUBTITLEDOWNLOAD, \
        PUSHOVER_USERKEY, PUSHOVER_APIKEY, PUSHOVER_PRIORITY, PUSHOVER_DEVICE, PUSHOVER_SOUND, \
        USE_BOXCAR2, BOXCAR2_NOTIFY_ONSNATCH, BOXCAR2_NOTIFY_ONDOWNLOAD, BOXCAR2_NOTIFY_ONSUBTITLEDOWNLOAD, \
        BOXCAR2_ACCESSTOKEN, BOXCAR2_SOUND, \
        USE_PUSHALOT, PUSHALOT_NOTIFY_ONSNATCH, PUSHALOT_NOTIFY_ONDOWNLOAD, \
        PUSHALOT_NOTIFY_ONSUBTITLEDOWNLOAD, PUSHALOT_AUTHORIZATIONTOKEN, \
        USE_PUSHBULLET, PUSHBULLET_NOTIFY_ONSNATCH, PUSHBULLET_NOTIFY_ONDOWNLOAD, \
        PUSHBULLET_NOTIFY_ONSUBTITLEDOWNLOAD, PUSHBULLET_ACCESS_TOKEN, PUSHBULLET_DEVICE_IDEN
    # Notification Settings/Social
    global USE_TRAKT, TRAKT_CONNECTED_ACCOUNT, TRAKT_ACCOUNTS, TRAKT_MRU, TRAKT_VERIFY, \
        TRAKT_USE_WATCHLIST, TRAKT_REMOVE_WATCHLIST, TRAKT_TIMEOUT, TRAKT_METHOD_ADD, TRAKT_START_PAUSED, \
        TRAKT_SYNC, TRAKT_DEFAULT_INDEXER, TRAKT_REMOVE_SERIESLIST, TRAKT_UPDATE_COLLECTION, \
        MC_MRU, NE_MRU, TMDB_MRU, TVC_MRU, TVDB_MRU, TVM_MRU, \
        USE_SLACK, SLACK_NOTIFY_ONSNATCH, SLACK_NOTIFY_ONDOWNLOAD, SLACK_NOTIFY_ONSUBTITLEDOWNLOAD, \
        SLACK_CHANNEL, SLACK_AS_AUTHED, SLACK_BOT_NAME, SLACK_ICON_URL, SLACK_ACCESS_TOKEN, \
        USE_DISCORD, DISCORD_NOTIFY_ONSNATCH, DISCORD_NOTIFY_ONDOWNLOAD, \
        DISCORD_NOTIFY_ONSUBTITLEDOWNLOAD, \
        DISCORD_AS_AUTHED, DISCORD_USERNAME, DISCORD_ICON_URL, DISCORD_AS_TTS, DISCORD_ACCESS_TOKEN,\
        USE_GITTER, GITTER_NOTIFY_ONSNATCH, GITTER_NOTIFY_ONDOWNLOAD, GITTER_NOTIFY_ONSUBTITLEDOWNLOAD,\
        GITTER_ROOM, GITTER_ACCESS_TOKEN, \
        USE_TELEGRAM, TELEGRAM_NOTIFY_ONSNATCH, TELEGRAM_NOTIFY_ONDOWNLOAD, TELEGRAM_NOTIFY_ONSUBTITLEDOWNLOAD, \
        TELEGRAM_SEND_IMAGE, TELEGRAM_QUIET, TELEGRAM_ACCESS_TOKEN, TELEGRAM_CHATID, \
        USE_EMAIL, EMAIL_NOTIFY_ONSNATCH, EMAIL_NOTIFY_ONDOWNLOAD, EMAIL_NOTIFY_ONSUBTITLEDOWNLOAD, EMAIL_FROM, \
        EMAIL_HOST, EMAIL_PORT, EMAIL_TLS, EMAIL_USER, EMAIL_PASSWORD, EMAIL_LIST, EMAIL_OLD_SUBJECTS
    # Anime Settings
    global ANIME_TREAT_AS_HDTV, USE_ANIDB, ANIDB_USERNAME, ANIDB_PASSWORD, ANIDB_USE_MYLIST
    # db backup settings
    global BACKUP_DB_PATH, BACKUP_DB_ONEDAY, BACKUP_DB_MAX_COUNT, BACKUP_DB_DEFAULT_COUNT
    # pip update states
    global UPDATES_TODO

    for stanza in ('General', 'Blackhole', 'SABnzbd', 'NZBGet', 'Emby', 'Kodi', 'XBMC', 'PLEX',
                   'Growl', 'Prowl', 'Slack', 'Discord', 'Boxcar2', 'NMJ', 'NMJv2',
                   'Synology', 'SynologyNotifier',
                   'pyTivo', 'Pushalot', 'Pushbullet', 'Subtitles'):
        check_section(CFG, stanza)

    update_config = False

    WANTEDLIST_CACHE = common.WantedQualities()

    # wanted branch
    BRANCH = check_setting_str(CFG, 'General', 'branch', '')

    # git_remote
    GIT_REMOTE = check_setting_str(CFG, 'General', 'git_remote', 'origin')

    ACTUAL_CACHE_DIR = check_setting_str(CFG, 'General', 'cache_dir', 'cache')

    # unless they specify, put the cache dir inside the data dir
    if not os.path.isabs(ACTUAL_CACHE_DIR):
        CACHE_DIR = os.path.join(DATA_DIR, ACTUAL_CACHE_DIR)
    else:
        CACHE_DIR = ACTUAL_CACHE_DIR

    if not helpers.make_dir(CACHE_DIR):
        logger.error('!!! creating local cache dir failed, using system default')
        CACHE_DIR = None

    # clean cache folders
    if CACHE_DIR:
        helpers.clear_cache()
        ZONEINFO_DIR = os.path.join(CACHE_DIR, 'zoneinfo')
        if not os.path.isdir(ZONEINFO_DIR) and not helpers.make_path(ZONEINFO_DIR):
            logger.error('!!! creating local zoneinfo dir failed')
    sg_helpers.CACHE_DIR = CACHE_DIR
    sg_helpers.DATA_DIR = DATA_DIR

    THEME_NAME = check_setting_str(CFG, 'GUI', 'theme_name', 'dark')
    GUI_NAME = check_setting_str(CFG, 'GUI', 'gui_name', 'slick')
    DEFAULT_HOME = check_setting_str(CFG, 'GUI', 'default_home', 'episodes')
    FANART_LIMIT = check_setting_int(CFG, 'GUI', 'fanart_limit', 3)
    FANART_PANEL = check_setting_str(CFG, 'GUI', 'fanart_panel', 'highlight2')
    FANART_RATINGS = sg_helpers.ast_eval(check_setting_str(CFG, 'GUI', 'fanart_ratings', None), {})
    USE_IMDB_INFO = bool(check_setting_int(CFG, 'GUI', 'use_imdb_info', 1))
    IMDB_ACCOUNTS = CFG.get('GUI', []).get('imdb_accounts', [IMDB_DEFAULT_LIST_ID, IMDB_DEFAULT_LIST_NAME])
    HOME_SEARCH_FOCUS = bool(check_setting_int(CFG, 'General', 'home_search_focus', HOME_SEARCH_FOCUS))
    DISPLAY_FREESPACE = bool(check_setting_int(CFG, 'General', 'display_freespace', 1))
    SORT_ARTICLE = bool(check_setting_int(CFG, 'General', 'sort_article', 0))
    FUZZY_DATING = bool(check_setting_int(CFG, 'GUI', 'fuzzy_dating', 0))
    TRIM_ZERO = bool(check_setting_int(CFG, 'GUI', 'trim_zero', 0))
    DATE_PRESET = check_setting_str(CFG, 'GUI', 'date_preset', '%x')
    TIME_PRESET_W_SECONDS = check_setting_str(CFG, 'GUI', 'time_preset', '%I:%M:%S %p')
    TIME_PRESET = TIME_PRESET_W_SECONDS.replace(':%S', '')
    TIMEZONE_DISPLAY = check_setting_str(CFG, 'GUI', 'timezone_display', 'network')
    SHOW_TAGS = check_setting_str(CFG, 'GUI', 'show_tags', 'Show List').split(',')
    SHOW_TAG_DEFAULT = check_setting_str(CFG, 'GUI', 'show_tag_default',
                                         check_setting_str(CFG, 'GUI', 'default_show_tag', 'Show List'))
    SHOWLIST_TAGVIEW = check_setting_str(CFG, 'GUI', 'showlist_tagview', 'standard')

    ACTUAL_LOG_DIR = check_setting_str(CFG, 'General', 'log_dir', 'Logs')
    # put the log dir inside the data dir, unless an absolute path
    LOG_DIR = os.path.normpath(os.path.join(DATA_DIR, ACTUAL_LOG_DIR))

    if not helpers.make_dir(LOG_DIR):
        logger.error('!!! no log folder, logging to screen only!')

    FILE_LOGGING_PRESET = check_setting_str(CFG, 'General', 'file_logging_preset', 'DEBUG')
    if bool(check_setting_int(CFG, 'General', 'file_logging_db', 0)):
        FILE_LOGGING_PRESET = 'DB'
    elif 'DB' == FILE_LOGGING_PRESET:
        FILE_LOGGING_PRESET = 'DEBUG'

    SOCKET_TIMEOUT = check_setting_int(CFG, 'General', 'socket_timeout', 30)
    socket.setdefaulttimeout(SOCKET_TIMEOUT)

    WEB_HOST = check_setting_str(CFG, 'General', 'web_host', '0.0.0.0')
    WEB_PORT = minimax(check_setting_int(CFG, 'General', 'web_port', 8081), 8081, 21, 65535)
    WEB_ROOT = check_setting_str(CFG, 'General', 'web_root', '').rstrip('/')
    WEB_IPV6 = bool(check_setting_int(CFG, 'General', 'web_ipv6', 0))
    WEB_IPV64 = bool(check_setting_int(CFG, 'General', 'web_ipv64', 0))
    WEB_LOG = bool(check_setting_int(CFG, 'General', 'web_log', 0))
    ENCRYPTION_VERSION = check_setting_int(CFG, 'General', 'encryption_version', 0)
    WEB_USERNAME = check_setting_str(CFG, 'General', 'web_username', '')
    WEB_PASSWORD = check_setting_str(CFG, 'General', 'web_password', '')
    LAUNCH_BROWSER = bool(check_setting_int(CFG, 'General', 'launch_browser', 1))

    CPU_PRESET = check_setting_str(CFG, 'General', 'cpu_preset', 'DISABLED')

    ANON_REDIRECT = check_setting_str(CFG, 'General', 'anon_redirect', '')
    PROXY_SETTING = check_setting_str(CFG, 'General', 'proxy_setting', '')
    sg_helpers.PROXY_SETTING = PROXY_SETTING
    sg_helpers.USER_AGENT = USER_AGENT
    from . import notifiers
    sg_helpers.NOTIFIERS = notifiers
    PROXY_INDEXERS = bool(check_setting_int(CFG, 'General', 'proxy_indexers', 1))
    # attempt to help prevent users from breaking links by using a bad url
    if not ANON_REDIRECT.endswith('?'):
        ANON_REDIRECT = ''

    UPDATE_SHOWS_ON_START = bool(check_setting_int(CFG, 'General', 'update_shows_on_start', 0))
    SHOW_UPDATE_HOUR = check_setting_int(CFG, 'General', 'show_update_hour', 3)
    SHOW_UPDATE_HOUR = minimax(SHOW_UPDATE_HOUR, 3, 0, 23)

    TRASH_REMOVE_SHOW = bool(check_setting_int(CFG, 'General', 'trash_remove_show', 0))
    sg_helpers.TRASH_REMOVE_SHOW = TRASH_REMOVE_SHOW
    TRASH_ROTATE_LOGS = bool(check_setting_int(CFG, 'General', 'trash_rotate_logs', 0))

    USE_API = bool(check_setting_int(CFG, 'General', 'use_api', 0))
    API_KEYS = [k.split(':::') for k in check_setting_str(CFG, 'General', 'api_keys', '').split('|||') if k]
    if not API_KEYS:
        tmp_api_key = check_setting_str(CFG, 'General', 'api_key', None)
        if None is not tmp_api_key:
            API_KEYS = [['app name (old key)', tmp_api_key]]

    DEBUG = bool(check_setting_int(CFG, 'General', 'debug', 0))

    ENABLE_HTTPS = bool(check_setting_int(CFG, 'General', 'enable_https', 0))

    HTTPS_CERT = check_setting_str(CFG, 'General', 'https_cert', 'server.crt')
    HTTPS_KEY = check_setting_str(CFG, 'General', 'https_key', 'server.key')

    HANDLE_REVERSE_PROXY = bool(check_setting_int(CFG, 'General', 'handle_reverse_proxy', 0))
    SEND_SECURITY_HEADERS = bool(check_setting_int(CFG, 'General', 'send_security_headers', 1))
    ALLOWED_HOSTS = check_setting_str(CFG, 'General', 'allowed_hosts', '')
    ALLOW_ANYIP = bool(check_setting_int(CFG, 'General', 'allow_anyip', 1))

    ROOT_DIRS = check_setting_str(CFG, 'General', 'root_dirs', '')
    if not re.match(r'\d+\|[^|]+(?:\|[^|]+)*', ROOT_DIRS):
        ROOT_DIRS = ''

    RESULTS_SORTBY = check_setting_str(CFG, 'General', 'results_sortby', '')

    QUALITY_DEFAULT = check_setting_int(CFG, 'General', 'quality_default', SD)
    STATUS_DEFAULT = check_setting_int(CFG, 'General', 'status_default', SKIPPED)
    WANTED_BEGIN_DEFAULT = check_setting_int(CFG, 'General', 'wanted_begin_default', 0)
    WANTED_LATEST_DEFAULT = check_setting_int(CFG, 'General', 'wanted_latest_default', 0)

    UPDATE_NOTIFY = bool(check_setting_int(CFG, 'General', 'update_notify', None))
    if None is UPDATE_NOTIFY:
        UPDATE_NOTIFY = check_setting_int(CFG, 'General', 'version_notify', 1)  # deprecated 2020.11.21 no config update
    UPDATE_AUTO = bool(check_setting_int(CFG, 'General', 'update_auto', None))
    if None is UPDATE_AUTO:
        UPDATE_AUTO = check_setting_int(CFG, 'General', 'auto_update', 0)  # deprecated 2020.11.21 no config update
    UPDATE_INTERVAL = max(
        MIN_UPDATE_INTERVAL,
        check_setting_int(CFG, 'General', 'update_interval', DEFAULT_UPDATE_INTERVAL))
    NOTIFY_ON_UPDATE = bool(check_setting_int(CFG, 'General', 'notify_on_update', 1))

    UPDATE_PACKAGES_NOTIFY = bool(
        check_setting_int(CFG, 'General', 'update_packages_notify', 'win' == sys.platform[0:3]))
    UPDATE_PACKAGES_AUTO = bool(check_setting_int(CFG, 'General', 'update_packages_auto', 0))
    UPDATE_PACKAGES_MENU = bool(check_setting_int(CFG, 'General', 'update_packages_menu', 0))
    UPDATE_PACKAGES_INTERVAL = max(
        MIN_UPDATE_PACKAGES_INTERVAL,
        check_setting_int(CFG, 'General', 'update_packages_interval', DEFAULT_UPDATE_PACKAGES_INTERVAL))

    TVINFO_DEFAULT = check_setting_int(CFG, 'General', 'indexer_default', 0)
    if TVINFO_DEFAULT and not TVInfoAPI(TVINFO_DEFAULT).config['active']:
        TVINFO_DEFAULT = TVINFO_TVDB
    TVINFO_TIMEOUT = check_setting_int(CFG, 'General', 'indexer_timeout', 20)

    PAUSE_DEFAULT = bool(check_setting_int(CFG, 'General', 'pause default', 0))
    SCENE_DEFAULT = bool(check_setting_int(CFG, 'General', 'scene_default', 0))
    FLATTEN_FOLDERS_DEFAULT = bool(check_setting_int(CFG, 'General', 'flatten_folders_default', 0))
    ANIME_DEFAULT = bool(check_setting_int(CFG, 'General', 'anime_default', 0))

    PROVIDER_ORDER = check_setting_str(CFG, 'General', 'provider_order', '').split()
    PROVIDER_HOMES = sg_helpers.ast_eval(check_setting_str(CFG, 'General', 'provider_homes', None), {})

    NAMING_PATTERN = check_setting_str(CFG, 'General', 'naming_pattern', 'Season %0S/%SN - S%0SE%0E - %EN')
    NAMING_ABD_PATTERN = check_setting_str(CFG, 'General', 'naming_abd_pattern', '%SN - %A.D - %EN')
    NAMING_CUSTOM_ABD = bool(check_setting_int(CFG, 'General', 'naming_custom_abd', 0))
    NAMING_SPORTS_PATTERN = check_setting_str(CFG, 'General', 'naming_sports_pattern', '%SN - %A-D - %EN')
    NAMING_ANIME_PATTERN = check_setting_str(CFG, 'General', 'naming_anime_pattern',
                                             'Season %0S/%SN - S%0SE%0E - %EN')
    NAMING_ANIME = check_setting_int(CFG, 'General', 'naming_anime', 3)
    NAMING_CUSTOM_SPORTS = bool(check_setting_int(CFG, 'General', 'naming_custom_sports', 0))
    NAMING_CUSTOM_ANIME = bool(check_setting_int(CFG, 'General', 'naming_custom_anime', 0))
    NAMING_MULTI_EP = check_setting_int(CFG, 'General', 'naming_multi_ep', 1)
    NAMING_ANIME_MULTI_EP = check_setting_int(CFG, 'General', 'naming_anime_multi_ep', 1)
    NAMING_FORCE_FOLDERS = naming.check_force_season_folders()
    NAMING_STRIP_YEAR = bool(check_setting_int(CFG, 'General', 'naming_strip_year', 0))

    USE_NZBS = bool(check_setting_int(CFG, 'General', 'use_nzbs', 0))
    USE_TORRENTS = bool(check_setting_int(CFG, 'General', 'use_torrents', 0))

    NZB_METHOD = check_setting_str(CFG, 'General', 'nzb_method', 'blackhole')
    if NZB_METHOD not in ('blackhole', 'sabnzbd', 'nzbget'):
        NZB_METHOD = 'blackhole'

    TORRENT_METHOD = check_setting_str(CFG, 'General', 'torrent_method', 'blackhole')
    if TORRENT_METHOD not in ('blackhole', 'deluge', 'download_station', 'qbittorrent',
                              'rtorrent', 'transmission', 'utorrent'):
        TORRENT_METHOD = 'blackhole'

    DOWNLOAD_PROPERS = bool(check_setting_int(CFG, 'General', 'download_propers', 1))
    PROPERS_WEBDL_ONEGRP = bool(check_setting_int(CFG, 'General', 'propers_webdl_onegrp', 1))

    ALLOW_HIGH_PRIORITY = bool(check_setting_int(CFG, 'General', 'allow_high_priority', 1))

    RECENTSEARCH_STARTUP = bool(check_setting_int(CFG, 'General', 'recentsearch_startup', 0))
    BACKLOG_NOFULL = bool(check_setting_int(CFG, 'General', 'backlog_nofull', 0))
    SKIP_REMOVED_FILES = check_setting_int(CFG, 'General', 'skip_removed_files', 0)

    USENET_RETENTION = check_setting_int(CFG, 'General', 'usenet_retention', 500)

    MEDIAPROCESS_INTERVAL = check_setting_int(CFG, 'General', 'mediaprocess_interval', DEFAULT_MEDIAPROCESS_INTERVAL)
    if MEDIAPROCESS_INTERVAL < MIN_MEDIAPROCESS_INTERVAL:
        MEDIAPROCESS_INTERVAL = MIN_MEDIAPROCESS_INTERVAL

    RECENTSEARCH_INTERVAL = check_setting_int(CFG, 'General', 'recentsearch_interval', DEFAULT_RECENTSEARCH_INTERVAL)
    if RECENTSEARCH_INTERVAL < MIN_RECENTSEARCH_INTERVAL:
        RECENTSEARCH_INTERVAL = MIN_RECENTSEARCH_INTERVAL

    # special case during dev to migrate backlog_interval to backlog_period
    BACKLOG_PERIOD = check_setting_int(CFG, 'General', 'backlog_period',
                                       check_setting_int(CFG, 'General', 'backlog_interval', DEFAULT_BACKLOG_PERIOD))
    BACKLOG_PERIOD = minimax(BACKLOG_PERIOD, DEFAULT_BACKLOG_PERIOD, MIN_BACKLOG_PERIOD, MAX_BACKLOG_PERIOD)
    BACKLOG_LIMITED_PERIOD = check_setting_int(CFG, 'General', 'backlog_limited_period', 7)

    SEARCH_UNAIRED = bool(check_setting_int(CFG, 'General', 'search_unaired', 0))
    UNAIRED_RECENT_SEARCH_ONLY = bool(check_setting_int(CFG, 'General', 'unaired_recent_search_only', 1))
    FLARESOLVERR_HOST = check_setting_str(CFG, 'General', 'flaresolverr_host', '')
    sg_helpers.FLARESOLVERR_HOST = FLARESOLVERR_HOST

    NZB_DIR = check_setting_str(CFG, 'Blackhole', 'nzb_dir', '')
    TORRENT_DIR = check_setting_str(CFG, 'Blackhole', 'torrent_dir', '')

    TV_DOWNLOAD_DIR = check_setting_str(CFG, 'General', 'tv_download_dir', '')
    PROCESS_AUTOMATICALLY = bool(check_setting_int(CFG, 'General', 'process_automatically', 0))
    UNPACK = bool(check_setting_int(CFG, 'General', 'unpack', 0))
    RENAME_EPISODES = bool(check_setting_int(CFG, 'General', 'rename_episodes', 1))
    RENAME_TBA_EPISODES = bool(check_setting_int(CFG, 'General', 'rename_tba_episodes', 1))
    RENAME_NAME_CHANGED_EPISODES = bool(check_setting_int(CFG, 'General', 'rename_name_changed_episodes', 0))
    AIRDATE_EPISODES = bool(check_setting_int(CFG, 'General', 'airdate_episodes', 0))
    KEEP_PROCESSED_DIR = bool(check_setting_int(CFG, 'General', 'keep_processed_dir', 1))
    PROCESS_METHOD = check_setting_str(CFG, 'General', 'process_method', 'copy' if KEEP_PROCESSED_DIR else 'move')
    PROCESS_LAST_DIR = check_setting_str(CFG, 'General', 'process_last_dir', TV_DOWNLOAD_DIR)
    PROCESS_LAST_METHOD = check_setting_str(CFG, 'General', 'process_last_method', PROCESS_METHOD)
    PROCESS_LAST_CLEANUP = bool(check_setting_int(CFG, 'General', 'process_last_cleanup', 0))
    MOVE_ASSOCIATED_FILES = bool(check_setting_int(CFG, 'General', 'move_associated_files', 0))
    POSTPONE_IF_SYNC_FILES = bool(check_setting_int(CFG, 'General', 'postpone_if_sync_files', 1))
    PROCESS_POSITIVE_LOG = bool(check_setting_int(CFG, 'General', 'process_positive_log', 0))
    NFO_RENAME = bool(check_setting_int(CFG, 'General', 'nfo_rename', 1))
    CREATE_MISSING_SHOW_DIRS = bool(check_setting_int(CFG, 'General', 'create_missing_show_dirs', 0))
    SHOW_DIRS_WITH_DOTS = bool(check_setting_int(CFG, 'General', 'show_dirs_with_dots', 0))
    ADD_SHOWS_WO_DIR = bool(check_setting_int(CFG, 'General', 'add_shows_wo_dir', 0))
    ADD_SHOWS_METALANG = check_setting_str(CFG, 'General', 'add_shows_metalang', 'en')
    REMOVE_FILENAME_CHARS = check_setting_str(CFG, 'General', 'remove_filename_chars', '')
    sg_helpers.REMOVE_FILENAME_CHARS = REMOVE_FILENAME_CHARS
    IMPORT_DEFAULT_CHECKED_SHOWS = bool(check_setting_int(CFG, 'General', 'import_default_checked_shows', 0))

    SAB_USERNAME = check_setting_str(CFG, 'SABnzbd', 'sab_username', '')
    SAB_PASSWORD = check_setting_str(CFG, 'SABnzbd', 'sab_password', '')
    SAB_APIKEY = check_setting_str(CFG, 'SABnzbd', 'sab_apikey', '')
    SAB_CATEGORY = check_setting_str(CFG, 'SABnzbd', 'sab_category', 'tv')
    SAB_HOST = check_setting_str(CFG, 'SABnzbd', 'sab_host', '')

    # first check using official name case, then with case of legacy
    # todo: migrate config, (just not atm due to testing map feature)
    NZBGET_USERNAME = (check_setting_str(CFG, 'NZBGet', 'nzbget_username', '')
                       or check_setting_str(CFG, 'NZBget', 'nzbget_username', 'nzbget'))
    NZBGET_PASSWORD = (check_setting_str(CFG, 'NZBGet', 'nzbget_password', '')
                       or check_setting_str(CFG, 'NZBget', 'nzbget_password', 'tegbzn6789'))
    NZBGET_CATEGORY = (check_setting_str(CFG, 'NZBGet', 'nzbget_category', '')
                       or check_setting_str(CFG, 'NZBget', 'nzbget_category', 'tv'))
    NZBGET_HOST = (check_setting_str(CFG, 'NZBGet', 'nzbget_host', '')
                   or check_setting_str(CFG, 'NZBget', 'nzbget_host', ''))
    NZBGET_USE_HTTPS = (bool(check_setting_int(CFG, 'NZBGet', 'nzbget_use_https', 0))
                        or bool(check_setting_int(CFG, 'NZBget', 'nzbget_use_https', 0)))
    NZBGET_PRIORITY = check_setting_int(CFG, 'NZBGet', 'nzbget_priority', None)
    if None is NZBGET_PRIORITY:
        NZBGET_PRIORITY = check_setting_int(CFG, 'NZBget', 'nzbget_priority', 100)
    NZBGET_MAP = check_setting_str(CFG, 'NZBGet', 'nzbget_map', '')
    NZBGET_SKIP_PM = bool(check_setting_int(CFG, 'NZBGet', 'nzbget_skip_process_media', 0))

    try:
        ng_script_file = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                      'autoProcessTV', 'SickGear-NG', 'SickGear-NG.py')
        with io.open(ng_script_file, 'r', encoding='utf8') as ng:
            text = ng.read()
        NZBGET_SCRIPT_VERSION = re.search(r""".*version: (\d+\.\d+)""", text, flags=re.M).group(1)
    except (BaseException, Exception):
        NZBGET_SCRIPT_VERSION = None

    TORRENT_USERNAME = check_setting_str(CFG, 'TORRENT', 'torrent_username', '')
    TORRENT_PASSWORD = check_setting_str(CFG, 'TORRENT', 'torrent_password', '')
    TORRENT_HOST = check_setting_str(CFG, 'TORRENT', 'torrent_host', '')
    TORRENT_PATH = check_setting_str(CFG, 'TORRENT', 'torrent_path', '')
    TORRENT_SEED_TIME = check_setting_int(CFG, 'TORRENT', 'torrent_seed_time', 0)
    TORRENT_PAUSED = bool(check_setting_int(CFG, 'TORRENT', 'torrent_paused', 0))
    TORRENT_HIGH_BANDWIDTH = bool(check_setting_int(CFG, 'TORRENT', 'torrent_high_bandwidth', 0))
    TORRENT_LABEL = check_setting_str(CFG, 'TORRENT', 'torrent_label', '')
    TORRENT_LABEL_VAR = check_setting_int(CFG, 'TORRENT', 'torrent_label_var', 1)
    TORRENT_VERIFY_CERT = bool(check_setting_int(CFG, 'TORRENT', 'torrent_verify_cert', 0))

    USE_EMBY = bool(check_setting_int(CFG, 'Emby', 'use_emby', 0))
    EMBY_UPDATE_LIBRARY = bool(check_setting_int(CFG, 'Emby', 'emby_update_library', 0))
    EMBY_PARENT_MAPS = check_setting_str(CFG, 'Emby', 'emby_parent_maps', '')
    EMBY_HOST = check_setting_str(CFG, 'Emby', 'emby_host', '')
    EMBY_APIKEY = check_setting_str(CFG, 'Emby', 'emby_apikey', '')
    EMBY_WATCHEDSTATE_SCHEDULED = bool(check_setting_int(CFG, 'Emby', 'emby_watchedstate_scheduled', 0))
    EMBY_WATCHEDSTATE_INTERVAL = minimax(check_setting_int(
        CFG, 'Emby', 'emby_watchedstate_interval', DEFAULT_WATCHEDSTATE_INTERVAL),
        DEFAULT_WATCHEDSTATE_INTERVAL, MIN_WATCHEDSTATE_INTERVAL, MAX_WATCHEDSTATE_INTERVAL)

    USE_KODI = bool(check_setting_int(CFG, 'Kodi', 'use_kodi', 0))
    KODI_ALWAYS_ON = bool(check_setting_int(CFG, 'Kodi', 'kodi_always_on', 1))
    KODI_NOTIFY_ONSNATCH = bool(check_setting_int(CFG, 'Kodi', 'kodi_notify_onsnatch', 0))
    KODI_NOTIFY_ONDOWNLOAD = bool(check_setting_int(CFG, 'Kodi', 'kodi_notify_ondownload', 0))
    KODI_NOTIFY_ONSUBTITLEDOWNLOAD = bool(check_setting_int(CFG, 'Kodi', 'kodi_notify_onsubtitledownload', 0))
    KODI_UPDATE_LIBRARY = bool(check_setting_int(CFG, 'Kodi', 'kodi_update_library', 0))
    KODI_UPDATE_FULL = bool(check_setting_int(CFG, 'Kodi', 'kodi_update_full', 0))
    KODI_UPDATE_ONLYFIRST = bool(check_setting_int(CFG, 'Kodi', 'kodi_update_onlyfirst', 0))
    KODI_PARENT_MAPS = check_setting_str(CFG, 'Kodi', 'kodi_parent_maps', '')
    KODI_HOST = check_setting_str(CFG, 'Kodi', 'kodi_host', '')
    KODI_USERNAME = check_setting_str(CFG, 'Kodi', 'kodi_username', '')
    KODI_PASSWORD = check_setting_str(CFG, 'Kodi', 'kodi_password', '')

    USE_XBMC = bool(check_setting_int(CFG, 'XBMC', 'use_xbmc', 0))
    XBMC_ALWAYS_ON = bool(check_setting_int(CFG, 'XBMC', 'xbmc_always_on', 1))
    XBMC_NOTIFY_ONSNATCH = bool(check_setting_int(CFG, 'XBMC', 'xbmc_notify_onsnatch', 0))
    XBMC_NOTIFY_ONDOWNLOAD = bool(check_setting_int(CFG, 'XBMC', 'xbmc_notify_ondownload', 0))
    XBMC_NOTIFY_ONSUBTITLEDOWNLOAD = bool(check_setting_int(CFG, 'XBMC', 'xbmc_notify_onsubtitledownload', 0))
    XBMC_UPDATE_LIBRARY = bool(check_setting_int(CFG, 'XBMC', 'xbmc_update_library', 0))
    XBMC_UPDATE_FULL = bool(check_setting_int(CFG, 'XBMC', 'xbmc_update_full', 0))
    XBMC_UPDATE_ONLYFIRST = bool(check_setting_int(CFG, 'XBMC', 'xbmc_update_onlyfirst', 0))
    XBMC_HOST = check_setting_str(CFG, 'XBMC', 'xbmc_host', '')
    XBMC_USERNAME = check_setting_str(CFG, 'XBMC', 'xbmc_username', '')
    XBMC_PASSWORD = check_setting_str(CFG, 'XBMC', 'xbmc_password', '')

    USE_PLEX = bool(check_setting_int(CFG, 'Plex', 'use_plex', 0))
    PLEX_NOTIFY_ONSNATCH = bool(check_setting_int(CFG, 'Plex', 'plex_notify_onsnatch', 0))
    PLEX_NOTIFY_ONDOWNLOAD = bool(check_setting_int(CFG, 'Plex', 'plex_notify_ondownload', 0))
    PLEX_NOTIFY_ONSUBTITLEDOWNLOAD = bool(check_setting_int(CFG, 'Plex', 'plex_notify_onsubtitledownload', 0))
    PLEX_UPDATE_LIBRARY = bool(check_setting_int(CFG, 'Plex', 'plex_update_library', 0))
    PLEX_PARENT_MAPS = check_setting_str(CFG, 'Plex', 'plex_parent_maps', '')
    PLEX_SERVER_HOST = check_setting_str(CFG, 'Plex', 'plex_server_host', '')
    PLEX_HOST = check_setting_str(CFG, 'Plex', 'plex_host', '')
    PLEX_USERNAME = check_setting_str(CFG, 'Plex', 'plex_username', '')
    PLEX_PASSWORD = check_setting_str(CFG, 'Plex', 'plex_password', '')
    PLEX_WATCHEDSTATE_SCHEDULED = bool(check_setting_int(CFG, 'Plex', 'plex_watchedstate_scheduled', 0))
    PLEX_WATCHEDSTATE_INTERVAL = minimax(check_setting_int(
        CFG, 'Plex', 'plex_watchedstate_interval', DEFAULT_WATCHEDSTATE_INTERVAL),
        DEFAULT_WATCHEDSTATE_INTERVAL, MIN_WATCHEDSTATE_INTERVAL, MAX_WATCHEDSTATE_INTERVAL)

    USE_GROWL = bool(check_setting_int(CFG, 'Growl', 'use_growl', 0))
    GROWL_NOTIFY_ONSNATCH = bool(check_setting_int(CFG, 'Growl', 'growl_notify_onsnatch', 0))
    GROWL_NOTIFY_ONDOWNLOAD = bool(check_setting_int(CFG, 'Growl', 'growl_notify_ondownload', 0))
    GROWL_NOTIFY_ONSUBTITLEDOWNLOAD = bool(check_setting_int(CFG, 'Growl', 'growl_notify_onsubtitledownload', 0))
    GROWL_HOST = check_setting_str(CFG, 'Growl', 'growl_host', '')
    # GROWL_PASSWORD = check_setting_str(CFG, 'Growl', 'growl_password', '')

    USE_PROWL = bool(check_setting_int(CFG, 'Prowl', 'use_prowl', 0))
    PROWL_NOTIFY_ONSNATCH = bool(check_setting_int(CFG, 'Prowl', 'prowl_notify_onsnatch', 0))
    PROWL_NOTIFY_ONDOWNLOAD = bool(check_setting_int(CFG, 'Prowl', 'prowl_notify_ondownload', 0))
    PROWL_NOTIFY_ONSUBTITLEDOWNLOAD = bool(check_setting_int(CFG, 'Prowl', 'prowl_notify_onsubtitledownload', 0))
    PROWL_API = check_setting_str(CFG, 'Prowl', 'prowl_api', '')
    PROWL_PRIORITY = check_setting_str(CFG, 'Prowl', 'prowl_priority', '0')

    USE_BOXCAR2 = bool(check_setting_int(CFG, 'Boxcar2', 'use_boxcar2', 0))
    BOXCAR2_NOTIFY_ONSNATCH = bool(check_setting_int(CFG, 'Boxcar2', 'boxcar2_notify_onsnatch', 0))
    BOXCAR2_NOTIFY_ONDOWNLOAD = bool(check_setting_int(CFG, 'Boxcar2', 'boxcar2_notify_ondownload', 0))
    BOXCAR2_NOTIFY_ONSUBTITLEDOWNLOAD = bool(
        check_setting_int(CFG, 'Boxcar2', 'boxcar2_notify_onsubtitledownload', 0))
    BOXCAR2_ACCESSTOKEN = check_setting_str(CFG, 'Boxcar2', 'boxcar2_accesstoken', '')
    BOXCAR2_SOUND = check_setting_str(CFG, 'Boxcar2', 'boxcar2_sound', 'default')

    USE_PUSHOVER = bool(check_setting_int(CFG, 'Pushover', 'use_pushover', 0))
    PUSHOVER_NOTIFY_ONSNATCH = bool(check_setting_int(CFG, 'Pushover', 'pushover_notify_onsnatch', 0))
    PUSHOVER_NOTIFY_ONDOWNLOAD = bool(check_setting_int(CFG, 'Pushover', 'pushover_notify_ondownload', 0))
    PUSHOVER_NOTIFY_ONSUBTITLEDOWNLOAD = bool(
        check_setting_int(CFG, 'Pushover', 'pushover_notify_onsubtitledownload', 0))
    PUSHOVER_USERKEY = check_setting_str(CFG, 'Pushover', 'pushover_userkey', '')
    PUSHOVER_APIKEY = check_setting_str(CFG, 'Pushover', 'pushover_apikey', '')
    PUSHOVER_PRIORITY = check_setting_str(CFG, 'Pushover', 'pushover_priority', '0')
    PUSHOVER_DEVICE = check_setting_str(CFG, 'Pushover', 'pushover_device', 'all')
    PUSHOVER_SOUND = check_setting_str(CFG, 'Pushover', 'pushover_sound', 'pushover')

    USE_LIBNOTIFY = bool(check_setting_int(CFG, 'Libnotify', 'use_libnotify', 0))
    LIBNOTIFY_NOTIFY_ONSNATCH = bool(check_setting_int(CFG, 'Libnotify', 'libnotify_notify_onsnatch', 0))
    LIBNOTIFY_NOTIFY_ONDOWNLOAD = bool(check_setting_int(CFG, 'Libnotify', 'libnotify_notify_ondownload', 0))
    LIBNOTIFY_NOTIFY_ONSUBTITLEDOWNLOAD = bool(
        check_setting_int(CFG, 'Libnotify', 'libnotify_notify_onsubtitledownload', 0))

    USE_NMJ = bool(check_setting_int(CFG, 'NMJ', 'use_nmj', 0))
    NMJ_HOST = check_setting_str(CFG, 'NMJ', 'nmj_host', '')
    NMJ_DATABASE = check_setting_str(CFG, 'NMJ', 'nmj_database', '')
    NMJ_MOUNT = check_setting_str(CFG, 'NMJ', 'nmj_mount', '')

    USE_NMJv2 = bool(check_setting_int(CFG, 'NMJv2', 'use_nmjv2', 0))
    NMJv2_HOST = check_setting_str(CFG, 'NMJv2', 'nmjv2_host', '')
    NMJv2_DATABASE = check_setting_str(CFG, 'NMJv2', 'nmjv2_database', '')
    NMJv2_DBLOC = check_setting_str(CFG, 'NMJv2', 'nmjv2_dbloc', '')

    USE_SYNOINDEX = bool(check_setting_int(CFG, 'Synology', 'use_synoindex', 0))

    USE_SYNOLOGYNOTIFIER = bool(check_setting_int(CFG, 'SynologyNotifier', 'use_synologynotifier', 0))
    SYNOLOGYNOTIFIER_NOTIFY_ONSNATCH = bool(
        check_setting_int(CFG, 'SynologyNotifier', 'synologynotifier_notify_onsnatch', 0))
    SYNOLOGYNOTIFIER_NOTIFY_ONDOWNLOAD = bool(
        check_setting_int(CFG, 'SynologyNotifier', 'synologynotifier_notify_ondownload', 0))
    SYNOLOGYNOTIFIER_NOTIFY_ONSUBTITLEDOWNLOAD = bool(
        check_setting_int(CFG, 'SynologyNotifier', 'synologynotifier_notify_onsubtitledownload', 0))

    USE_TRAKT = bool(check_setting_int(CFG, 'Trakt', 'use_trakt', 0))
    TRAKT_REMOVE_WATCHLIST = bool(check_setting_int(CFG, 'Trakt', 'trakt_remove_watchlist', 0))
    TRAKT_REMOVE_SERIESLIST = bool(check_setting_int(CFG, 'Trakt', 'trakt_remove_serieslist', 0))
    TRAKT_USE_WATCHLIST = bool(check_setting_int(CFG, 'Trakt', 'trakt_use_watchlist', 0))
    TRAKT_METHOD_ADD = check_setting_int(CFG, 'Trakt', 'trakt_method_add', 0)
    TRAKT_START_PAUSED = bool(check_setting_int(CFG, 'Trakt', 'trakt_start_paused', 0))
    TRAKT_SYNC = bool(check_setting_int(CFG, 'Trakt', 'trakt_sync', 0))
    TRAKT_DEFAULT_INDEXER = check_setting_int(CFG, 'Trakt', 'trakt_default_indexer', 1)
    TRAKT_UPDATE_COLLECTION = trakt_helpers.read_config_string(
        check_setting_str(CFG, 'Trakt', 'trakt_update_collection', ''))
    TRAKT_ACCOUNTS = TraktAPI.read_config_string(check_setting_str(CFG, 'Trakt', 'trakt_accounts', ''))
    TRAKT_MRU = check_setting_str(CFG, 'Trakt', 'trakt_mru', '')

    MC_MRU = check_setting_str(CFG, 'Metacritic', 'mc_mru', '')
    NE_MRU = check_setting_str(CFG, 'NextEpisode', 'ne_mru', '')
    TMDB_MRU = check_setting_str(CFG, 'TMDB', 'tmdb_mru', '')
    TVC_MRU = check_setting_str(CFG, 'TVCalendar', 'tvc_mru', '')
    TVDB_MRU = check_setting_str(CFG, 'TVDb', 'tvdb_mru', '')
    TVM_MRU = check_setting_str(CFG, 'TVmaze', 'tvm_mru', '')

    USE_PYTIVO = bool(check_setting_int(CFG, 'pyTivo', 'use_pytivo', 0))
    PYTIVO_HOST = check_setting_str(CFG, 'pyTivo', 'pytivo_host', '')
    PYTIVO_SHARE_NAME = check_setting_str(CFG, 'pyTivo', 'pytivo_share_name', '')
    PYTIVO_TIVO_NAME = check_setting_str(CFG, 'pyTivo', 'pytivo_tivo_name', '')

    USE_PUSHALOT = bool(check_setting_int(CFG, 'Pushalot', 'use_pushalot', 0))
    PUSHALOT_NOTIFY_ONSNATCH = bool(check_setting_int(CFG, 'Pushalot', 'pushalot_notify_onsnatch', 0))
    PUSHALOT_NOTIFY_ONDOWNLOAD = bool(check_setting_int(CFG, 'Pushalot', 'pushalot_notify_ondownload', 0))
    PUSHALOT_NOTIFY_ONSUBTITLEDOWNLOAD = bool(
        check_setting_int(CFG, 'Pushalot', 'pushalot_notify_onsubtitledownload', 0))
    PUSHALOT_AUTHORIZATIONTOKEN = check_setting_str(CFG, 'Pushalot', 'pushalot_authorizationtoken', '')

    USE_PUSHBULLET = bool(check_setting_int(CFG, 'Pushbullet', 'use_pushbullet', 0))
    PUSHBULLET_NOTIFY_ONSNATCH = bool(check_setting_int(CFG, 'Pushbullet', 'pushbullet_notify_onsnatch', 0))
    PUSHBULLET_NOTIFY_ONDOWNLOAD = bool(check_setting_int(CFG, 'Pushbullet', 'pushbullet_notify_ondownload', 0))
    PUSHBULLET_NOTIFY_ONSUBTITLEDOWNLOAD = bool(
        check_setting_int(CFG, 'Pushbullet', 'pushbullet_notify_onsubtitledownload', 0))
    PUSHBULLET_ACCESS_TOKEN = check_setting_str(CFG, 'Pushbullet', 'pushbullet_access_token', '')
    PUSHBULLET_DEVICE_IDEN = check_setting_str(CFG, 'Pushbullet', 'pushbullet_device_iden', '')

    USE_SLACK = bool(check_setting_int(CFG, 'Slack', 'use_slack', 0))
    SLACK_NOTIFY_ONSNATCH = bool(check_setting_int(CFG, 'Slack', 'slack_notify_onsnatch', 0))
    SLACK_NOTIFY_ONDOWNLOAD = bool(check_setting_int(CFG, 'Slack', 'slack_notify_ondownload', 0))
    SLACK_NOTIFY_ONSUBTITLEDOWNLOAD = bool(check_setting_int(CFG, 'Slack', 'slack_notify_onsubtitledownload', 0))
    SLACK_CHANNEL = check_setting_str(CFG, 'Slack', 'slack_channel', '')
    SLACK_AS_AUTHED = bool(check_setting_int(CFG, 'Slack', 'slack_as_authed', 0))
    SLACK_BOT_NAME = check_setting_str(CFG, 'Slack', 'slack_bot_name', '')
    SLACK_ICON_URL = check_setting_str(CFG, 'Slack', 'slack_icon_url', '')
    SLACK_ACCESS_TOKEN = check_setting_str(CFG, 'Slack', 'slack_access_token', '')

    USE_DISCORD = bool(check_setting_int(CFG, 'Discord', 'use_discord', 0))
    DISCORD_NOTIFY_ONSNATCH = bool(check_setting_int(CFG, 'Discord', 'discord_notify_onsnatch', 0))
    DISCORD_NOTIFY_ONDOWNLOAD = bool(check_setting_int(CFG, 'Discord', 'discord_notify_ondownload', 0))
    DISCORD_NOTIFY_ONSUBTITLEDOWNLOAD = bool(
        check_setting_int(CFG, 'Discord', 'discord_notify_onsubtitledownload', 0))
    DISCORD_AS_AUTHED = bool(check_setting_int(CFG, 'Discord', 'discord_as_authed', 0))
    DISCORD_USERNAME = check_setting_str(CFG, 'Discord', 'discord_username', '')
    DISCORD_ICON_URL = check_setting_str(CFG, 'Discord', 'discord_icon_url', '')
    DISCORD_AS_TTS = bool(check_setting_str(CFG, 'Discord', 'discord_as_tts', 0))
    DISCORD_ACCESS_TOKEN = check_setting_str(CFG, 'Discord', 'discord_access_token', '')

    USE_GITTER = bool(check_setting_int(CFG, 'Gitter', 'use_gitter', 0))
    GITTER_NOTIFY_ONSNATCH = bool(check_setting_int(CFG, 'Gitter', 'gitter_notify_onsnatch', 0))
    GITTER_NOTIFY_ONDOWNLOAD = bool(check_setting_int(CFG, 'Gitter', 'gitter_notify_ondownload', 0))
    GITTER_NOTIFY_ONSUBTITLEDOWNLOAD = bool(check_setting_int(CFG, 'Gitter', 'gitter_notify_onsubtitledownload', 0))
    GITTER_ROOM = check_setting_str(CFG, 'Gitter', 'gitter_room', '')
    GITTER_ACCESS_TOKEN = check_setting_str(CFG, 'Gitter', 'gitter_access_token', '')

    USE_TELEGRAM = bool(check_setting_int(CFG, 'Telegram', 'use_telegram', 0))
    TELEGRAM_NOTIFY_ONSNATCH = bool(check_setting_int(CFG, 'Telegram', 'telegram_notify_onsnatch', 0))
    TELEGRAM_NOTIFY_ONDOWNLOAD = bool(check_setting_int(CFG, 'Telegram', 'telegram_notify_ondownload', 0))
    TELEGRAM_NOTIFY_ONSUBTITLEDOWNLOAD = bool(check_setting_int(
        CFG, 'Telegram', 'telegram_notify_onsubtitledownload', 0))
    TELEGRAM_SEND_IMAGE = bool(check_setting_int(CFG, 'Telegram', 'telegram_send_image', 1))
    TELEGRAM_QUIET = bool(check_setting_int(CFG, 'Telegram', 'telegram_quiet', 0))
    TELEGRAM_ACCESS_TOKEN = check_setting_str(CFG, 'Telegram', 'telegram_access_token', '')
    TELEGRAM_CHATID = check_setting_str(CFG, 'Telegram', 'telegram_chatid', '')

    USE_EMAIL = bool(check_setting_int(CFG, 'Email', 'use_email', 0))
    EMAIL_OLD_SUBJECTS = bool(check_setting_int(CFG, 'Email', 'email_old_subjects',
                                                None is not EMAIL_HOST and any(EMAIL_HOST)))
    EMAIL_NOTIFY_ONSNATCH = bool(check_setting_int(CFG, 'Email', 'email_notify_onsnatch', 0))
    EMAIL_NOTIFY_ONDOWNLOAD = bool(check_setting_int(CFG, 'Email', 'email_notify_ondownload', 0))
    EMAIL_NOTIFY_ONSUBTITLEDOWNLOAD = bool(check_setting_int(CFG, 'Email', 'email_notify_onsubtitledownload', 0))
    EMAIL_HOST = check_setting_str(CFG, 'Email', 'email_host', '')
    EMAIL_PORT = check_setting_int(CFG, 'Email', 'email_port', 25)
    EMAIL_TLS = bool(check_setting_int(CFG, 'Email', 'email_tls', 0))
    EMAIL_USER = check_setting_str(CFG, 'Email', 'email_user', '')
    EMAIL_PASSWORD = check_setting_str(CFG, 'Email', 'email_password', '')
    EMAIL_FROM = check_setting_str(CFG, 'Email', 'email_from', '')
    EMAIL_LIST = check_setting_str(CFG, 'Email', 'email_list', '')

    USE_SUBTITLES = bool(check_setting_int(CFG, 'Subtitles', 'use_subtitles', 0))
    SUBTITLES_LANGUAGES = check_setting_str(CFG, 'Subtitles', 'subtitles_languages', '').split(',')
    if SUBTITLES_LANGUAGES[0] == '':
        SUBTITLES_LANGUAGES = []
    SUBTITLES_DIR = check_setting_str(CFG, 'Subtitles', 'subtitles_dir', '')
    SUBTITLES_SERVICES_LIST = check_setting_str(CFG, 'Subtitles', 'SUBTITLES_SERVICES_LIST', '').split(',')
    SUBTITLES_SERVICES_ENABLED = [int(x) for x in
                                  check_setting_str(CFG, 'Subtitles', 'SUBTITLES_SERVICES_ENABLED', '').split('|')
                                  if x]
    SUBTITLES_SERVICES_AUTH = [k.split(':::') for k in
                               check_setting_str(CFG, 'Subtitles', 'subtitles_services_auth', ':::').split('|||')
                               if k]
    try:
        # unlikely to happen, but did happen once, so added here as defensive
        dct_cfg = sg_helpers.ast_eval(check_setting_str(CFG, 'Subtitles', 'subtitles_services_auth', ':::'), {})
        SUBTITLES_SERVICES_AUTH = [[dct_cfg['os_user'], dct_cfg['os_pass']]]
    except (BaseException, Exception):
        pass
    SUBTITLES_DEFAULT = bool(check_setting_int(CFG, 'Subtitles', 'subtitles_default', 0))
    SUBTITLES_HISTORY = bool(check_setting_int(CFG, 'Subtitles', 'subtitles_history', 0))
    SUBTITLES_FINDER_INTERVAL = check_setting_int(CFG, 'Subtitles', 'subtitles_finder_interval', 1)
    SUBTITLES_OS_HASH = bool(check_setting_int(CFG, 'Subtitles', 'subtitles_os_hash', 1))

    USE_FAILED_DOWNLOADS = bool(check_setting_int(CFG, 'FailedDownloads', 'use_failed_downloads', 0))
    DELETE_FAILED = bool(check_setting_int(CFG, 'FailedDownloads', 'delete_failed', 0))

    GIT_PATH = check_setting_str(CFG, 'General', 'git_path', '')

    IGNORE_WORDS, IGNORE_WORDS_REGEX = helpers.split_word_str(
        check_setting_str(CFG, 'General', 'ignore_words', helpers.generate_word_str(IGNORE_WORDS, IGNORE_WORDS_REGEX)))
    REQUIRE_WORDS, REQUIRE_WORDS_REGEX = helpers.split_word_str(
        check_setting_str(CFG, 'General', 'require_words',
                          helpers.generate_word_str(REQUIRE_WORDS, REQUIRE_WORDS_REGEX)))

    CALENDAR_UNPROTECTED = bool(check_setting_int(CFG, 'General', 'calendar_unprotected', 0))

    EXTRA_SCRIPTS = [x.strip() for x in check_setting_str(CFG, 'General', 'extra_scripts', '').split('|') if
                     x.strip()]

    SG_EXTRA_SCRIPTS = [x.strip() for x in check_setting_str(CFG, 'General', 'sg_extra_scripts', '').split('|') if
                        x.strip()]

    USE_ANIDB = bool(check_setting_int(CFG, 'ANIDB', 'use_anidb', 0))
    ANIDB_USERNAME = check_setting_str(CFG, 'ANIDB', 'anidb_username', '')
    ANIDB_PASSWORD = check_setting_str(CFG, 'ANIDB', 'anidb_password', '')
    ANIDB_USE_MYLIST = bool(check_setting_int(CFG, 'ANIDB', 'anidb_use_mylist', 0))

    ANIME_TREAT_AS_HDTV = bool(check_setting_int(CFG, 'ANIME', 'anime_treat_as_hdtv', 0))

    METADATA_XBMC = check_setting_str(CFG, 'General', 'metadata_xbmc', '0|0|0|0|0|0|0|0|0|0')
    METADATA_XBMC_12PLUS = check_setting_str(CFG, 'General', 'metadata_xbmc_12plus', '0|0|0|0|0|0|0|0|0|0')
    METADATA_MEDIABROWSER = check_setting_str(CFG, 'General', 'metadata_mediabrowser', '0|0|0|0|0|0|0|0|0|0')
    METADATA_PS3 = check_setting_str(CFG, 'General', 'metadata_ps3', '0|0|0|0|0|0|0|0|0|0')
    METADATA_WDTV = check_setting_str(CFG, 'General', 'metadata_wdtv', '0|0|0|0|0|0|0|0|0|0')
    METADATA_TIVO = check_setting_str(CFG, 'General', 'metadata_tivo', '0|0|0|0|0|0|0|0|0|0')
    METADATA_MEDE8ER = check_setting_str(CFG, 'General', 'metadata_mede8er', '0|0|0|0|0|0|0|0|0|0')
    METADATA_KODI = check_setting_str(CFG, 'General', 'metadata_kodi', '0|0|0|0|0|0|0|0|0|0')

    HOME_LAYOUT = check_setting_str(CFG, 'GUI', 'home_layout', 'poster')
    FOOTER_TIME_LAYOUT = check_setting_int(CFG, 'GUI', 'footer_time_layout', 0)
    POSTER_SORTBY = check_setting_str(CFG, 'GUI', 'poster_sortby', 'name')
    POSTER_SORTDIR = check_setting_int(CFG, 'GUI', 'poster_sortdir', 1)
    DISPLAY_SHOW_GLIDE = sg_helpers.ast_eval(check_setting_str(CFG, 'GUI', 'display_show_glide', None), {})
    DISPLAY_SHOW_GLIDE_SLIDETIME = check_setting_int(CFG, 'GUI', 'display_show_glide_slidetime', 3000)
    DISPLAY_SHOW_VIEWMODE = check_setting_int(CFG, 'GUI', 'display_show_viewmode', 2)
    DISPLAY_SHOW_BACKGROUND = bool(check_setting_int(CFG, 'GUI', 'display_show_background', 1))
    DISPLAY_SHOW_BACKGROUND_TRANSLUCENT = bool(check_setting_int(
        CFG, 'GUI', 'display_show_background_translucent', 1))
    DISPLAY_SHOW_VIEWART = check_setting_int(CFG, 'GUI', 'display_show_viewart', 0)
    DISPLAY_SHOW_MINIMUM = bool(check_setting_int(CFG, 'GUI', 'display_show_minimum', 1))
    DISPLAY_SHOW_SPECIALS = bool(check_setting_int(CFG, 'GUI', 'display_show_specials', 0))

    EPISODE_VIEW_VIEWMODE = check_setting_int(CFG, 'GUI', 'episode_view_viewmode', 2)
    EPISODE_VIEW_BACKGROUND = bool(check_setting_int(CFG, 'GUI', 'episode_view_background', 1))
    EPISODE_VIEW_BACKGROUND_TRANSLUCENT = bool(check_setting_int(
        CFG, 'GUI', 'episode_view_background_translucent', 1))
    EPISODE_VIEW_LAYOUT = check_setting_str(CFG, 'GUI', 'episode_view_layout', 'daybyday')
    EPISODE_VIEW_SORT = check_setting_str(CFG, 'GUI', 'episode_view_sort', 'time')
    EPISODE_VIEW_DISPLAY_PAUSED = check_setting_int(CFG, 'GUI', 'episode_view_display_paused', 1)
    EPISODE_VIEW_POSTERS = bool(check_setting_int(CFG, 'GUI', 'episode_view_posters', 1))
    EPISODE_VIEW_MISSED_RANGE = check_setting_int(CFG, 'GUI', 'episode_view_missed_range', 7)

    HISTORY_LAYOUT = check_setting_str(CFG, 'GUI', 'history_layout', 'detailed')
    BROWSELIST_HIDDEN = list(map(
        lambda y: TVidProdid.glue in y and y or '%s%s%s' % (
            (TVINFO_TVDB, TVINFO_IMDB)[bool(helpers.parse_imdb_id(y))], TVidProdid.glue, y),
        [x.strip() for x in check_setting_str(CFG, 'GUI', 'browselist_hidden', '').split('|~|') if x.strip()]))
    BROWSELIST_MRU = sg_helpers.ast_eval(check_setting_str(CFG, 'GUI', 'browselist_prefs', None), {})

    BACKUP_DB_PATH = check_setting_str(CFG, 'Backup', 'backup_db_path', '')
    BACKUP_DB_ONEDAY = bool(check_setting_int(CFG, 'Backup', 'backup_db_oneday', 0))
    BACKUP_DB_MAX_COUNT = minimax(check_setting_int(CFG, 'Backup', 'backup_db_max_count', BACKUP_DB_DEFAULT_COUNT),
                                  BACKUP_DB_DEFAULT_COUNT, 0, 90)

    UPDATES_TODO = sg_helpers.ast_eval(check_setting_str(CFG, 'Updates', 'updates_todo', None), {})

    sg_helpers.db = db
    sg_helpers.DOMAIN_FAILURES.load_from_db()

    # initialize NZB and TORRENT providers
    provider_list = providers.provider_modules()

    NEWZNAB_DATA = check_setting_str(CFG, 'Newznab', 'newznab_data', '')
    newznab_providers = providers.newznab_source_list(NEWZNAB_DATA)

    torrentrss_data = check_setting_str(CFG, 'TorrentRss', 'torrentrss_data', '')
    torrent_rss_providers = providers.torrent_rss_source_list(torrentrss_data)

    # dynamically load provider settings
    for torrent_prov in [curProvider for curProvider in providers.sorted_sources()
                         if GenericProvider.TORRENT == curProvider.providerType]:
        prov_id = torrent_prov.get_id()
        prov_id_uc = torrent_prov.get_id().upper()
        torrent_prov.enabled = bool(check_setting_int(CFG, prov_id_uc, prov_id, False))

        # check str with a def of list, don't add to block settings
        if getattr(torrent_prov, 'url_edit', None):
            torrent_prov.url_home = check_setting_str(CFG, prov_id_uc, prov_id + '_url_home', [])

        # check int with a default of str, don't add to block settings
        attr = 'seed_time'
        if hasattr(torrent_prov, attr):
            torrent_prov.seed_time = check_setting_int(CFG, prov_id_uc, '%s_%s' % (prov_id, attr), '')

        # custom cond, don't add to block settings
        attr = 'enable_recentsearch'
        if hasattr(torrent_prov, attr):
            torrent_prov.enable_recentsearch = bool(check_setting_int(
                CFG, prov_id_uc, '%s_%s' % (prov_id, attr), True)) or not getattr(torrent_prov, 'supports_backlog')

        # check str with a default of list, don't add to block settings
        if hasattr(torrent_prov, 'filter'):
            torrent_prov.filter = check_setting_str(CFG, prov_id_uc, prov_id + '_filter', [])

        for (attr, default) in [
            ('enable_backlog', True), ('enable_scheduled_backlog', True),
            ('api_key', ''), ('hash', ''), ('digest', ''),
            ('username', ''), ('uid', ''), ('password', ''), ('passkey', ''),
            ('options', ''),
            ('_seed_ratio', ''), ('minseed', 0), ('minleech', 0),
            ('scene_only', False), ('scene_or_contain', ''), ('scene_loose', False), ('scene_loose_active', False),
            ('scene_rej_nuked', False), ('scene_nuked_active', False),
            ('freeleech', False), ('confirmed', False), ('reject_m2ts', False), ('use_after_get_data', True),
            ('search_mode', 'eponly'), ('search_fallback', False)
        ]:
            if hasattr(torrent_prov, attr):
                attr_check = '%s_%s' % (prov_id, attr.strip('_'))
                if isinstance(default, bool):
                    setattr(torrent_prov, attr, bool(check_setting_int(CFG, prov_id_uc, attr_check, default)))
                elif isinstance(default, string_types):
                    setattr(torrent_prov, attr, check_setting_str(CFG, prov_id_uc, attr_check, default))
                elif isinstance(default, int):
                    setattr(torrent_prov, attr, check_setting_int(CFG, prov_id_uc, attr_check, default))

    for nzb_prov in [curProvider for curProvider in providers.sorted_sources()
                     if GenericProvider.NZB == curProvider.providerType]:
        prov_id = nzb_prov.get_id()
        prov_id_uc = nzb_prov.get_id().upper()
        nzb_prov.enabled = bool(check_setting_int(CFG, prov_id_uc, prov_id, False))

        attr = 'enable_recentsearch'
        if hasattr(nzb_prov, attr):
            nzb_prov.enable_recentsearch = bool(check_setting_int(
                CFG, prov_id_uc, '%s_%s' % (prov_id, attr), True)) or not getattr(nzb_prov, 'supports_backlog')

        for (attr, default) in [
            ('enable_backlog', True), ('enable_scheduled_backlog', True),
            ('api_key', ''), ('digest', ''), ('username', ''),
            ('scene_only', False), ('scene_or_contain', ''), ('scene_loose', False), ('scene_loose_active', False),
            ('scene_rej_nuked', False), ('scene_nuked_active', False),
            ('search_mode', 'eponly'), ('search_fallback', False), ('server_type', NewznabConstants.SERVER_DEFAULT)
        ]:
            if hasattr(nzb_prov, attr):
                attr_check = '%s_%s' % (prov_id, attr.strip('_'))
                if isinstance(default, bool):
                    setattr(nzb_prov, attr, bool(check_setting_int(CFG, prov_id_uc, attr_check, default)))
                elif isinstance(default, string_types):
                    setattr(nzb_prov, attr, check_setting_str(CFG, prov_id_uc, attr_check, default))
                elif isinstance(default, int):
                    setattr(nzb_prov, attr, check_setting_int(CFG, prov_id_uc, attr_check, default))
    for cur_provider in filter(lambda p: abs(zlib.crc32(decode_bytes(p.name))) + 40000400 in (
            1449593765, 1597250020, 1524942228, 160758496, 2925374331
    ) or (p.url and abs(zlib.crc32(decode_bytes(re.sub(r'[./]', '', p.url[-10:])))) + 40000400 in (
            2417143804,)), providers.sorted_sources()):
        header = {'User-Agent': get_ua()}
        if hasattr(cur_provider, 'nn'):
            cur_provider.nn = False
            cur_provider.ui_string()
            # noinspection PyProtectedMember
            header = callable(getattr(cur_provider, '_init_api', False)) and False is cur_provider._init_api() \
                and header or {}
        cur_provider.headers.update(header)
        update_config |= cur_provider.should_save_config()

    # current commit hash
    CUR_COMMIT_HASH = check_setting_str(CFG, 'General', 'cur_commit_hash', '')

    # current commit branch
    CUR_COMMIT_BRANCH = check_setting_str(CFG, 'General', 'cur_commit_branch', '')

    if not CUR_COMMIT_HASH or '00000000000000000000000000000000000' == CUR_COMMIT_HASH:
        tmp_v = version_checker.SoftwareUpdater()
        if 'git' == tmp_v.install_type:
            # noinspection PyProtectedMember
            tmp_v.updater._find_installed_version()
            if not CUR_COMMIT_HASH:
                # in case git fails for some reason, set dummy hash to enable update for next start
                CUR_COMMIT_HASH = '00000000000000000000000000000000000'
            if not CUR_COMMIT_BRANCH:
                # noinspection PyProtectedMember
                tmp_branch = tmp_v.updater._find_installed_branch()
                if tmp_branch:
                    CUR_COMMIT_BRANCH = tmp_branch
            update_config = True

    EXT_UPDATES = (35 > len(CUR_COMMIT_HASH) or not bool(re.match('^[a-z0-9]+$', CUR_COMMIT_HASH))) and \
        ('docker/other', 'snap')['snap' in CUR_COMMIT_HASH]

    if not os.path.isfile(CONFIG_FILE):
        logger.debug(f'Unable to find \'{CONFIG_FILE}\', all settings will be default!')
        update_config = True

    # Get expected config version
    CONFIG_VERSION = max(ConfigMigrator(CFG).migration_names)

    # we have fully loaded all config settings into vars
    CONFIG_LOADED = True

    if update_config:
        _save_config(force=True)

    # start up all the threads
    old_log = os.path.join(LOG_DIR, 'sickgear.log')
    if os.path.isfile(old_log):
        try:
            os.rename(old_log, os.path.join(LOG_DIR, logger.sb_log_instance.log_file))
        except (BaseException, Exception):
            pass
    logger.sb_log_instance.init_logging(console_logging=console_logging)

    showList = []
    showDict = {}

    # dict of switched shows for web redirects
    switched_shows = {}


def init_stage_2():

    # Misc
    global __INITIALIZED__, MEMCACHE, MEMCACHE_FLAG_IMAGES, RECENTSEARCH_STARTUP
    # Schedulers
    # global trakt_checker_scheduler
    global update_software_scheduler, update_packages_scheduler, \
        update_show_scheduler, update_release_mappings_scheduler, \
        search_backlog_scheduler, search_propers_scheduler, \
        search_recent_scheduler, search_subtitles_scheduler, \
        search_queue_scheduler, show_queue_scheduler, people_queue_scheduler, \
        watched_state_queue_scheduler, emby_watched_state_scheduler, plex_watched_state_scheduler, \
        process_media_scheduler, background_mapping_task, config_events

    # Gen Config/Misc
    global SHOW_UPDATE_HOUR, UPDATE_INTERVAL, UPDATE_PACKAGES_INTERVAL
    # Search Settings/Episode
    global RECENTSEARCH_INTERVAL
    # Subtitles
    global USE_SUBTITLES, SUBTITLES_FINDER_INTERVAL
    # Media Process/Post-Processing
    global PROCESS_AUTOMATICALLY, MEDIAPROCESS_INTERVAL
    # Media Process/Metadata
    global metadata_provider_dict, METADATA_KODI, METADATA_MEDE8ER, METADATA_MEDIABROWSER, \
        METADATA_PS3, METADATA_TIVO, METADATA_WDTV, METADATA_XBMC, METADATA_XBMC_12PLUS
    # Notification Settings/HT and NAS
    global EMBY_WATCHEDSTATE_INTERVAL, PLEX_WATCHEDSTATE_INTERVAL

    # initialize main database
    my_db = db.DBConnection()
    db.migration_code(my_db)

    # initialize the cache database
    my_db = db.DBConnection('cache.db')
    db.upgrade_database(my_db, cache_db.InitialSchema)

    # initialize the failed downloads database
    my_db = db.DBConnection('failed.db')
    db.upgrade_database(my_db, failed_db.InitialSchema)

    # fix up any db problems
    my_db = db.DBConnection()
    db.sanity_check_db(my_db, mainDB.MainSanityCheck)

    # initialize metadata_providers
    metadata_provider_dict = metadata.get_metadata_generator_dict()
    for cur_metadata_tuple in [(METADATA_KODI, metadata.kodi),
                               (METADATA_MEDE8ER, metadata.mede8er),
                               (METADATA_MEDIABROWSER, metadata.mediabrowser),
                               (METADATA_PS3, metadata.ps3),
                               (METADATA_TIVO, metadata.tivo),
                               (METADATA_WDTV, metadata.wdtv),
                               (METADATA_XBMC, metadata.xbmc),
                               (METADATA_XBMC_12PLUS, metadata.xbmc_12plus),
                               ]:
        (cur_metadata_config, cur_metadata_class) = cur_metadata_tuple
        tmp_provider = cur_metadata_class.metadata_class()
        tmp_provider.set_config(cur_metadata_config)
        metadata_provider_dict[tmp_provider.name] = tmp_provider

    # initialize schedulers
    # /
    # queues must be first
    show_queue_scheduler = scheduler.Scheduler(
        show_queue.ShowQueue(),
        cycle_time=datetime.timedelta(seconds=3),
        thread_name='SHOWQUEUE')

    search_queue_scheduler = scheduler.Scheduler(
        search_queue.SearchQueue(),
        cycle_time=datetime.timedelta(seconds=3),
        thread_name='SEARCHQUEUE')

    people_queue_scheduler = scheduler.Scheduler(
        people_queue.PeopleQueue(),
        cycle_time=datetime.timedelta(seconds=3),
        thread_name='PEOPLEQUEUE'
    )

    watched_state_queue_scheduler = scheduler.Scheduler(
        watchedstate_queue.WatchedStateQueue(),
        cycle_time=datetime.timedelta(seconds=3),
        thread_name='WATCHEDSTATEQUEUE')

    # /
    # updaters
    update_software_scheduler = scheduler.Scheduler(
        version_checker.SoftwareUpdater(),
        cycle_time=datetime.timedelta(hours=UPDATE_INTERVAL),
        thread_name='SOFTWAREUPDATE',
        silent=False)

    update_packages_scheduler = scheduler.Scheduler(
        version_checker.PackagesUpdater(),
        cycle_time=datetime.timedelta(hours=UPDATE_PACKAGES_INTERVAL),
        # run_delay=datetime.timedelta(minutes=2),
        thread_name='PACKAGESUPDATE',
        silent=False)

    update_show_scheduler = scheduler.Scheduler(
        show_updater.ShowUpdater(),
        cycle_time=datetime.timedelta(hours=1),
        start_time=datetime.time(hour=SHOW_UPDATE_HOUR),
        thread_name='SHOWDATAUPDATE',
        prevent_cycle_run=show_queue_scheduler.action.is_show_update_running)  # 3AM

    classes.loading_msg.message = 'Loading show maps'
    update_release_mappings_scheduler = scheduler.Scheduler(
        scene_exceptions.ReleaseMap(),
        cycle_time=datetime.timedelta(hours=2),
        thread_name='SHOWMAPSUPDATE',
        silent=False)

    # /
    # searchers
    init_search_delay = int(os.environ.get('INIT_SEARCH_DELAY', 0))

    # enter 4499 (was 4489) for experimental internal provider intervals
    update_interval = datetime.timedelta(minutes=(RECENTSEARCH_INTERVAL, 1)[4499 == RECENTSEARCH_INTERVAL])
    update_now = datetime.timedelta(minutes=0)
    search_recent_scheduler = scheduler.Scheduler(
        search_recent.RecentSearcher(),
        cycle_time=update_interval,
        run_delay=update_now if RECENTSEARCH_STARTUP else datetime.timedelta(minutes=init_search_delay or 5),
        thread_name='RECENTSEARCH',
        prevent_cycle_run=search_queue_scheduler.action.is_recentsearch_in_progress)

    if [x for x in providers.sorted_sources()
            if x.is_active() and getattr(x, 'enable_backlog', None) and GenericProvider.NZB == x.providerType]:
        nextbacklogpossible = datetime.datetime.fromtimestamp(
            search_backlog.BacklogSearcher().last_runtime) + datetime.timedelta(hours=23)
        now = datetime.datetime.now()
        if nextbacklogpossible > now:
            time_diff = nextbacklogpossible - now
            if (time_diff > datetime.timedelta(hours=12) and
                    nextbacklogpossible - datetime.timedelta(hours=12) > now):
                time_diff = time_diff - datetime.timedelta(hours=12)
        else:
            time_diff = datetime.timedelta(minutes=0)
        backlogdelay = helpers.try_int((time_diff.total_seconds() / 60) + 10, 10)
    else:
        backlogdelay = 10
    search_backlog_scheduler = search_backlog.BacklogSearchScheduler(
        search_backlog.BacklogSearcher(),
        cycle_time=datetime.timedelta(minutes=get_backlog_cycle_time()),
        run_delay=datetime.timedelta(minutes=init_search_delay or backlogdelay),
        thread_name='BACKLOGSEARCH',
        prevent_cycle_run=search_queue_scheduler.action.is_standard_backlog_in_progress)

    last_proper_search = datetime.datetime.fromtimestamp(properFinder.get_last_proper_search())
    time_diff = datetime.timedelta(days=1) - (datetime.datetime.now() - last_proper_search)
    if time_diff < datetime.timedelta(seconds=0):
        properdelay = 20
    else:
        properdelay = helpers.try_int((time_diff.total_seconds() / 60) + 5, 20)

    search_propers_scheduler = scheduler.Scheduler(
        search_propers.ProperSearcher(),
        cycle_time=datetime.timedelta(days=1),
        run_delay=datetime.timedelta(minutes=init_search_delay or properdelay),
        thread_name='PROPERSSEARCH',
        prevent_cycle_run=search_queue_scheduler.action.is_propersearch_in_progress)

    search_subtitles_scheduler = scheduler.Scheduler(
        subtitles.SubtitlesFinder(),
        cycle_time=datetime.timedelta(hours=SUBTITLES_FINDER_INTERVAL),
        thread_name='SUBTITLESEARCH',
        silent=not USE_SUBTITLES)

    # /
    # others
    emby_watched_state_scheduler = scheduler.Scheduler(
        EmbyWatchedStateUpdater(),
        cycle_time=datetime.timedelta(minutes=EMBY_WATCHEDSTATE_INTERVAL),
        run_delay=datetime.timedelta(minutes=5),
        thread_name='EMBYWATCHEDSTATE')

    plex_watched_state_scheduler = scheduler.Scheduler(
        PlexWatchedStateUpdater(),
        cycle_time=datetime.timedelta(minutes=PLEX_WATCHEDSTATE_INTERVAL),
        run_delay=datetime.timedelta(minutes=5),
        thread_name='PLEXWATCHEDSTATE')

    process_media_scheduler = scheduler.Scheduler(
        auto_media_process.MediaProcess(),
        cycle_time=datetime.timedelta(minutes=MEDIAPROCESS_INTERVAL),
        thread_name='PROCESSMEDIA',
        silent=not PROCESS_AUTOMATICALLY)

    background_mapping_task = threading.Thread(name='MAPPINGUPDATES', target=indexermapper.load_mapped_ids,
                                               kwargs={'load_all': True})

    MEMCACHE['history_tab_limit'] = 15
    MEMCACHE['history_tab'] = History.menu_tab(MEMCACHE['history_tab_limit'])

    try:
        with scandir(os.path.join(PROG_DIR, 'gui', GUI_NAME, 'images', 'flags')) as s_d:
            for f in s_d:
                if f.is_file():
                    MEMCACHE_FLAG_IMAGES[os.path.splitext(f.name)[0].lower()] = True
    except (BaseException, Exception):
        pass

    config_events = ConfigEvents(_save_config)
    config_events.start()

    __INITIALIZED__ = True
    return True


def enabled_schedulers(is_init=False):
    # ([], [trakt_checker_scheduler])[USE_TRAKT] + \
    return ([], [events])[is_init] \
           + ([], [update_software_scheduler, update_packages_scheduler,
                   update_show_scheduler, update_release_mappings_scheduler,
                   search_recent_scheduler, search_backlog_scheduler,
                   search_propers_scheduler, search_subtitles_scheduler,
                   show_queue_scheduler, search_queue_scheduler,
                   people_queue_scheduler, watched_state_queue_scheduler,
                   emby_watched_state_scheduler, plex_watched_state_scheduler,
                   process_media_scheduler
                   ]
              )[not MEMCACHE.get('update_restart')] \
           + ([events], [])[is_init]


def start():
    global started

    with INIT_LOCK:
        if __INITIALIZED__:
            # Load all Indexer mappings in background
            indexermapper.defunct_indexer = [
                i for i in TVInfoAPI().all_sources if TVInfoAPI(i).config.get('defunct')]
            indexermapper.indexer_list = [i for i in TVInfoAPI().all_sources if TVInfoAPI(i).config.get('show_url')
                                          and True is not TVInfoAPI(i).config.get('people_only')]
            background_mapping_task.start()

            for p in providers.sorted_sources():
                if p.is_active() and getattr(p, 'ping_iv', None):
                    # noinspection PyProtectedMember
                    provider_ping_thread_pool[p.get_id()] = threading.Thread(
                        name='PING-PROVIDER %s' % p.name, target=p._ping)
                    provider_ping_thread_pool[p.get_id()].start()

            for thread in enabled_schedulers(is_init=True):  # type: threading.Thread
                thread.start()

            started = True


def restart(soft=True, update_pkg=None):

    if not soft:
        if update_pkg:
            MY_ARGS.append('--update-pkg')

        logger.log('Trigger event restart')
        events.put(events.SystemEvent.RESTART)

    else:
        halt()
        save_all()
        logger.log('Re-initializing all data')
        initialize()


def sig_handler(signum=None, _=None):
    is_ctrlbreak = 'win32' == sys.platform and signal.SIGBREAK == signum
    msg = 'Signal "%s" found' % (signal.SIGINT == signum and 'CTRL-C' or is_ctrlbreak and 'CTRL+BREAK' or
                                 signal.SIGTERM == signum and 'Termination' or signum)
    if None is signum or signum in (signal.SIGINT, signal.SIGTERM) or is_ctrlbreak:
        logger.log('%s, saving and exiting...' % msg)
        events.put(events.SystemEvent.SHUTDOWN)
    else:
        logger.log('%s, not exiting' % msg)


def halt():
    global __INITIALIZED__, started, config_events

    logger.debug('Check INIT_LOCK on halt')
    with INIT_LOCK:

        logger.debug(f'Check __INITIALIZED__ on halt: {__INITIALIZED__}')
        if __INITIALIZED__:

            logger.log('Exiting threads')

            try:
                config_events.stopit()
            except (BaseException, Exception):
                pass

            for p in provider_ping_thread_pool:
                provider_ping_thread_pool[p].stop = True

            for p in provider_ping_thread_pool:
                try:
                    provider_ping_thread_pool[p].join(10)
                    logger.log('Thread %s has exit' % provider_ping_thread_pool[p].name)
                except RuntimeError:
                    logger.log('Fail, thread %s did not exit' % provider_ping_thread_pool[p].name)
                    pass

            if ADBA_CONNECTION:
                try:
                    ADBA_CONNECTION.logout()
                except AniDBError:
                    pass
                try:
                    ADBA_CONNECTION.join(10)
                    logger.log('Thread %s has exit' % ADBA_CONNECTION.name)
                except (BaseException, Exception):
                    logger.log('Fail, thread %s did not exit' % ADBA_CONNECTION.name)

            for thread in enabled_schedulers():  # type: scheduler.Scheduler
                try:
                    thread.stopit()
                    if getattr(thread, 'action', None) and getattr(thread.action, 'save_queue', None):
                        try:
                            thread.action.save_queue()
                        except (BaseException, Exception):
                            pass
                except Exception as e:
                    logger.log('Thread %s stop failed with: %s' % (thread.name, e))

            for thread in enabled_schedulers():  # type: threading.Thread
                try:
                    thread.join(10)
                    logger.log('Thread %s has exit' % thread.name)
                except RuntimeError:
                    # this just means it's the current thread, can be ignored
                    logger.log('Thread %s is exiting' % thread.name)
                except (BaseException, Exception) as e:
                    logger.log('Thread %s exception %s' % (thread.name, e))

            try:
                config_events.join(10)
            except RuntimeError:
                pass

            __INITIALIZED__ = False
            started = False


def save_all():
    if not MEMCACHE.get('update_restart'):
        global showList

        # write all shows
        logger.log('Saving all shows to the database')
        for show_obj in showList:  # type: tv.TVShow
            show_obj.save_to_db()

    # save config
    logger.log('Saving config file to disk')
    _save_config(force=True)


def save_config(force=False):
    # type: (bool) -> None
    """
    add queue request for saving the config.ini

    :param force: force save config even if unchanged
    """
    global config_events, CONFIG_LOADED
    if not CONFIG_LOADED:
        return

    # use queue if it's available, otherwise, call save_config directly
    hasattr(config_events, 'put') and config_events.put(force) or _save_config(force)


def _save_config(force=False, **kwargs):
    # type: (bool, ...) -> None
    global CONFIG_OLD, CONFIG_LOADED
    if not CONFIG_LOADED:
        return

    new_config = ConfigObj()
    new_config.filename = CONFIG_FILE

    # For passwords, you must include the word `password` in the item_name and
    # add `helpers.encrypt(ITEM_NAME, ENCRYPTION_VERSION)` in save_config()
    new_config['General'] = dict()
    s_z = check_setting_int(CFG, 'General', 'stack_size', 0)
    if s_z:
        new_config['General']['stack_size'] = s_z
    new_config['General']['config_version'] = CONFIG_VERSION
    new_config['General']['branch'] = BRANCH
    new_config['General']['git_remote'] = GIT_REMOTE
    new_config['General']['cur_commit_hash'] = CUR_COMMIT_HASH
    new_config['General']['cur_commit_branch'] = CUR_COMMIT_BRANCH
    new_config['General']['encryption_version'] = int(ENCRYPTION_VERSION)
    new_config['General']['log_dir'] = ACTUAL_LOG_DIR if ACTUAL_LOG_DIR else 'Logs'
    new_config['General']['file_logging_preset'] = FILE_LOGGING_PRESET \
        if FILE_LOGGING_PRESET and 'DB' != FILE_LOGGING_PRESET else 'DEBUG'
    new_config['General']['file_logging_db'] = 0
    new_config['General']['socket_timeout'] = SOCKET_TIMEOUT
    new_config['General']['web_host'] = WEB_HOST
    new_config['General']['web_port'] = WEB_PORT
    new_config['General']['web_ipv6'] = int(WEB_IPV6)
    new_config['General']['web_ipv64'] = int(WEB_IPV64)
    new_config['General']['web_log'] = int(WEB_LOG)
    new_config['General']['web_root'] = WEB_ROOT
    new_config['General']['web_username'] = WEB_USERNAME
    new_config['General']['web_password'] = helpers.encrypt(WEB_PASSWORD, ENCRYPTION_VERSION)
    new_config['General']['cpu_preset'] = CPU_PRESET
    new_config['General']['anon_redirect'] = ANON_REDIRECT
    new_config['General']['use_api'] = int(USE_API)
    new_config['General']['api_keys'] = '|||'.join([':::'.join(a) for a in API_KEYS])
    new_config['General']['debug'] = int(DEBUG)
    new_config['General']['enable_https'] = int(ENABLE_HTTPS)
    new_config['General']['https_cert'] = HTTPS_CERT
    new_config['General']['https_key'] = HTTPS_KEY
    new_config['General']['handle_reverse_proxy'] = int(HANDLE_REVERSE_PROXY)
    new_config['General']['send_security_headers'] = int(SEND_SECURITY_HEADERS)
    new_config['General']['allowed_hosts'] = ALLOWED_HOSTS
    new_config['General']['allow_anyip'] = int(ALLOW_ANYIP)
    new_config['General']['use_nzbs'] = int(USE_NZBS)
    new_config['General']['use_torrents'] = int(USE_TORRENTS)
    new_config['General']['nzb_method'] = NZB_METHOD
    new_config['General']['torrent_method'] = TORRENT_METHOD
    new_config['General']['usenet_retention'] = int(USENET_RETENTION)
    new_config['General']['mediaprocess_interval'] = int(MEDIAPROCESS_INTERVAL)
    new_config['General']['recentsearch_interval'] = int(RECENTSEARCH_INTERVAL)
    new_config['General']['backlog_period'] = int(BACKLOG_PERIOD)
    new_config['General']['backlog_limited_period'] = int(BACKLOG_LIMITED_PERIOD)
    new_config['General']['download_propers'] = int(DOWNLOAD_PROPERS)
    new_config['General']['propers_webdl_onegrp'] = int(PROPERS_WEBDL_ONEGRP)
    new_config['General']['allow_high_priority'] = int(ALLOW_HIGH_PRIORITY)
    new_config['General']['recentsearch_startup'] = int(RECENTSEARCH_STARTUP)
    new_config['General']['backlog_nofull'] = int(BACKLOG_NOFULL)
    new_config['General']['skip_removed_files'] = int(SKIP_REMOVED_FILES)
    new_config['General']['results_sortby'] = str(RESULTS_SORTBY)
    new_config['General']['indexer_default'] = int(TVINFO_DEFAULT)
    new_config['General']['indexer_timeout'] = int(TVINFO_TIMEOUT)
    new_config['General']['quality_default'] = int(QUALITY_DEFAULT)
    new_config['General']['wanted_begin_default'] = int(WANTED_BEGIN_DEFAULT)
    new_config['General']['wanted_latest_default'] = int(WANTED_LATEST_DEFAULT)
    new_config['General']['pause default'] = int(PAUSE_DEFAULT)
    new_config['General']['status_default'] = int(STATUS_DEFAULT)
    new_config['General']['scene_default'] = int(SCENE_DEFAULT)
    new_config['General']['flatten_folders_default'] = int(FLATTEN_FOLDERS_DEFAULT)
    new_config['General']['anime_default'] = int(ANIME_DEFAULT)
    new_config['General']['provider_order'] = ' '.join(PROVIDER_ORDER)
    new_config['General']['provider_homes'] = '%s' % dict([(pid, v) for pid, v in list(PROVIDER_HOMES.items())
                                                           if pid in [
        p.get_id() for p in [x for x in providers.sorted_sources() if GenericProvider.TORRENT == x.providerType]]])
    new_config['General']['update_notify'] = int(UPDATE_NOTIFY)
    new_config['General']['update_auto'] = int(UPDATE_AUTO)
    new_config['General']['update_interval'] = int(UPDATE_INTERVAL)
    new_config['General']['notify_on_update'] = int(NOTIFY_ON_UPDATE)
    new_config['General']['update_packages_notify'] = int(UPDATE_PACKAGES_NOTIFY)
    new_config['General']['update_packages_auto'] = int(UPDATE_PACKAGES_AUTO)
    new_config['General']['update_packages_menu'] = int(UPDATE_PACKAGES_MENU)
    new_config['General']['update_packages_interval'] = int(UPDATE_PACKAGES_INTERVAL)
    new_config['General']['naming_strip_year'] = int(NAMING_STRIP_YEAR)
    new_config['General']['naming_pattern'] = NAMING_PATTERN
    new_config['General']['naming_custom_abd'] = int(NAMING_CUSTOM_ABD)
    new_config['General']['naming_abd_pattern'] = NAMING_ABD_PATTERN
    new_config['General']['naming_custom_sports'] = int(NAMING_CUSTOM_SPORTS)
    new_config['General']['naming_sports_pattern'] = NAMING_SPORTS_PATTERN
    new_config['General']['naming_custom_anime'] = int(NAMING_CUSTOM_ANIME)
    new_config['General']['naming_anime_pattern'] = NAMING_ANIME_PATTERN
    new_config['General']['naming_multi_ep'] = int(NAMING_MULTI_EP)
    new_config['General']['naming_anime_multi_ep'] = int(NAMING_ANIME_MULTI_EP)
    new_config['General']['naming_anime'] = int(NAMING_ANIME)
    new_config['General']['launch_browser'] = int(LAUNCH_BROWSER)
    new_config['General']['update_shows_on_start'] = int(UPDATE_SHOWS_ON_START)
    new_config['General']['show_update_hour'] = int(SHOW_UPDATE_HOUR)
    new_config['General']['trash_remove_show'] = int(TRASH_REMOVE_SHOW)
    new_config['General']['trash_rotate_logs'] = int(TRASH_ROTATE_LOGS)
    new_config['General']['home_search_focus'] = int(HOME_SEARCH_FOCUS)
    new_config['General']['display_freespace'] = int(DISPLAY_FREESPACE)
    new_config['General']['sort_article'] = int(SORT_ARTICLE)
    new_config['General']['proxy_setting'] = PROXY_SETTING
    sg_helpers.PROXY_SETTING = PROXY_SETTING
    new_config['General']['proxy_indexers'] = int(PROXY_INDEXERS)

    new_config['General']['metadata_xbmc'] = METADATA_XBMC
    new_config['General']['metadata_xbmc_12plus'] = METADATA_XBMC_12PLUS
    new_config['General']['metadata_mediabrowser'] = METADATA_MEDIABROWSER
    new_config['General']['metadata_ps3'] = METADATA_PS3
    new_config['General']['metadata_wdtv'] = METADATA_WDTV
    new_config['General']['metadata_tivo'] = METADATA_TIVO
    new_config['General']['metadata_mede8er'] = METADATA_MEDE8ER
    new_config['General']['metadata_kodi'] = METADATA_KODI

    new_config['General']['search_unaired'] = int(SEARCH_UNAIRED)
    new_config['General']['unaired_recent_search_only'] = int(UNAIRED_RECENT_SEARCH_ONLY)
    new_config['General']['flaresolverr_host'] = FLARESOLVERR_HOST

    new_config['General']['cache_dir'] = ACTUAL_CACHE_DIR if ACTUAL_CACHE_DIR else 'cache'
    sg_helpers.CACHE_DIR = CACHE_DIR
    sg_helpers.DATA_DIR = DATA_DIR
    new_config['General']['root_dirs'] = ROOT_DIRS if ROOT_DIRS else ''
    new_config['General']['tv_download_dir'] = TV_DOWNLOAD_DIR
    new_config['General']['keep_processed_dir'] = int(KEEP_PROCESSED_DIR)
    new_config['General']['process_method'] = PROCESS_METHOD
    new_config['General']['process_last_dir'] = PROCESS_LAST_DIR
    new_config['General']['process_last_method'] = PROCESS_LAST_METHOD
    new_config['General']['process_last_cleanup'] = int(PROCESS_LAST_CLEANUP)
    new_config['General']['move_associated_files'] = int(MOVE_ASSOCIATED_FILES)
    new_config['General']['postpone_if_sync_files'] = int(POSTPONE_IF_SYNC_FILES)
    new_config['General']['process_positive_log'] = int(PROCESS_POSITIVE_LOG)
    new_config['General']['nfo_rename'] = int(NFO_RENAME)
    new_config['General']['process_automatically'] = int(PROCESS_AUTOMATICALLY)
    new_config['General']['unpack'] = int(UNPACK)
    new_config['General']['rename_episodes'] = int(RENAME_EPISODES)
    new_config['General']['rename_tba_episodes'] = int(RENAME_TBA_EPISODES)
    new_config['General']['rename_name_changed_episodes'] = int(RENAME_NAME_CHANGED_EPISODES)
    new_config['General']['airdate_episodes'] = int(AIRDATE_EPISODES)
    new_config['General']['create_missing_show_dirs'] = int(CREATE_MISSING_SHOW_DIRS)
    new_config['General']['show_dirs_with_dots'] = int(SHOW_DIRS_WITH_DOTS)
    new_config['General']['add_shows_wo_dir'] = int(ADD_SHOWS_WO_DIR)
    new_config['General']['add_shows_metalang'] = ADD_SHOWS_METALANG
    new_config['General']['remove_filename_chars'] = REMOVE_FILENAME_CHARS
    new_config['General']['import_default_checked_shows'] = int(IMPORT_DEFAULT_CHECKED_SHOWS)

    new_config['General']['extra_scripts'] = '|'.join(EXTRA_SCRIPTS)
    new_config['General']['sg_extra_scripts'] = '|'.join(SG_EXTRA_SCRIPTS)
    new_config['General']['git_path'] = GIT_PATH
    new_config['General']['ignore_words'] = helpers.generate_word_str(IGNORE_WORDS, IGNORE_WORDS_REGEX)
    new_config['General']['require_words'] = helpers.generate_word_str(REQUIRE_WORDS, REQUIRE_WORDS_REGEX)
    new_config['General']['calendar_unprotected'] = int(CALENDAR_UNPROTECTED)

    new_config['Updates'] = {}
    new_config['Updates']['updates_todo'] = '%s' % (UPDATES_TODO or {})

    new_config['Backup'] = {}
    if BACKUP_DB_PATH:
        new_config['Backup']['backup_db_path'] = BACKUP_DB_PATH
    new_config['Backup']['backup_db_oneday'] = int(BACKUP_DB_ONEDAY)
    new_config['Backup']['backup_db_max_count'] = BACKUP_DB_MAX_COUNT

    default_not_zero = ('enable_recentsearch', 'enable_backlog', 'enable_scheduled_backlog', 'use_after_get_data')
    for src in filter(lambda px: GenericProvider.TORRENT == px.providerType, providers.sorted_sources()):
        src_id = src.get_id()
        src_id_uc = src_id.upper()
        new_config[src_id_uc] = {}
        if int(src.enabled):
            new_config[src_id_uc][src_id] = int(src.enabled)
        if getattr(src, 'url_edit', None):
            new_config[src_id_uc][src_id + '_url_home'] = src.url_home

        if getattr(src, 'password', None):
            new_config[src_id_uc][src_id + '_password'] = helpers.encrypt(src.password, ENCRYPTION_VERSION)

        for (attr, value) in [
            (k, getattr(src, k, v) if not v else helpers.try_int(getattr(src, k, None)))
            for (k, v) in [
                ('enable_recentsearch', 1), ('enable_backlog', 1), ('enable_scheduled_backlog', 1),
                ('api_key', None), ('passkey', None), ('digest', None), ('hash', None), ('username', ''), ('uid', ''),
                ('minseed', 1), ('minleech', 1), ('seed_time', None),
                ('confirmed', 1), ('freeleech', 1), ('reject_m2ts', 1), ('use_after_get_data', 1),
                ('scene_only', None), ('scene_or_contain', ''), ('scene_loose', None), ('scene_loose_active', None),
                ('scene_rej_nuked', None), ('scene_nuked_active', None),
                ('search_mode', None), ('search_fallback', 1)
            ]
                if hasattr(src, k)]:
            if (value and not ('search_mode' == attr and 'eponly' == value)
                    # must allow the following to save '0' not '1' because default is enable (1) instead of disable (0)
                    and (attr not in default_not_zero) or not value and (attr in default_not_zero)):
                new_config[src_id_uc]['%s_%s' % (src_id, attr)] = value

        if getattr(src, '_seed_ratio', None):
            new_config[src_id_uc][src_id + '_seed_ratio'] = src.seed_ratio()
        if getattr(src, 'filter', None):
            new_config[src_id_uc][src_id + '_filter'] = src.filter

        if not new_config[src_id_uc]:
            del new_config[src_id_uc]

    default_not_zero = ('enable_recentsearch', 'enable_backlog', 'enable_scheduled_backlog')
    for src in filter(lambda px: GenericProvider.NZB == px.providerType, providers.sorted_sources()):
        src_id = src.get_id()
        src_id_uc = src.get_id().upper()
        new_config[src_id_uc] = {}
        if int(src.enabled):
            new_config[src_id_uc][src_id] = int(src.enabled)

        for attr in filter(lambda _a: None is not getattr(src, _a, None),
                           ('api_key', 'digest', 'username', 'search_mode')):
            if 'search_mode' != attr or 'eponly' != getattr(src, attr):
                new_config[src_id_uc]['%s_%s' % (src_id, attr)] = getattr(src, attr)

        for attr in filter(lambda _a: None is not getattr(src, _a, None), (
                'enable_recentsearch', 'enable_backlog', 'enable_scheduled_backlog',
                'scene_only', 'scene_loose', 'scene_loose_active',
                'scene_rej_nuked', 'scene_nuked_active',
                'search_fallback', 'server_type')):
            value = helpers.try_int(getattr(src, attr, None))
            # must allow the following to save '0' not '1' because default is enable (1) instead of disable (0)
            if (value and (attr not in default_not_zero)) or (not value and (attr in default_not_zero)):
                new_config[src_id_uc]['%s_%s' % (src_id, attr)] = value

        attr = 'scene_or_contain'
        if getattr(src, attr, None):
            new_config[src_id_uc]['%s_%s' % (src_id, attr)] = getattr(src, attr, '')

        if not new_config[src_id_uc]:
            del new_config[src_id_uc]

    cfg_keys = []
    for (cfg, items) in iteritems(OrderedDict([
        # -----------------------------------
        # Config/Search
        # -----------------------------------
        ('Blackhole', [
            ('nzb_dir', NZB_DIR), ('torrent_dir', TORRENT_DIR)]),
        ('NZBGet', [
            ('username', NZBGET_USERNAME), ('password', helpers.encrypt(NZBGET_PASSWORD, ENCRYPTION_VERSION)),
            ('host', NZBGET_HOST),
            ('category', NZBGET_CATEGORY),
            ('use_https', int(NZBGET_USE_HTTPS)),
            ('priority', NZBGET_PRIORITY),
            ('map', NZBGET_MAP),
            ('skip_process_media', int(NZBGET_SKIP_PM)),
        ]),
        ('SABnzbd', [
            ('username', SAB_USERNAME), ('password', helpers.encrypt(SAB_PASSWORD, ENCRYPTION_VERSION)),
            ('apikey', SAB_APIKEY),
            ('host', SAB_HOST),
            ('category', SAB_CATEGORY),
        ]),
        ('TORRENT', [
            ('username', TORRENT_USERNAME), ('password', helpers.encrypt(TORRENT_PASSWORD, ENCRYPTION_VERSION)),
            ('host', TORRENT_HOST),
            ('path', TORRENT_PATH),
            ('seed_time', int(TORRENT_SEED_TIME)),
            ('paused', int(TORRENT_PAUSED)),
            ('high_bandwidth', int(TORRENT_HIGH_BANDWIDTH)),
            ('label', TORRENT_LABEL),
            ('label_var', int(TORRENT_LABEL_VAR)),
            ('verify_cert', int(TORRENT_VERIFY_CERT)),
        ]),
        # -----------------------------------
        # Config/Notifications
        # -----------------------------------
        ('Emby', [
            ('use_%s', int(USE_EMBY)),
            ('apikey', EMBY_APIKEY), ('host', EMBY_HOST),
            ('update_library', int(EMBY_UPDATE_LIBRARY)),
            ('watchedstate_scheduled', int(EMBY_WATCHEDSTATE_SCHEDULED)),
            ('watchedstate_interval', int(EMBY_WATCHEDSTATE_INTERVAL)),
            ('parent_maps', EMBY_PARENT_MAPS),
        ]),
        ('Kodi', [
            ('use_%s', int(USE_KODI)),
            ('username', KODI_USERNAME), ('password', helpers.encrypt(KODI_PASSWORD, ENCRYPTION_VERSION)),
            ('host', KODI_HOST),
            ('always_on', int(KODI_ALWAYS_ON)), ('update_library', int(KODI_UPDATE_LIBRARY)),
            ('update_full', int(KODI_UPDATE_FULL)),
            ('update_onlyfirst', int(KODI_UPDATE_ONLYFIRST)),
            ('parent_maps', KODI_PARENT_MAPS),
        ]),
        ('Plex', [
            ('use_%s', int(USE_PLEX)),
            ('username', PLEX_USERNAME), ('password', helpers.encrypt(PLEX_PASSWORD, ENCRYPTION_VERSION)),
            ('host', PLEX_HOST),
            ('update_library', int(PLEX_UPDATE_LIBRARY)),
            ('watchedstate_scheduled', int(PLEX_WATCHEDSTATE_SCHEDULED)),
            ('watchedstate_interval', int(PLEX_WATCHEDSTATE_INTERVAL)),
            ('parent_maps', PLEX_PARENT_MAPS),
            ('server_host', PLEX_SERVER_HOST),
        ]),
        ('XBMC', [
            ('use_%s', int(USE_XBMC)),
            ('username', XBMC_USERNAME), ('password', helpers.encrypt(XBMC_PASSWORD, ENCRYPTION_VERSION)),
            ('host', XBMC_HOST),
            ('always_on', int(XBMC_ALWAYS_ON)), ('update_library', int(XBMC_UPDATE_LIBRARY)),
            ('update_full', int(XBMC_UPDATE_FULL)),
            ('update_onlyfirst', int(XBMC_UPDATE_ONLYFIRST)),
        ]),
        ('NMJ', [
            ('use_%s', int(USE_NMJ)),
            ('host', NMJ_HOST),
            ('database', NMJ_DATABASE),
            ('mount', NMJ_MOUNT),
        ]),
        ('NMJv2', [
            ('use_%s', int(USE_NMJv2)),
            ('host', NMJv2_HOST),
            ('database', NMJv2_DATABASE),
            ('dbloc', NMJv2_DBLOC),
        ]),
        ('Synology', [
            ('use_synoindex', int(USE_SYNOINDEX)),
        ]),
        ('SynologyNotifier', [
            ('use_%s', int(USE_SYNOLOGYNOTIFIER)),
        ]),
        ('pyTivo', [
            ('use_%s', int(USE_PYTIVO)),
            ('host', PYTIVO_HOST),
            ('share_name', PYTIVO_SHARE_NAME),
            ('tivo_name', PYTIVO_TIVO_NAME),
        ]),
        ('Boxcar2', [
            ('use_%s', int(USE_BOXCAR2)),
            ('accesstoken', BOXCAR2_ACCESSTOKEN),
            ('sound', BOXCAR2_SOUND if 'default' != BOXCAR2_SOUND else None),
        ]),
        ('Pushbullet', [
            ('use_%s', int(USE_PUSHBULLET)),
            ('access_token', PUSHBULLET_ACCESS_TOKEN),
            ('device_iden', PUSHBULLET_DEVICE_IDEN),
        ]),
        ('Pushover', [
            ('use_%s', int(USE_PUSHOVER)),
            ('userkey', PUSHOVER_USERKEY),
            ('apikey', PUSHOVER_APIKEY),
            ('priority', PUSHOVER_PRIORITY if '0' != PUSHOVER_PRIORITY else None),
            ('device', PUSHOVER_DEVICE if 'all' != PUSHOVER_DEVICE else None),
            ('sound', PUSHOVER_SOUND if 'pushover' != PUSHOVER_SOUND else None),
        ]),
        ('Growl', [
            ('use_%s', int(USE_GROWL)),
            ('host', GROWL_HOST),
            # ('password', helpers.encrypt(GROWL_PASSWORD, ENCRYPTION_VERSION)),
        ]),
        ('Prowl', [
            ('use_%s', int(USE_PROWL)),
            ('api', PROWL_API),
            ('priority', PROWL_PRIORITY if '0' != PROWL_PRIORITY else None),
        ]),
        ('Libnotify', [
            ('use_%s', int(USE_LIBNOTIFY))
        ]),
        # deprecated service
        # new_config['Pushalot'] = {}
        # new_config['Pushalot']['use_pushalot'] = int(USE_PUSHALOT)
        # new_config['Pushalot']['pushalot_authorizationtoken'] = PUSHALOT_AUTHORIZATIONTOKEN
        ('Trakt', [
            ('use_%s', int(USE_TRAKT)),
            ('update_collection', TRAKT_UPDATE_COLLECTION
                and trakt_helpers.build_config_string(TRAKT_UPDATE_COLLECTION)),
            ('accounts', TraktAPI.build_config_string(TRAKT_ACCOUNTS)),
            ('mru', TRAKT_MRU),
            # new_config['Trakt'] = {}
            # new_config['Trakt']['trakt_remove_watchlist'] = int(TRAKT_REMOVE_WATCHLIST)
            # new_config['Trakt']['trakt_remove_serieslist'] = int(TRAKT_REMOVE_SERIESLIST)
            # new_config['Trakt']['trakt_use_watchlist'] = int(TRAKT_USE_WATCHLIST)
            # new_config['Trakt']['trakt_method_add'] = int(TRAKT_METHOD_ADD)
            # new_config['Trakt']['trakt_start_paused'] = int(TRAKT_START_PAUSED)
            # new_config['Trakt']['trakt_sync'] = int(TRAKT_SYNC)
            # new_config['Trakt']['trakt_default_indexer'] = int(TRAKT_DEFAULT_INDEXER)
        ]),
        ('Metacritic', [
            ('mru', MC_MRU)
        ]),
        ('NextEpisode', [
            ('mru', NE_MRU)
        ]),
        ('TMDB', [
            ('mru', TMDB_MRU)
        ]),
        ('TVCalendar', [
            ('mru', TVC_MRU)
        ]),
        ('TVDb', [
            ('mru', TVDB_MRU)
        ]),
        ('TVmaze', [
            ('mru', TVM_MRU)
        ]),
        ('Slack', [
            ('use_%s', int(USE_SLACK)),
            ('channel', SLACK_CHANNEL),
            ('as_authed', int(SLACK_AS_AUTHED)),
            ('bot_name', SLACK_BOT_NAME),
            ('icon_url', SLACK_ICON_URL),
            ('access_token', SLACK_ACCESS_TOKEN),
        ]),
        ('Discord', [
            ('use_%s', int(USE_DISCORD)),
            ('as_authed', int(DISCORD_AS_AUTHED)),
            ('username', DISCORD_USERNAME),
            ('icon_url', DISCORD_ICON_URL),
            ('as_tts', int(DISCORD_AS_TTS)),
            ('access_token', DISCORD_ACCESS_TOKEN),
        ]),
        ('Gitter', [
            ('use_%s', int(USE_GITTER)),
            ('room', GITTER_ROOM),
            ('access_token', GITTER_ACCESS_TOKEN),
        ]),
        ('Telegram', [
            ('use_%s', int(USE_TELEGRAM)),
            ('send_image', int(TELEGRAM_SEND_IMAGE)),
            ('quiet', int(TELEGRAM_QUIET)),
            ('access_token', TELEGRAM_ACCESS_TOKEN),
            ('chatid', TELEGRAM_CHATID),
        ]),
        ('Email', [
            ('use_%s', int(USE_EMAIL)),
            ('old_subjects', int(EMAIL_OLD_SUBJECTS)),
            ('host', EMAIL_HOST), ('port', int(EMAIL_PORT) if 25 != int(EMAIL_PORT) else None),
            ('tls', int(EMAIL_TLS)),
            ('user', EMAIL_USER), ('password', helpers.encrypt(EMAIL_PASSWORD, ENCRYPTION_VERSION)),
            ('from', EMAIL_FROM),
            ('list', EMAIL_LIST),
        ]),
        # (, [(, )]),
    ])):
        cfg_lc = cfg.lower()
        cfg_keys += [cfg]
        new_config[cfg] = {}
        for (k, v) in filter(lambda arg: any([arg[1]]) or (
                # allow saving where item value default is non-zero but 0 is a required setting value
                cfg_lc in ('kodi', 'xbmc', 'synoindex', 'nzbget', 'torrent', 'telegram')
                and arg[0] in ('always_on', 'priority', 'send_image'))
                or ('rtorrent' == new_config['General']['torrent_method'] and 'label_var' == arg[0]), items):
            k = '%s' in k and (k % cfg_lc) or (cfg_lc + '_' + k)
            # correct for cases where keys are named in an inconsistent manner to parent stanza
            k = k.replace('blackhole_', '').replace('sabnzbd_', 'sab_')
            new_config[cfg].update({k: v})

    for (notifier, onsnatch, ondownload, onsubtitledownload) in [
        ('Kodi', KODI_NOTIFY_ONSNATCH, KODI_NOTIFY_ONDOWNLOAD, KODI_NOTIFY_ONSUBTITLEDOWNLOAD),
        ('Plex', PLEX_NOTIFY_ONSNATCH, PLEX_NOTIFY_ONDOWNLOAD, PLEX_NOTIFY_ONSUBTITLEDOWNLOAD),
        ('XBMC', XBMC_NOTIFY_ONSNATCH, XBMC_NOTIFY_ONDOWNLOAD, XBMC_NOTIFY_ONSUBTITLEDOWNLOAD),
        ('SynologyNotifier', SYNOLOGYNOTIFIER_NOTIFY_ONSNATCH, SYNOLOGYNOTIFIER_NOTIFY_ONDOWNLOAD,
         SYNOLOGYNOTIFIER_NOTIFY_ONSUBTITLEDOWNLOAD),

        ('Boxcar2', BOXCAR2_NOTIFY_ONSNATCH, BOXCAR2_NOTIFY_ONDOWNLOAD, BOXCAR2_NOTIFY_ONSUBTITLEDOWNLOAD),
        ('Pushbullet', PUSHBULLET_NOTIFY_ONSNATCH, PUSHBULLET_NOTIFY_ONDOWNLOAD, PUSHBULLET_NOTIFY_ONSUBTITLEDOWNLOAD),
        ('Pushover', PUSHOVER_NOTIFY_ONSNATCH, PUSHOVER_NOTIFY_ONDOWNLOAD, PUSHOVER_NOTIFY_ONSUBTITLEDOWNLOAD),
        ('Growl', GROWL_NOTIFY_ONSNATCH, GROWL_NOTIFY_ONDOWNLOAD, GROWL_NOTIFY_ONSUBTITLEDOWNLOAD),
        ('Prowl', PROWL_NOTIFY_ONSNATCH, PROWL_NOTIFY_ONDOWNLOAD, PROWL_NOTIFY_ONSUBTITLEDOWNLOAD),
        ('Libnotify', LIBNOTIFY_NOTIFY_ONSNATCH, LIBNOTIFY_NOTIFY_ONDOWNLOAD, LIBNOTIFY_NOTIFY_ONSUBTITLEDOWNLOAD),
        # ('Pushalot', PUSHALOT_NOTIFY_ONSNATCH, PUSHALOT_NOTIFY_ONDOWNLOAD, PUSHALOT_NOTIFY_ONSUBTITLEDOWNLOAD),

        ('Slack', SLACK_NOTIFY_ONSNATCH, SLACK_NOTIFY_ONDOWNLOAD, SLACK_NOTIFY_ONSUBTITLEDOWNLOAD),
        ('Discord', DISCORD_NOTIFY_ONSNATCH, DISCORD_NOTIFY_ONDOWNLOAD, DISCORD_NOTIFY_ONSUBTITLEDOWNLOAD),
        ('Gitter', GITTER_NOTIFY_ONSNATCH, GITTER_NOTIFY_ONDOWNLOAD, GITTER_NOTIFY_ONSUBTITLEDOWNLOAD),
        ('Telegram', TELEGRAM_NOTIFY_ONSNATCH, TELEGRAM_NOTIFY_ONDOWNLOAD, TELEGRAM_NOTIFY_ONSUBTITLEDOWNLOAD),
        ('Email', EMAIL_NOTIFY_ONSNATCH, EMAIL_NOTIFY_ONDOWNLOAD, EMAIL_NOTIFY_ONSUBTITLEDOWNLOAD),
    ]:
        if any([onsnatch, ondownload, onsubtitledownload]):
            if onsnatch:
                new_config[notifier]['%s_notify_onsnatch' % notifier.lower()] = int(onsnatch)
            if ondownload:
                new_config[notifier]['%s_notify_ondownload' % notifier.lower()] = int(ondownload)
            if onsubtitledownload:
                new_config[notifier]['%s_notify_onsubtitledownload' % notifier.lower()] = int(onsubtitledownload)

    # remove empty stanzas
    for k in filter(lambda c: not new_config[c], cfg_keys):
        del new_config[k]

    new_config['Newznab'] = {}
    new_config['Newznab']['newznab_data'] = NEWZNAB_DATA

    torrent_rss = '!!!'.join([x.config_str() for x in torrent_rss_providers])
    if torrent_rss:
        new_config['TorrentRss'] = {}
        new_config['TorrentRss']['torrentrss_data'] = torrent_rss

    new_config['GUI'] = {}
    new_config['GUI']['gui_name'] = GUI_NAME
    new_config['GUI']['theme_name'] = THEME_NAME
    new_config['GUI']['default_home'] = DEFAULT_HOME
    new_config['GUI']['fanart_limit'] = FANART_LIMIT
    new_config['GUI']['fanart_panel'] = FANART_PANEL
    new_config['GUI']['fanart_ratings'] = '%s' % (FANART_RATINGS or {})
    new_config['GUI']['use_imdb_info'] = int(USE_IMDB_INFO)
    new_config['GUI']['imdb_accounts'] = IMDB_ACCOUNTS
    new_config['GUI']['fuzzy_dating'] = int(FUZZY_DATING)
    new_config['GUI']['trim_zero'] = int(TRIM_ZERO)
    new_config['GUI']['date_preset'] = DATE_PRESET
    new_config['GUI']['time_preset'] = TIME_PRESET_W_SECONDS
    new_config['GUI']['timezone_display'] = TIMEZONE_DISPLAY

    new_config['GUI']['show_tags'] = ','.join(SHOW_TAGS)
    new_config['GUI']['showlist_tagview'] = SHOWLIST_TAGVIEW

    new_config['GUI']['home_layout'] = HOME_LAYOUT
    new_config['GUI']['footer_time_layout'] = FOOTER_TIME_LAYOUT
    new_config['GUI']['poster_sortby'] = POSTER_SORTBY
    new_config['GUI']['poster_sortdir'] = POSTER_SORTDIR

    new_config['GUI']['display_show_glide'] = '%s' % (DISPLAY_SHOW_GLIDE or {})
    new_config['GUI']['display_show_glide_slidetime'] = int(DISPLAY_SHOW_GLIDE_SLIDETIME)
    new_config['GUI']['display_show_viewmode'] = int(DISPLAY_SHOW_VIEWMODE)
    new_config['GUI']['display_show_background'] = int(DISPLAY_SHOW_BACKGROUND)
    new_config['GUI']['display_show_background_translucent'] = int(DISPLAY_SHOW_BACKGROUND_TRANSLUCENT)
    new_config['GUI']['display_show_viewart'] = int(DISPLAY_SHOW_VIEWART)
    new_config['GUI']['display_show_minimum'] = int(DISPLAY_SHOW_MINIMUM)
    new_config['GUI']['display_show_specials'] = int(DISPLAY_SHOW_SPECIALS)

    new_config['GUI']['episode_view_viewmode'] = int(EPISODE_VIEW_VIEWMODE)
    new_config['GUI']['episode_view_background'] = int(EPISODE_VIEW_BACKGROUND)
    new_config['GUI']['episode_view_background_translucent'] = int(EPISODE_VIEW_BACKGROUND_TRANSLUCENT)
    new_config['GUI']['episode_view_layout'] = EPISODE_VIEW_LAYOUT
    new_config['GUI']['episode_view_sort'] = EPISODE_VIEW_SORT
    new_config['GUI']['episode_view_display_paused'] = int(EPISODE_VIEW_DISPLAY_PAUSED)
    new_config['GUI']['episode_view_posters'] = int(EPISODE_VIEW_POSTERS)
    new_config['GUI']['episode_view_missed_range'] = int(EPISODE_VIEW_MISSED_RANGE)
    new_config['GUI']['poster_sortby'] = POSTER_SORTBY
    new_config['GUI']['poster_sortdir'] = POSTER_SORTDIR
    new_config['GUI']['show_tags'] = ','.join(SHOW_TAGS)
    new_config['GUI']['showlist_tagview'] = SHOWLIST_TAGVIEW
    new_config['GUI']['show_tag_default'] = SHOW_TAG_DEFAULT
    new_config['GUI']['history_layout'] = HISTORY_LAYOUT
    new_config['GUI']['browselist_hidden'] = '|~|'.join(BROWSELIST_HIDDEN)
    new_config['GUI']['browselist_prefs'] = '%s' % (BROWSELIST_MRU or {})

    new_config['Subtitles'] = {}
    new_config['Subtitles']['use_subtitles'] = int(USE_SUBTITLES)
    new_config['Subtitles']['subtitles_languages'] = ','.join(SUBTITLES_LANGUAGES)
    new_config['Subtitles']['SUBTITLES_SERVICES_LIST'] = ','.join(SUBTITLES_SERVICES_LIST)
    new_config['Subtitles']['SUBTITLES_SERVICES_ENABLED'] = '|'.join([str(x) for x in SUBTITLES_SERVICES_ENABLED])
    new_config['Subtitles']['subtitles_services_auth'] = '|||'.join([':::'.join(a) for a in SUBTITLES_SERVICES_AUTH])
    new_config['Subtitles']['subtitles_dir'] = SUBTITLES_DIR
    new_config['Subtitles']['subtitles_default'] = int(SUBTITLES_DEFAULT)
    new_config['Subtitles']['subtitles_history'] = int(SUBTITLES_HISTORY)
    new_config['Subtitles']['subtitles_finder_interval'] = int(SUBTITLES_FINDER_INTERVAL)
    new_config['Subtitles']['subtitles_os_hash'] = SUBTITLES_OS_HASH

    new_config['FailedDownloads'] = {}
    new_config['FailedDownloads']['use_failed_downloads'] = int(USE_FAILED_DOWNLOADS)
    new_config['FailedDownloads']['delete_failed'] = int(DELETE_FAILED)

    new_config['ANIDB'] = {}
    new_config['ANIDB']['use_anidb'] = int(USE_ANIDB)
    new_config['ANIDB']['anidb_username'] = ANIDB_USERNAME
    new_config['ANIDB']['anidb_password'] = helpers.encrypt(ANIDB_PASSWORD, ENCRYPTION_VERSION)
    new_config['ANIDB']['anidb_use_mylist'] = int(ANIDB_USE_MYLIST)

    new_config['ANIME'] = {}
    new_config['ANIME']['anime_treat_as_hdtv'] = int(ANIME_TREAT_AS_HDTV)

    if not force and CONFIG_OLD == new_config and os.path.isfile(new_config.filename):
        logger.debug('config.ini not dirty, not saving.')
        return
    from sg_helpers import copy_file
    backup_config = re.sub(r'\.ini$', '.bak', CONFIG_FILE)
    from .config import check_valid_config
    try:
        if check_valid_config(CONFIG_FILE):
            for _t in range(0, 3):
                copy_file(CONFIG_FILE, backup_config)
                if not check_valid_config(backup_config):
                    if 2 > _t:
                        logger.debug('backup config file seems to be invalid, retrying...')
                    else:
                        logger.warning('backup config file seems to be invalid, not backing up.')
                        backup_config = None
                    remove_file_perm(backup_config)
                    2 > _t and time.sleep(3)
                else:
                    break
        else:
            logger.warning('existing config file is invalid, not backing it up')
            backup_config = None
    except (BaseException, Exception):
        backup_config = None

    for _t in range(0, 3):
        new_config.write()
        if check_valid_config(CONFIG_FILE):
            CONFIG_OLD = copy.deepcopy(new_config)
            return
        if 2 > _t:
            logger.debug('saving config file failed, retrying...')
        else:
            logger.warning('saving config file failed.')
        remove_file_perm(CONFIG_FILE)
        2 > _t and time.sleep(3)

    # we only get here if the config saving failed multiple times
    if None is not backup_config and os.path.isfile(backup_config):
        logger.error('saving config file failed, using backup file')
        try:
            copy_file(backup_config, CONFIG_FILE)
            logger.log('using old backup config file')
            return
        except (BaseException, Exception):
            logger.error('failed to use backup config file')

    from sg_helpers import scantree
    try:
        target_base = os.path.join(BACKUP_DB_PATH or os.path.join(DATA_DIR, 'backup'))
        file_list = [f for f in scantree(target_base, include='config', filter_kind=False)]
        if file_list:
            logger.log('trying to use latest config.ini backup')
            # sort newest to oldest backup
            file_list.sort(key=lambda _f: _f.stat(follow_symlinks=False).st_mtime)
            import zipfile
            try:
                with zipfile.ZipFile(file_list[0].path, mode='r') as zf:
                    zf.extractall(target_base)
                backup_config_file = os.path.join(target_base, 'config.ini')
                if os.path.isfile(backup_config_file):
                    os.replace(backup_config_file, CONFIG_FILE)
                if check_valid_config(CONFIG_FILE):
                    logger.log(f'used latest config.ini backup file: {file_list[0].name}')
                    return
                else:
                    logger.error(f'failed to use latest config.ini backup file: {file_list[0].name}')
                    remove_file_perm(CONFIG_FILE)
            except (BaseException, Exception):
                pass
            finally:
                try:
                    remove_file_perm(backup_config_file)
                except (BaseException, Exception):
                    pass
            logger.error('failed to use latest config.ini')
    except (BaseException, Exception):
        pass

    logger.error('saving config file failed and no backup available')


def launch_browser(start_port=None):
    if not start_port:
        start_port = WEB_PORT
    browser_url = 'http%s://localhost:%d%s' % (('s', '')[not ENABLE_HTTPS], start_port, WEB_ROOT)
    try:
        webbrowser.open(browser_url, 2, True)
    except (BaseException, Exception):
        try:
            webbrowser.open(browser_url, 1, True)
        except (BaseException, Exception):
            logger.error('Unable to launch a browser')
