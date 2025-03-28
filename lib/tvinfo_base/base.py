import copy
import datetime
import diskcache
import itertools
import logging
import threading
import shutil
import time
from collections import deque
from exceptions_helper import ex

from six import integer_types, iteritems, iterkeys, string_types, text_type
from typing import Callable


from lib.tvinfo_base.exceptions import *
from sg_helpers import calc_age, make_path

# noinspection PyUnreachableCode
if False:
    from typing import Any, AnyStr, Dict, List, Optional, Set, Tuple, Union
    str_int = Union[AnyStr, integer_types]

TVINFO_TVDB = 1
TVINFO_TVRAGE = 2
TVINFO_TVMAZE = 3
TVINFO_TMDB = 4

# old tvdb api - version 1
# TVINFO_TVDB_V1 = 10001

# mapped only source
TVINFO_IMDB = 100
TVINFO_TRAKT = 101
# old tmdb id
TVINFO_TMDB_OLD = 102
# end mapped only source
TVINFO_TVDB_SLUG = 1001
TVINFO_TRAKT_SLUG = 1101

# generic stuff
TVINFO_SLUG = 100000

# social media sources
TVINFO_X = 250000
TVINFO_FACEBOOK = 250001
TVINFO_INSTAGRAM = 250002
TVINFO_WIKIPEDIA = 250003
TVINFO_REDDIT = 250004
TVINFO_YOUTUBE = 250005
TVINFO_WIKIDATA = 250006
TVINFO_TIKTOK = 250007
TVINFO_LINKEDIN = 25008
TVINFO_OFFICIALSITE = 250009
TVINFO_FANSITE = 250010

tv_src_names = {
    TVINFO_TVDB: 'tvdb',
    TVINFO_TVRAGE: 'tvrage',
    TVINFO_TVMAZE: 'tvmaze',

    10001: 'tvdb v1',
    TVINFO_IMDB: 'imdb',
    TVINFO_TRAKT: 'trakt',
    TVINFO_TMDB: 'tmdb',
    TVINFO_TVDB_SLUG: 'tvdb slug',
    TVINFO_TRAKT_SLUG: 'trakt slug',

    TVINFO_SLUG: 'generic slug',

    TVINFO_X: 'twitter',
    TVINFO_FACEBOOK: 'facebook',
    TVINFO_INSTAGRAM: 'instagram',
    TVINFO_WIKIPEDIA: 'wikipedia',
    TVINFO_REDDIT: 'reddit',
    TVINFO_YOUTUBE: 'youtube',
    TVINFO_WIKIDATA: 'wikidata',
    TVINFO_TIKTOK: 'tiktok',
    TVINFO_LINKEDIN: 'linkedin',
    TVINFO_OFFICIALSITE: 'officialsite',
    TVINFO_FANSITE: 'fansite'

}

TVINFO_MID_SEASON_FINALE = 1
TVINFO_SEASON_FINALE = 2
TVINFO_SERIES_FINALE = 3

final_types = {
    TVINFO_MID_SEASON_FINALE: 'mid-season',
    TVINFO_SEASON_FINALE: 'season',
    TVINFO_SERIES_FINALE: 'series'
}

# limit to maximum actors
TVINFO_CAST_LIMIT = 30

log = logging.getLogger('TVInfo')
log.addHandler(logging.NullHandler())
TVInfoShowContainer = {}  # type: Union[ShowContainer, Dict]


class ShowContainer(dict):
    """Simple dict that holds a series of Show instances
    """

    def __init__(self, **kwargs):
        super(ShowContainer, self).__init__(**kwargs)
        # limit caching of TVInfoShow objects to 15 minutes
        self.max_age = 900  # type: integer_types
        self.lock = threading.RLock()

    def __setitem__(self, k, v):
        super(ShowContainer, self).__setitem__(k, (v, time.time()))

    def __getitem__(self, k):
        return super(ShowContainer, self).__getitem__(k)[0]

    def cleanup_old(self):
        """
        remove entries that are older than max_age
        """
        acquired_lock = self.lock.acquire(False)
        if acquired_lock:
            try:
                current_time = time.time()
                for k, v in list(self.items()):
                    if self.max_age < current_time - v[1]:
                        lock_acquired = self[k].lock.acquire(False)
                        if lock_acquired:
                            try:
                                del self[k]
                            except (BaseException, Exception):
                                try:
                                    self[k].lock.release()
                                except RuntimeError:
                                    pass
            finally:
                self.lock.release()

    def __str__(self):
        nr_shows = len(self)
        return '<ShowContainer (containing %s Show%s)>' % (nr_shows, ('s', '')[1 == nr_shows])

    __repr__ = __str__


class TVInfoIDs(object):
    def __init__(
            self,
            tvdb=None,  # type: integer_types
            tmdb=None,  # type: integer_types
            tvmaze=None,  # type: integer_types
            imdb=None,  # type: integer_types
            trakt=None,  # type: integer_types
            rage=None,  # type: integer_types
            ids=None  # type: Dict[int, integer_types]
    ):
        ids = ids or {}
        self.tvdb = tvdb or ids.get(TVINFO_TVDB)
        self.tmdb = tmdb or ids.get(TVINFO_TMDB)
        self.tvmaze = tvmaze or ids.get(TVINFO_TVMAZE)
        self.imdb = imdb or ids.get(TVINFO_IMDB)
        self.trakt = trakt or ids.get(TVINFO_TRAKT)
        self.rage = rage or ids.get(TVINFO_TVRAGE)

    def __getitem__(self, key):
        return {TVINFO_TVDB: self.tvdb, TVINFO_TMDB: self.tmdb, TVINFO_TVMAZE: self.tvmaze,
                TVINFO_IMDB: self.imdb, TVINFO_TRAKT: self.trakt, TVINFO_TVRAGE: self.rage}.get(key)

    def __setitem__(self, key, value):
        self.__dict__[{
            TVINFO_TVDB: 'tvdb', TVINFO_TMDB: 'tmdb', TVINFO_TVMAZE: 'tvmaze',
            TVINFO_IMDB: 'imdb', TVINFO_TRAKT: 'trakt', TVINFO_TVRAGE: 'rage'
        }[key]] = value

    def get(self, key):
        return self.__getitem__(key)

    def keys(self):
        for k, v in iter(((TVINFO_TVDB, self.tvdb), (TVINFO_TMDB, self.tmdb), (TVINFO_TVMAZE, self.tvmaze),
                          (TVINFO_IMDB, self.imdb), (TVINFO_TRAKT, self.trakt), (TVINFO_TVRAGE, self.rage))):
            if None is not v:
                yield k

    def __iter__(self):
        for s, v in iter(((TVINFO_TVDB, self.tvdb), (TVINFO_TMDB, self.tmdb), (TVINFO_TVMAZE, self.tvmaze),
                          (TVINFO_IMDB, self.imdb), (TVINFO_TRAKT, self.trakt), (TVINFO_TVRAGE, self.rage))):
            if None is not v:
                yield s, v

    def __len__(self):
        counter = itertools.count()
        deque(zip(self.__iter__(), counter), maxlen=0)  # (consume at C speed)
        return next(counter)

    def __str__(self):
        return ', '.join('%s: %s' % (tv_src_names.get(k, k), v) for k, v in self.__iter__())

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    __repr__ = __str__
    iteritems = __iter__
    items = __iter__
    iterkeys = keys


class TVInfoSocialIDs(object):
    def __init__(
            self,
            twitter=None,  # type: str_int
            instagram=None,  # type: str_int
            facebook=None,  # type: str_int
            wikipedia=None,  # type: str_int
            ids=None,  # type: Dict[int, str_int]
            reddit=None,  # type: str_int
            youtube=None,  # type: AnyStr
            wikidata=None,  # type: AnyStr
            tiktok=None,  # type: AnyStr
            linkedin=None,  # type: AnyStr
            fansite=None  # type: AnyStr
    ):
        ids = ids or {}
        self.twitter = twitter or ids.get(TVINFO_X)
        self.instagram = instagram or ids.get(TVINFO_INSTAGRAM)
        self.facebook = facebook or ids.get(TVINFO_FACEBOOK)
        self.wikipedia = wikipedia or ids.get(TVINFO_WIKIPEDIA)
        self.reddit = reddit or ids.get(TVINFO_REDDIT)
        self.youtube = youtube or ids.get(TVINFO_YOUTUBE)
        self.wikidata = wikidata or ids.get(TVINFO_WIKIDATA)
        self.tiktok = tiktok or ids.get(TVINFO_TIKTOK)
        self.linkedin = linkedin or ids.get(TVINFO_LINKEDIN)
        self.fansite = fansite or ids.get(TVINFO_FANSITE)

    def __getitem__(self, key):
        return {TVINFO_X: self.twitter, TVINFO_INSTAGRAM: self.instagram, TVINFO_FACEBOOK: self.facebook,
                TVINFO_WIKIDATA: self.wikidata, TVINFO_WIKIPEDIA: self.wikipedia, TVINFO_REDDIT: self.reddit,
                TVINFO_TIKTOK: self.tiktok, TVINFO_LINKEDIN: self.linkedin, TVINFO_FANSITE: self.fansite,
                TVINFO_YOUTUBE: self.youtube}.get(key)

    def __setitem__(self, key, value):
        self.__dict__[{
            TVINFO_X: 'twitter', TVINFO_INSTAGRAM: 'instagram', TVINFO_FACEBOOK: 'facebook',
            TVINFO_WIKIPEDIA: 'wikipedia', TVINFO_REDDIT: 'reddit', TVINFO_YOUTUBE: 'youtube',
            TVINFO_WIKIDATA: 'wikidata', TVINFO_TIKTOK: 'tiktok', TVINFO_LINKEDIN: 'linkedin', TVINFO_FANSITE: 'fansite'
        }[key]] = value

    def get(self, key):
        return self.__getitem__(key)

    def keys(self):
        for k, v in self.__iter__():
            yield k

    def __iter__(self):
        for s, v in iter(((TVINFO_X, self.twitter), (TVINFO_INSTAGRAM, self.instagram),
                          (TVINFO_FACEBOOK, self.facebook), (TVINFO_TIKTOK, self.tiktok),
                          (TVINFO_WIKIPEDIA, self.wikipedia), (TVINFO_WIKIDATA, self.wikidata),
                          (TVINFO_REDDIT, self.reddit), (TVINFO_YOUTUBE, self.youtube),
                          (TVINFO_LINKEDIN, self.linkedin), (TVINFO_FANSITE, self.fansite))):
            if None is not v:
                yield s, v

    def __len__(self):
        counter = itertools.count()
        deque(zip(self.__iter__(), counter), maxlen=0)  # (consume at C speed)
        return next(counter)

    def __str__(self):
        return ', '.join('%s: %s' % (tv_src_names.get(k, k), v) for k, v in self.__iter__())

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    __repr__ = __str__
    iteritems = __iter__
    items = __iter__
    iterkeys = keys


class TVInfoImageType(object):
    poster = 1
    banner = 2
    # fanart/background
    fanart = 3
    typography = 4
    other = 10
    # person
    person_poster = 50
    # season
    season_poster = 100
    season_banner = 101
    season_fanart = 103
    # stills
    still = 200

    reverse_str = {
        poster: 'poster',
        banner: 'banner',
        # fanart/background
        fanart: 'fanart',
        typography: 'typography',
        other: 'other',
        # person
        person_poster: 'person poster',
        # season
        season_poster: 'season poster',
        season_banner: 'season banner',
        season_fanart: 'season fanart',
        # stills
        still: 'still'
    }


class TVInfoImageSize(object):
    original = 1
    medium = 2
    small = 3

    reverse_str = {
        1: 'original',
        2: 'medium',
        3: 'small'
    }


class TVInfoImage(object):
    def __init__(self, image_type, sizes, img_id=None, main_image=False, type_str='', rating=None, votes=None,
                 lang=None, height=None, width=None, aspect_ratio=None, updated_at=None, has_text=None):
        self.img_id = img_id  # type: Optional[integer_types]
        self.image_type = image_type  # type: integer_types
        self.sizes = sizes  # type: Union[TVInfoImageSize, Dict]
        self.type_str = type_str  # type: AnyStr
        self.main_image = main_image  # type: bool
        self.rating = rating  # type: Optional[Union[float, integer_types]]
        self.votes = votes  # type: Optional[integer_types]
        self.lang = lang  # type: Optional[AnyStr]
        self.height = height  # type: Optional[integer_types]
        self.width = width  # type: Optional[integer_types]
        self.aspect_ratio = aspect_ratio  # type: Optional[Union[float, integer_types]]
        self.has_text = has_text  # type: Optional[bool]
        self.updated_at = updated_at  # type: Optional[integer_types]

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __str__(self):
        return '<TVInfoImage %s [%s]>' % (TVInfoImageType.reverse_str.get(self.image_type, 'unknown'),
                                          ', '.join(TVInfoImageSize.reverse_str.get(s, 'unknown') for s in self.sizes))

    __repr__ = __str__


class TVInfoNetwork(object):
    def __init__(self, name, n_id=None, country=None, country_code=None, timezone=None, stream=None, active_date=None,
                 inactive_date=None):
        # type: (AnyStr, integer_types, AnyStr, AnyStr, AnyStr, bool, AnyStr, AnyStr) -> None
        self.name = name  # type: AnyStr
        self.id = n_id  # type: Optional[integer_types]
        self.country = country  # type: Optional[AnyStr]
        self.country_code = country_code  # type: Optional[AnyStr]
        self.timezone = timezone  # type: Optional[AnyStr]
        self.stream = stream  # type: Optional[bool]
        self.active_date = active_date  # type: Optional[AnyStr]
        self.inactive_date = inactive_date  # type: Optional[AnyStr]

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __str__(self):
        return '<Network (%s)>' % ', '.join('%s' % s for s in [self.name, self.id, self.country, self.country_code,
                                                               self.timezone] if s)

    __repr__ = __str__


class TVInfoShow(dict):
    """Holds a dict of seasons, and show data.
    """

    def __init__(self, show_loaded=True):
        dict.__init__(self)
        self.lock = threading.RLock()
        self.data = {}  # type: Dict
        self.ep_loaded = False  # type: bool
        self.poster_loaded = False  # type: bool
        self.banner_loaded = False  # type: bool
        self.fanart_loaded = False  # type: bool
        self.season_images_loaded = False  # type: bool
        self.seasonwide_images_loaded = False  # type: bool
        self.actors_loaded = False  # type: bool
        self.show_not_found = False  # type: bool
        self.id = None  # type: integer_types
        self.ids = TVInfoIDs()  # type: TVInfoIDs
        self.social_ids = TVInfoSocialIDs()  # type: TVInfoSocialIDs
        self.slug = None  # type: Optional[AnyStr]
        self.seriesname = None  # type: Optional[AnyStr]
        self.aliases = []  # type: List[AnyStr]
        self.season = None  # type: integer_types
        self.classification = None  # type: Optional[AnyStr]
        self.genre = None  # type: Optional[AnyStr]
        self.genre_list = []  # type: List[AnyStr]
        self.actors = []  # type: List[Dict]
        self.cast = CastList()  # type: CastList
        self.crew = CrewList()  # type: CrewList
        self.show_type = []  # type: List[AnyStr]
        self.networks = []  # type: List[TVInfoNetwork]
        self.network = None  # type: Optional[AnyStr]
        self.network_id = None  # type: integer_types
        self.network_timezone = None  # type: Optional[AnyStr]
        self.network_country = None  # type: Optional[AnyStr]
        self.network_country_code = None  # type: Optional[AnyStr]
        self.network_is_stream = None  # type: Optional[bool]
        self.runtime = None  # type: integer_types
        self.language = None  # type: Optional[AnyStr]
        self.spoken_languages = []  # type: List[string_types]
        self.official_site = None  # type: Optional[AnyStr]
        self.imdb_id = None  # type: Optional[AnyStr]
        self.zap2itid = None  # type: Optional[AnyStr]
        self.airs_dayofweek = None  # type: Optional[AnyStr]
        self.airs_time = None  # type: Optional[AnyStr]
        self.time = None  # type: Optional[datetime.time]
        self.firstaired = None  # type: Optional[AnyStr]
        self.added = None  # type: Optional[AnyStr]
        self.addedby = None  # type: Union[integer_types, AnyStr]
        self.siteratingcount = None  # type: integer_types
        self.lastupdated = None  # type: integer_types
        self.contentrating = None  # type: Optional[AnyStr]
        self.rating = None  # type: Union[integer_types, float]
        self.status = None  # type: Optional[AnyStr]
        self.overview = ''  # type: AnyStr
        self.poster = None  # type: Optional[AnyStr]
        self.poster_thumb = None  # type: Optional[AnyStr]
        self.banner = None  # type: Optional[AnyStr]
        self.banner_thumb = None  # type: Optional[AnyStr]
        self.fanart = None  # type: Optional[AnyStr]
        self.banners = {}  # type: Dict
        self.images = {}  # type: Dict[TVInfoImageType, List[TVInfoImage]]
        self.updated_timestamp = None  # type: Optional[integer_types]
        # special properties for trending, popular, ...
        self.popularity = None  # type: Optional[Union[integer_types, float]]
        self.vote_count = None  # type: Optional[integer_types]
        self.vote_average = None  # type: Optional[Union[integer_types, float]]
        self.origin_countries = []  # type: List[AnyStr]
        self.requested_language = ''  # type: AnyStr
        self.alt_ep_numbering = {}  # type: Dict[Any, Dict[integer_types, Dict[integer_types, TVInfoEpisode]]]
        self.watcher_count = None  # type: integer_types
        self.play_count = None  # type: integer_types
        self.collected_count = None  # type: integer_types
        self.collector_count = None  # type: integer_types
        self.next_season_airdate = None  # type: Optional[string_types]
        # trailers dict containing: {language: trailer url} , 'any' for unknown langauge
        self.trailers = {}  # type: Dict[string_types, string_types]
        self.show_loaded = show_loaded  # type: bool
        self.load_method = None  # type: Optional[Callable]

    def load_data(self):
        if not self.show_loaded and self.id and isinstance(self.load_method, Callable):
            _new_show_data = self.load_method(self.id, load_actors=False)
            if isinstance(_new_show_data, TVInfoShow):
                self.__dict__.update(_new_show_data.__dict__)
                self.show_loaded = True

    @property
    def seriesid(self):
        # type: (...) -> integer_types
        return self.id

    @seriesid.setter
    def seriesid(self, val):
        # type: (integer_types) -> None
        self.id = val

    def __str__(self):
        nr_seasons = len(self)
        return '<Show %r (containing %s season%s)>' % (self.seriesname, nr_seasons, ('s', '')[1 == nr_seasons])

    def __getattr__(self, key):
        if key in self:
            # Key is an episode, return it
            return self[key]

        if key in self.data:
            # Non-numeric request is for show-data
            return self.data[key]

        raise AttributeError

    def __getitem__(self, key):
        if isinstance(key, string_types) and key in self.__dict__:
            return self.__dict__[key]

        if key in self:
            # Key is an episode, return it
            return dict.__getitem__(self, key)

        if key in self.data:
            # Non-numeric request is for show-data
            return dict.__getitem__(self.data, key)

        # Data wasn't found, raise appropriate error
        if isinstance(key, integer_types) or isinstance(key, string_types) and key.isdigit():
            # Episode number x was not found
            raise BaseTVinfoSeasonnotfound('Could not find season %s' % (repr(key)))
        else:
            # If it's not numeric, it must be an attribute name, which
            # doesn't exist, so attribute error.
            raise BaseTVinfoAttributenotfound('Cannot find attribute %s' % (repr(key)))

    def get(self, __key, *args):
        try:
            return self.__getitem__(__key)
        except (BaseException, Exception):
            if 0 != len(args):
                return args[0]

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if 'lock' == k:
                setattr(result, k, threading.RLock())
            elif 'load_method' == k:
                setattr(result, k, None)
            else:
                setattr(result, k, copy.deepcopy(v, memo))
        for k, v in self.items():
            result[k] = copy.deepcopy(v, memo)
            if isinstance(k, integer_types):
                setattr(result[k], 'show', result)
        return result

    def __bool__(self):
        # type: (...) -> bool
        return bool(self.id) or any(iterkeys(self.data))

    def to_dict(self):
        return self.__dict__.copy()

    def aired_on(self, date):
        ret = self.search(str(date), 'firstaired')
        if 0 == len(ret):
            raise BaseTVinfoEpisodenotfound('Could not find any episodes that aired on %s' % date)
        return ret

    def search(self, term=None, key=None):
        """
        Search all episodes in show. Can search all data, or a specific key (for
        example, episodename)

        Always returns an array (can be empty). First index contains the first
        match, and so on.
        """
        results = []
        for cur_season in self.values():
            searchresult = cur_season.search(term=term, key=key)
            if 0 != len(searchresult):
                results.extend(searchresult)

        return results

    def __getstate__(self):
        d = dict(self.__dict__)
        for d_a in ('lock', 'load_method'):
            try:
                del d[d_a]
            except (BaseException, Exception):
                pass
        return d

    def __setstate__(self, d):
        self.__dict__ = d
        self.lock = threading.RLock()
        self.load_method = None

    __repr__ = __str__
    __nonzero__ = __bool__


class TVInfoSeason(dict):
    def __init__(self, show=None, number=None, **kwargs):
        """The show attribute points to the parent show
        """
        super(TVInfoSeason, self).__init__(**kwargs)
        self.show = show  # type: TVInfoShow
        self.id = None  # type: integer_types
        self.number = number  # type: integer_types
        self.name = None  # type: Optional[AnyStr]
        self.actors = []  # type: List[Dict]
        self.cast = CastList()  # type: Dict[integer_types, TVInfoCharacter]
        self.network = None  # type: Optional[AnyStr]
        self.network_id = None  # type: Optional[integer_types]
        self.network_timezone = None  # type: Optional[AnyStr]
        self.network_country = None  # type: Optional[AnyStr]
        self.network_country_code = None  # type: Optional[AnyStr]
        self.network_is_stream = None  # type: Optional[bool]
        self.ordered = None  # type: Optional[integer_types]
        self.start_date = None  # type: Optional[AnyStr]
        self.end_date = None  # type: Optional[AnyStr]
        self.poster = None  # type: Optional[AnyStr]
        self.summery = None  # type: Optional[AnyStr]
        self.episode_order = None  # type: Optional[integer_types]

    def __str__(self):
        nr_episodes = len(self)
        return '<Season %s instance (containing %s episode%s)>' % \
               (self.number, nr_episodes, ('s', '')[1 == nr_episodes])

    def __getattr__(self, episode_number):
        if episode_number in self:
            return self[episode_number]
        raise AttributeError

    def __getitem__(self, episode_number):
        if episode_number not in self:
            raise BaseTVinfoEpisodenotfound('Could not find episode %s' % (repr(episode_number)))
        else:
            return dict.__getitem__(self, episode_number)

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            # noinspection PyArgumentList
            setattr(result, k, copy.deepcopy(v, memo))
        for k, v in self.items():
            result[k] = copy.deepcopy(v, memo)
            if isinstance(k, integer_types):
                setattr(result[k], 'season', result)
        return result

    def search(self, term=None, key=None):
        """Search all episodes in season, returns a list of matching Episode
        instances.
        """
        results = []
        for ep in self.values():
            searchresult = ep.search(term=term, key=key)
            if None is not searchresult:
                results.append(searchresult)
        return results

    __repr__ = __str__


class TVInfoEpisode(dict):
    def __init__(self, season=None, show=None, **kwargs):
        """The season attribute points to the parent season
        """
        super(TVInfoEpisode, self).__init__(**kwargs)
        self.id = None  # type: integer_types
        self.seriesid = None  # type: integer_types
        self.season = season  # type: TVInfoSeason
        self.seasonnumber = None  # type: integer_types
        self.episodenumber = None  # type: integer_types
        self.absolute_number = None  # type: integer_types
        self.is_special = None  # type: Optional[bool]
        self.actors = []  # type: List[Dict]
        self.gueststars = None  # type: Optional[AnyStr]
        self.gueststars_list = []  # type: List[AnyStr]
        self.cast = CastList()  # type: Dict[integer_types, TVInfoCharacter]
        self.directors = []  # type: List[AnyStr]
        self.writer = None  # type: Optional[AnyStr]
        self.writers = []  # type: List[AnyStr]
        self.crew = CrewList()  # type: CrewList
        self.episodename = None  # type: Optional[AnyStr]
        self.overview = ''  # type: AnyStr
        self.language = {'episodeName': None, 'overview': None}  # type: Dict[AnyStr, Optional[AnyStr]]
        self.productioncode = None  # type: Optional[AnyStr]
        self.showurl = None  # type: Optional[AnyStr]
        self.lastupdated = None  # type: integer_types
        self.dvddiscid = None  # type: Optional[AnyStr]
        self.dvd_season = None  # type: integer_types
        self.dvd_episodenumber = None  # type: integer_types
        self.dvdchapter = None  # type: integer_types
        self.firstaired = None  # type: Optional[AnyStr]
        self.airtime = None  # type: Optional[datetime.time]
        self.runtime = 0  # type: integer_types
        self.timestamp = None  # type: Optional[integer_types]
        self.network = None  # type: Optional[AnyStr]
        self.network_id = None  # type: integer_types
        self.network_timezone = None  # type: Optional[AnyStr]
        self.network_country = None  # type: Optional[AnyStr]
        self.network_country_code = None  # type: Optional[AnyStr]
        self.network_is_stream = None  # type: Optional[bool]
        self.filename = None  # type: Optional[AnyStr]
        self.lastupdatedby = None  # type: Union[integer_types, AnyStr]
        self.airsafterseason = None  # type: integer_types
        self.airsbeforeseason = None  # type: integer_types
        self.airsbeforeepisode = None  # type: integer_types
        self.imdb_id = None  # type: Optional[AnyStr]
        self.contentrating = None  # type: Optional[AnyStr]
        self.thumbadded = None  # type: Optional[AnyStr]
        self.rating = None  # type: Union[integer_types, float]
        self.vote_count = None  # type: integer_types
        self.siteratingcount = None  # type: integer_types
        self.show = show  # type: Optional[TVInfoShow]
        self.alt_nums = {}  # type: Dict[AnyStr, Dict[integer_types, integer_types]]
        self.finale_type = None  # type: Optional[integer_types]

    def __str__(self):
        show_name = (self.show and self.show.seriesname and '<Show  %s> - ' % self.show.seriesname) or ''
        seasno, epno = int(getattr(self, 'seasonnumber', 0) or 0), int(getattr(self, 'episodenumber', 0) or 0)
        epname = getattr(self, 'episodename', '')
        finale_str = (self.finale_type and ' (%s finale)' % final_types.get(self.finale_type).capitalize()) or ''
        if None is not epname:
            return '%s<Episode %02dx%02d - %r%s>' % (show_name, seasno, epno, epname, finale_str)
        else:
            return '%s<Episode %02dx%02d%s>' % (show_name, seasno, epno, finale_str)

    def __getattr__(self, key):
        if key in self:
            return self[key]
        raise AttributeError

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            raise BaseTVinfoAttributenotfound('Cannot find attribute %s' % (repr(key)))

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            # noinspection PyArgumentList
            setattr(result, k, copy.deepcopy(v, memo))
        for k, v in self.items():
            result[k] = copy.deepcopy(v, memo)
        return result

    def __bool__(self):
        # type: (...) -> bool
        return bool(self.id) or bool(self.episodename)

    def search(self, term=None, key=None):
        """Search episode data for term, if it matches, return the Episode (self).
        The key parameter can be used to limit the search to a specific element,
        for example, episodename.
        """
        if None is term:
            raise TypeError('must supply string to search for (contents)')

        term = text_type(term).lower()
        for cur_key, cur_value in iteritems(self):
            cur_key, cur_value = text_type(cur_key).lower(), text_type(cur_value).lower()
            if None is not key and cur_key != key:
                # Do not search this key
                continue
            if cur_value.find(text_type(term).lower()) > -1:
                return self

    __unicode__ = __str__
    __repr__ = __str__
    __nonzero__ = __bool__


class Persons(dict):
    """Holds all Persons instances for a show
    """
    def __str__(self):
        persons_count = len(self)
        return '<Persons (containing %s Person%s)>' % (persons_count, ('', 's')[1 != persons_count])

    __repr__ = __str__


class CastList(Persons):
    def __init__(self, **kwargs):
        super(CastList, self).__init__(**kwargs)
        for t in iterkeys(RoleTypes.reverse):
            if t < RoleTypes.crew_limit:
                self[t] = []  # type: List[TVInfoCharacter]

    def __str__(self):
        persons_count = []
        for t in iterkeys(RoleTypes.reverse):
            if t < RoleTypes.crew_limit:
                if len(self.get(t, [])):
                    persons_count.append('%s: %s' % (RoleTypes.reverse[t], len(self.get(t, []))))
        persons_text = ', '.join(persons_count)
        persons_text = ('0', '(%s)' % persons_text)['' != persons_text]
        return '<Cast (containing %s Person%s)>' % (persons_text, ('', 's')['' != persons_text])

    __repr__ = __str__


class CrewList(Persons):
    def __init__(self, **kwargs):
        super(CrewList, self).__init__(**kwargs)
        for t in iterkeys(RoleTypes.reverse):
            if t >= RoleTypes.crew_limit:
                self[t] = []  # type: List[Crew]

    def __str__(self):
        persons_count = []
        for t in iterkeys(RoleTypes.reverse):
            if t >= RoleTypes.crew_limit:
                if len(self.get(t, [])):
                    persons_count.append('%s: %s' % (RoleTypes.reverse[t], len(self.get(t, []))))
        persons_text = ', '.join(persons_count)
        persons_text = ('0', '(%s)' % persons_text)['' != persons_text]
        return '<Crew (containing %s Person%s)>' % (persons_text, ('', 's')['' != persons_text])

    __repr__ = __str__


class PersonBase(dict):
    """Represents a single person. Should contain..

    id,
    image,
    name,
    role,
    sortorder
    """
    def __init__(
            self,
            p_id=None,  # type: integer_types
            name=None,  # type: AnyStr
            image=None,  # type: AnyStr
            images=None,  # type: List[TVInfoImage]
            gender=None,  # type: integer_types
            bio=None,  # type: AnyStr
            birthdate=None,  # type: datetime.date
            deathdate=None,  # type: datetime.date
            country=None,  # type: AnyStr
            country_code=None,  # type: AnyStr
            country_timezone=None,  # type: AnyStr
            ids=None,  # type: TVInfoIDs
            thumb_url=None,  # type: AnyStr
            **kwargs  # type: Dict
    ):
        super(PersonBase, self).__init__(**kwargs)
        self.id = p_id  # type: Optional[integer_types]
        self.name = name  # type: Optional[AnyStr]
        self.image = image  # type: Optional[AnyStr]
        self.images = images or []  # type: List[TVInfoImage]
        self.thumb_url = thumb_url  # type: Optional[AnyStr]
        self.gender = gender  # type: Optional[int]
        self.bio = bio  # type: Optional[AnyStr]
        self.birthdate = birthdate  # type: Optional[datetime.date]
        self.deathdate = deathdate  # type: Optional[datetime.date]
        self.country = country  # type: Optional[AnyStr]
        self.country_code = country_code  # type: Optional[AnyStr]
        self.country_timezone = country_timezone  # type: Optional[AnyStr]
        self.ids = ids or TVInfoIDs()  # type: TVInfoIDs

    def calc_age(self, date=None):
        # type: (Optional[datetime.date]) -> Optional[int]
        return calc_age(self.birthdate, self.deathdate, date)

    @property
    def age(self):
        # type: (...) -> Optional[int]
        """
        :return: age of person if birthdate is known, in case of deathdate is known return age of death
        """
        return self.calc_age()

    def __bool__(self):
        # type: (...) -> bool
        return bool(self.name)

    def __str__(self):
        return '<Person "%s">' % self.name

    __repr__ = __str__
    __nonzero__ = __bool__


class PersonGenders(object):
    unknown = 0
    male = 1
    female = 2

    named = {'unknown': 0, 'male': 1, 'female': 2}
    reverse = {v: k for k, v in iteritems(named)}
    tmdb_map = {0: unknown, 1: female, 2: male}
    imdb_map = {'female': female, 'male': male}
    tvdb_map = {0: unknown, 1: male, 2: female, 3: unknown}  # 3 is technically: other
    trakt_map = {'female': female, 'male': male}


class Crew(PersonBase):

    def __init__(self, crew_type_name=None, **kwargs):
        super(Crew, self).__init__(**kwargs)
        self.crew_type_name = crew_type_name

    def __str__(self):
        return '<Crew%s "%s)">' % (('', ('/%s' % self.crew_type_name))[isinstance(self.crew_type_name, string_types)],
                                   self.name)

    __repr__ = __str__


class TVInfoPerson(PersonBase):
    def __init__(
            self,
            p_id=None,  # type: integer_types
            name=None,  # type: AnyStr
            image=None,  # type: Optional[AnyStr]
            images=None,  # type: List[TVInfoImage]
            thumb_url=None,  # type: AnyStr
            gender=None,  # type: integer_types
            bio=None,  # type: AnyStr
            birthdate=None,  # type: datetime.date
            deathdate=None,  # type: datetime.date
            country=None,  # type: AnyStr
            country_code=None,  # type: AnyStr
            country_timezone=None,  # type: AnyStr
            ids=None,  # type: TVInfoIDs
            homepage=None,  # type: Optional[AnyStr]
            social_ids=None,  # type: TVInfoSocialIDs
            birthplace=None,  # type: AnyStr
            deathplace=None,  # type: AnyStr
            url=None,  # type: AnyStr
            characters=None,  # type: List[TVInfoCharacter]
            height=None,  # type: Union[integer_types, float]
            nicknames=None,  # type: Set[AnyStr]
            real_name=None,  # type: AnyStr
            akas=None,  # type: Set[AnyStr]
            **kwargs  # type: Dict
    ):
        super(TVInfoPerson, self).__init__(
            p_id=p_id, name=name, image=image, thumb_url=thumb_url, bio=bio, gender=gender,
            birthdate=birthdate, deathdate=deathdate, country=country, images=images,
            country_code=country_code, country_timezone=country_timezone, ids=ids, **kwargs)
        self.credits = []  # type: List
        self.homepage = homepage  # type: Optional[AnyStr]
        self.social_ids = social_ids or TVInfoSocialIDs()  # type: TVInfoSocialIDs
        self.birthplace = birthplace  # type: Optional[AnyStr]
        self.deathplace = deathplace  # type: Optional[AnyStr]
        self.nicknames = nicknames or set()  # type: Set[AnyStr]
        self.real_name = real_name  # type: AnyStr
        self.url = url  # type: Optional[AnyStr]
        self.height = height  # type: Optional[Union[integer_types, float]]
        self.akas = akas or set()  # type: Set[AnyStr]
        self.characters = characters or []  # type: List[TVInfoCharacter]

    def __str__(self):
        return '<Person "%s">' % self.name

    __repr__ = __str__


class TVInfoCharacter(PersonBase):
    def __init__(self,
                 person=None,  # type: List[TVInfoPerson]
                 voice=None,  # type: bool
                 plays_self=None,  # type: bool
                 regular=None,  # type: bool
                 ti_show=None,  # type: TVInfoShow
                 start_year=None,  # type: int
                 end_year=None,  # type: int
                 ids=None,  # type: TVInfoIDs
                 name=None,  # type: AnyStr
                 episode_count=None,  # type: int
                 guest_episodes_numbers=None,  # type: Dict[int, List[int]]
                 **kwargs):
        # type: (...) -> None

        super(TVInfoCharacter, self).__init__(ids=ids, **kwargs)
        self.person = person  # type: List[TVInfoPerson]
        self.voice = voice  # type: Optional[bool]
        self.plays_self = plays_self  # type: Optional[bool]
        self.regular = regular  # type: Optional[bool]
        self.ti_show = ti_show  # type: Optional[TVInfoShow]
        self.start_year = start_year  # type: Optional[integer_types]
        self.end_year = end_year  # type: Optional[integer_types]
        self.name = name  # type: Optional[AnyStr]
        self.episode_count = episode_count  # type: Optional[int]
        self.guest_episodes_numbers = guest_episodes_numbers or {}  # type: Dict[int, List[int]]

    def __str__(self):
        pn = []
        char_type = ('', ' [Guest]')[False is self.regular]
        char_show = None is not self.ti_show and ' [%s]' % self.ti_show.seriesname
        if None is not self.person:
            for p in self.person:
                if getattr(p, 'name', None):
                    pn.append(p.name)
        return '<Character%s "%s%s%s">' % (char_type, self.name, ('', ' - (%s)' % ', '.join(pn))[bool(pn)], char_show)

    __repr__ = __str__


class RoleTypes(object):
    # Actor types
    ActorMain = 1
    ActorRecurring = 2
    ActorGuest = 3
    ActorSpecialGuest = 4
    Host = 10
    HostGuest = 11
    Presenter = 12
    PresenterGuest = 13
    Interviewer = 14
    InterviewerGuest = 15
    MusicalGuest = 16
    # Crew types (int's >= crew_limit)
    CrewDirector = 50
    CrewWriter = 51
    CrewProducer = 52
    CrewExecutiveProducer = 53
    CrewCreator = 60
    CrewEditor = 61
    CrewCamera = 62
    CrewMusic = 63
    CrewStylist = 64
    CrewMakeup = 65
    CrewPhotography = 66
    CrewSound = 67
    CrewDesigner = 68
    CrewDeveloper = 69
    CrewAnimation = 70
    CrewVisualEffects = 71
    CrewShowrunner = 72
    CrewOther = 100

    reverse = {1: 'Main', 2: 'Recurring', 3: 'Guest', 4: 'Special Guest', 10: 'Host', 11: 'Host Guest',
               12: 'Presenter', 13: 'Presenter Guest', 14: 'Interviewer', 15: 'Interviewer Guest',
               16: 'Musical Guest', 50: 'Director', 51: 'Writer', 52: 'Producer', 53: 'Executive Producer',
               60: 'Creator', 61: 'Editor', 62: 'Camera', 63: 'Music', 64: 'Stylist', 65: 'Makeup',
               66: 'Photography', 67: 'Sound', 68: 'Designer', 69: 'Developer', 70: 'Animation',
               71: 'Visual Effects', 72: 'Showrunner', 100: 'Other'}
    crew_limit = 50

    # just a helper to generate the reverse data
    # def __init__(self):
    #     import re
    #     {value: re.sub(r'([a-z])([A-Z])', r'\1 \2', name.replace('Actor', '').replace('Crew', ''))
    #      for name, value in iteritems(vars(RoleTypes)) if not name.startswith('_')
    #      and name not in ('reverse', 'crew_limit')}


crew_type_names = {c.lower(): v for v, c in iteritems(RoleTypes.reverse) if v >= RoleTypes.crew_limit}


class TVInfoSeasonTypes(object):
    default = 'default'
    official = 'official'
    dvd = 'dvd'


class TVInfoBase(object):
    supported_id_searches = []
    supported_person_id_searches = []
    _supported_languages = None
    map_languages = {'cs': 'ces', 'da': 'dan', 'de': 'deu', 'en': 'eng', 'es': 'spa', 'fi': 'fin', 'fr': 'fra',
                     'he': 'heb', 'hr': 'hrv', 'hu': 'hun', 'it': 'ita', 'ja': 'jpn', 'ko': 'kor', 'nb': 'nor',
                     'nl': 'nld', 'no': 'nor',
                     'pl': 'pol', 'pt': 'pot', 'ru': 'rus', 'sk': 'slv', 'sv': 'swe', 'zh': 'zho', '_1': 'srp'}
    reverse_map_languages = {v: k for k, v in iteritems(map_languages)}

    def __init__(self, banners=False, posters=False, seasons=False, seasonwides=False, fanart=False, actors=False,
                 dvdorder=False, *args, **kwargs):
        global TVInfoShowContainer
        if self.__class__.__name__ not in TVInfoShowContainer:
            TVInfoShowContainer[self.__class__.__name__] = ShowContainer()
        self.ti_shows = TVInfoShowContainer[self.__class__.__name__]  # type: ShowContainer[integer_types, TVInfoShow]
        self.ti_shows.cleanup_old()
        self.lang = None  # type: Optional[AnyStr]
        self.corrections = {}  # type: Dict
        self.show_not_found = False  # type: bool
        self.not_found = False  # type: bool
        self._old_config = None
        self._cachedir = kwargs.get('diskcache_dir')  # type: AnyStr
        self.diskcache = diskcache.Cache(directory=self._cachedir, disk_pickle_protocol=2)  # type: diskcache.Cache
        self.cache_expire = 60 * 60 * 18  # type: integer_types
        self.search_cache_expire = 60 * 15  # type: integer_types
        self.schedule_cache_expire = 60 * 30  # type: integer_types
        self.config = {
            'apikey': '',
            'debug_enabled': False,
            'custom_ui': None,
            'proxy': None,
            'cache_enabled': False,
            'cache_location': '',
            'valid_languages': [],
            'langabbv_to_id': {},
            'language': 'en',
            'base_url': '',
            'banners_enabled': banners,
            'posters_enabled': posters,
            'seasons_enabled': seasons,
            'seasonwides_enabled': seasonwides,
            'fanart_enabled': fanart,
            'actors_enabled': actors,
            'cache_search': kwargs.get('cache_search'),
            'dvdorder': dvdorder,
        }  # type: Dict[AnyStr, Any]

    def _must_load_data(self, sid, load_episodes, banners, posters, seasons, seasonwides, fanart, actors, lang):
        # type: (integer_types, bool, bool, bool, bool, bool, bool, bool, str) -> bool
        """
        returns if show data has to be fetched for (extra) data (episodes, images, ...)
        or can taken from self.shows cache
        :param sid: show id
        :param load_episodes: should episodes be loaded
        :param banners: should load banners
        :param posters: should load posters
        :param seasons: should load season images
        :param seasonwides: should load season wide images
        :param fanart: should load fanart
        :param actors: should load actors
        :param lang: requested language
        """
        if sid not in self.ti_shows or None is self.ti_shows[sid].id or \
                (load_episodes and not getattr(self.ti_shows[sid], 'ep_loaded', False)):
            return True
        _show = self.ti_shows[sid]  # type: TVInfoShow
        if _show.requested_language != lang:
            _show.ep_loaded = _show.poster_loaded = _show.banner_loaded = _show.actors_loaded = _show.fanart_loaded = \
                _show.seasonwide_images_loaded = _show.season_images_loaded = False
            return True
        for data_type, en_type, p_type in [(u'poster', 'posters_enabled', posters),
                                           (u'banner', 'banners_enabled', banners),
                                           (u'fanart', 'fanart_enabled', fanart),
                                           (u'season', 'seasons_enabled', seasons),
                                           (u'seasonwide', 'seasonwides_enabled', seasonwides),
                                           (u'actors', 'actors_enabled', actors)]:
            if (p_type or self.config.get(en_type, False)) and \
                    not getattr(_show, '%s_loaded' % data_type, False):
                return True
        return False

    def clear_cache(self):
        """
        Clear cache.
        """
        try:
            with self.diskcache as dc:
                dc.clear()
        except (BaseException, Exception):
            pass

    def clean_cache(self):
        """
        Remove expired items from cache.
        """
        try:
            with self.diskcache as dc:
                dc.expire()
        except (BaseException, Exception):
            pass

    def check_cache(self):
        """
        checks cache
        """
        try:
            with self.diskcache as dc:
                dc.check()
        except (BaseException, Exception):
            pass

    def _get_cache_entry(self, key, retry=False):
        # type: (Any, bool) -> Tuple[bool, Any]
        """
        returns tuple of is_None and value
        :param key:
        :param retry:
        """
        with self.diskcache as dc:
            try:
                v = dc.get(key)
                return 'None' == v, (v, None)['None' == v]
            except ValueError as e:
                if not retry:
                    dc.close()
                    try:
                        shutil.rmtree(self._cachedir)
                    except (BaseException, Exception) as e:
                        log.error(ex(e))
                        pass
                    try:
                        make_path(self._cachedir)
                    except (BaseException, Exception):
                        pass
                    return self._get_cache_entry(key, retry=True)
                else:
                    log.error('Error getting %s from cache: %s' % (key, ex(e)))
            except (BaseException, Exception) as e:
                log.error('Error getting %s from cache: %s' % (key, ex(e)))
        return False, None

    def _set_cache_entry(self, key, value, tag=None, expire=None):
        # type: (Any, Any, AnyStr, int) -> None
        try:
            with self.diskcache as dc:
                dc.set(key, (value, 'None')[None is value], expire=expire or self.cache_expire, tag=tag)
        except (BaseException, Exception) as e:
            log.error('Error setting %s to cache: %s' % (key, ex(e)))

    def get_person(self, p_id, get_show_credits=False, get_images=False, include_guests=False, **kwargs):
        # type: (integer_types, bool, bool, bool, Any) -> Optional[TVInfoPerson]
        """
        get person's data for id or list of matching persons for name

        :param p_id: persons id
        :param get_show_credits: get show credits
        :param get_images: get person images
        :param include_guests: include guest roles
        :return: person object
        """
        pass

    def _search_person(self, name=None, ids=None):
        # type: (AnyStr, Dict[integer_types, integer_types]) -> List[TVInfoPerson]
        """
        search by name for person
        :param name: name to search for
        :param ids: dict of ids to search
        :return: list of found person's
        """
        return []

    def search_person(self, name=None, ids=None):
        # type: (AnyStr, Dict[integer_types, integer_types]) -> List[TVInfoPerson]
        """
        search by name for person
        :param name: name to search for
        :param ids: dict of ids to search
        :return: list of found person's
        """
        if not name and not ids:
            log.debug('Nothing to search')
            raise BaseTVinfoPersonNotFound('Nothing to search')
        found_persons = []
        if ids:
            if not any(1 for i in ids if i in self.supported_person_id_searches) and not name:
                log.debug('Id type not supported')
                raise BaseTVinfoPersonNotFound('Id type not supported')
            found_persons = self._search_person(name=name, ids=ids)
        elif name:
            found_persons = self._search_person(name=name, ids=ids)
        return found_persons

    def _get_show_data(self, sid, language, get_ep_info=False, banners=False, posters=False, seasons=False,
                       seasonwides=False, fanart=False, actors=False, **kwargs):
        # type: (integer_types, AnyStr, bool, bool, bool, bool, bool, bool, bool, Optional[Any]) -> bool
        """
        internal function that should be overwritten in subclass to get data
        :param sid: show id to get data for
        :param language: language
        :param get_ep_info: get episodes
        :param banners: load banners
        :param posters: load posters
        :param seasons: load seasons
        :param seasonwides: load seasonwides
        :param fanart: load fanard
        :param actors: load actors
        """
        pass

    def get_show(
            self,
            show_id,  # type: integer_types
            load_episodes=True,  # type: bool
            banners=False,  # type: bool
            posters=False,  # type: bool
            seasons=False,  # type: bool
            seasonwides=False,  # type: bool
            fanart=False,  # type: bool
            actors=False,  # type: bool
            old_call=False,  # type: bool
            language=None,  # type: AnyStr
            # **kwargs  # type: dict
    ):
        # type: (...) -> Optional[TVInfoShow]
        """
        get data for show id

        :param show_id: id of show
        :param load_episodes: load episodes
        :param banners: load banners
        :param posters: load posters
        :param seasons: load season images
        :param seasonwides: load season wide images
        :param fanart: load fanart
        :param actors: load actors
        :param old_call: load legacy call
        :param language: set the request language
        :return: show object
        """
        if not old_call and None is self._old_config:
            self._old_config = self.config.copy()
            self.config.update({'banners_enabled': banners, 'posters_enabled': posters, 'seasons_enabled': seasons,
                                'seasonwides_enabled': seasonwides, 'fanart_enabled': fanart, 'actors_enabled': actors,
                                'language': language or 'en'})
        self.ti_shows.lock.acquire()
        try:
            if show_id not in self.ti_shows:
                self.ti_shows[show_id] = TVInfoShow()  # type: TVInfoShow
            with self.ti_shows[show_id].lock:
                self.ti_shows.lock.release()
                try:
                    if self._must_load_data(show_id, load_episodes, banners, posters, seasons, seasonwides, fanart,
                                            actors, self.config['language']):
                        self.ti_shows[show_id].requested_language = self.config['language']
                        self._get_show_data(show_id, self.map_languages.get(self.config['language'],
                                                                            self.config['language']),
                                            load_episodes, banners, posters, seasons, seasonwides, fanart, actors)
                        if None is self.ti_shows[show_id].id:
                            with self.ti_shows.lock:
                                del self.ti_shows[show_id]
                    if show_id not in self.ti_shows:
                        return None
                    else:
                        show_copy = copy.deepcopy(self.ti_shows[show_id])  # type: TVInfoShow
                        # provide old call compatibility for dvd order
                        if self.config.get('dvdorder') and TVInfoSeasonTypes.dvd in show_copy.alt_ep_numbering:
                            org_seasons, dvd_seasons = list(show_copy), \
                                                       list(show_copy.alt_ep_numbering[TVInfoSeasonTypes.dvd])
                            for r_season in set(org_seasons) - set(dvd_seasons):
                                try:
                                    del show_copy[r_season]
                                except (BaseException, Exception):
                                    continue
                            for ti_season in dvd_seasons:
                                show_copy[ti_season] = show_copy.alt_ep_numbering[TVInfoSeasonTypes.dvd][ti_season]
                        return show_copy
                finally:
                    try:
                        if None is self.ti_shows[show_id].id:
                            with self.ti_shows.lock:
                                del self.ti_shows[show_id]
                    except (BaseException, Exception):
                        pass
        finally:
            try:
                self.ti_shows.lock.release()
            except RuntimeError:
                pass
            if not old_call and None is not self._old_config:
                self.config = self._old_config
                self._old_config = None

    # noinspection PyMethodMayBeStatic
    def _search_show(self,
                     name=None,  # type: Union[AnyStr, List[AnyStr]]
                     ids=None,  # type: Dict[integer_types, integer_types]
                     lang=None,  # type: Optional[string_types]
                     **kwargs):
        # type: (...) -> List[Dict]
        """
        internal search function to find shows, should be overwritten in class
        :param name: name to search for
        :param ids: dict of ids {tvid: prodid} to search for
        :param lang: language code
        """
        return []

    @staticmethod
    def _convert_search_names(name):
        if name:
            names = ([name], name)[isinstance(name, list)]
            for i, n in enumerate(names):
                if not isinstance(n, string_types):
                    names[i] = text_type(n)
                names[i] = names[i].lower()
            return names
        return name

    def search_show(
            self,
            name=None,  # type: Union[AnyStr, List[AnyStr]]
            ids=None,  # type: Dict[integer_types, integer_types]
            lang=None,  # type: Optional[string_types]
            # **kwargs  # type: Optional[Any]
    ):
        # type: (...) -> List[Dict]
        """
        search for series with name(s) or ids

        :param name: series name or list of names to search for
        :param ids: dict of ids {tvid: prodid} to search for
        :param lang: language code
        :return: combined list of series results
        """
        if None is lang:
            if self.config.get('language'):
                lang = self.config['language']
        lang = self.map_languages.get(lang, lang)
        if not name and not ids:
            log.debug('Nothing to search')
            raise BaseTVinfoShownotfound('Nothing to search')
        name, selected_series = self._convert_search_names(name), []
        if ids:
            if not name and not any(1 for i in ids if i in self.supported_id_searches):
                log.debug('Id type not supported')
                raise BaseTVinfoShownotfound('Id type not supported')
            selected_series = self._search_show(name=name, ids=ids, lang=lang)
        elif name:
            selected_series = self._search_show(name, lang=lang)
        if isinstance(selected_series, dict):
            selected_series = [selected_series]
        if not isinstance(selected_series, list) or 0 == len(selected_series):
            log.debug('Series result returned zero')
            raise BaseTVinfoShownotfound('Show-name search returned zero results (cannot find show on %s)' %
                                         self.__class__.__name__)
        return selected_series

    def _set_item(self, sid, seas, ep, attrib, value):
        # type: (integer_types, integer_types, integer_types, integer_types, Any, Any) -> None
        """Creates a new episode, creating Show(), Season() and
        Episode()s as required. Called by _get_show_data to populate show

        Since the nice-to-use tvinfo[1][24]['name] interface
        makes it impossible to do tvinfo[1][24]['name] = "name"
        and still be capable of checking if an episode exists
        so that we can raise tvinfo_shownotfound, we have a slightly
        less pretty method of setting items... but since the API
        is supposed to be read-only, this is the best way to
        do it!
        The problem is that calling tvinfo[1][24]['episodename'] = "name"
        calls __getitem__ on tvinfo[1], there is no way to check if
        tvinfo.__dict__ should have a key "1" before we auto-create it
        """
        # if sid not in self.ti_shows:
        #     self.ti_shows[sid] = TVInfoShow()
        if seas not in self.ti_shows[sid]:
            self.ti_shows[sid][seas] = TVInfoSeason(show=self.ti_shows[sid])
            self.ti_shows[sid][seas].number = seas
        if ep not in self.ti_shows[sid][seas]:
            self.ti_shows[sid][seas][ep] = TVInfoEpisode(season=self.ti_shows[sid][seas], show=self.ti_shows[sid])
        if attrib not in ('cast', 'crew'):
            self.ti_shows[sid][seas][ep][attrib] = value
        self.ti_shows[sid][seas][ep].__dict__[attrib] = value

    def _set_show_data(self, sid, key, value, add=False):
        # type: (integer_types, Any, Any, bool) -> None
        """Sets self.ti_shows[sid] to a new Show instance, or sets the data
        """
        # if sid not in self.ti_shows:
        #     self.ti_shows[sid] = TVInfoShow()
        if key not in ('cast', 'crew'):
            if add and isinstance(self.ti_shows[sid].data, dict) and key in self.ti_shows[sid].data:
                self.ti_shows[sid].data[key].update(value)
            else:
                self.ti_shows[sid].data[key] = value
            if '_banners' == key:
                p_key = 'banners'
            else:
                p_key = key
            if add and key in self.ti_shows[sid].__dict__ and isinstance(self.ti_shows[sid].__dict__[p_key], dict):
                self.ti_shows[sid].__dict__[p_key].update(self.ti_shows[sid].data[key])
            else:
                self.ti_shows[sid].__dict__[p_key] = self.ti_shows[sid].data[key]
        else:
            if add and key in self.ti_shows[sid].__dict__ and isinstance(self.ti_shows[sid].__dict__[key], dict):
                self.ti_shows[sid].__dict__[key].update(value)
            else:
                self.ti_shows[sid].__dict__[key] = value

    def get_updated_shows(self):
        # type: (...) -> Dict[integer_types, integer_types]
        """
        gets all ids and timestamp of updated shows
        returns dict of id: timestamp
        """
        return {}

    def get_similar(self, tvid, result_count=100, **kwargs):
        # type: (integer_types, int, Any) -> List[TVInfoShow]
        """
        return list of similar shows to given id

        :param tvid: id to give similar shows for
        :param result_count: count of results requested
        """
        return []

    def get_recommended_for_show(self, tvid, result_count=100, **kwargs):
        # type: (integer_types, int, Any) -> List[TVInfoShow]
        """
        list of recommended shows to the provided tv id

        :param tvid: id to find recommended shows for
        :param result_count: result count to returned
        """
        return []

    def get_trending(self, result_count=100, **kwargs):
        # type: (...) -> List[TVInfoShow]
        """
        get trending shows
        :param result_count:
        """
        return []

    def get_popular(self, result_count=100, **kwargs):
        # type: (...) -> List[TVInfoShow]
        """
        get all popular shows
        """
        return []

    def get_top_rated(self, result_count=100, **kwargs):
        # type: (...) -> List[TVInfoShow]
        """
        get top-rated shows
        """
        return []

    def get_new_shows(self, result_count=100, **kwargs):
        # type: (...) -> List[TVInfoShow]
        """
        get new shows
        """
        return []

    def get_new_seasons(self, result_count=100, **kwargs):
        # type: (...) -> List[TVInfoShow]
        """
        get new seasons
        """
        return []

    def discover(self, result_count=100, get_extra_images=False, **kwargs):
        # type: (...) -> List[TVInfoShow]
        return []

    def get_premieres(self, **kwargs):
        # type: (...) -> List[TVInfoShow]
        """
        get all premiering shows
        """
        return []

    def get_returning(self, **kwargs):
        # type: (...) -> List[TVInfoShow]
        """
        get all returning shows
        """
        return []

    def get_most_played(self, result_count=100, **kwargs):
        # type: (...) -> List[TVInfoShow]
        """
        get most played shows
        :param result_count: how many results are supposed to be returned
        """
        return []

    def get_most_watched(self, result_count=100, **kwargs):
        # type: (...) -> List[TVInfoShow]
        """
        get most watched shows
        :param result_count: how many results are supposed to be returned
        """
        return []

    def get_most_collected(self, result_count=100, **kwargs):
        # type: (...) -> List[TVInfoShow]
        """
        get most collected shows
        :param result_count: how many results are supposed to be returned
        """
        return []

    def get_recommended(self, result_count=100, **kwargs):
        # type: (...) -> List[TVInfoShow]
        """
        get most recommended shows
        :param result_count: how many results are supposed to be returned
        """
        return []

    def get_recommended_for_account(self, account, result_count=100, **kwargs):
        # type: (...) -> List[TVInfoShow]
        """
        get recommended shows for account

        :param account: account to get recommendations for
        :param result_count: how many results are supposed to be returned
        """
        return []

    def hide_recommended_for_account(self, account, show_ids, **kwargs):
        # type: (integer_types, List[integer_types], Any) -> List[integer_types]
        """
        hide recommended show for account

        :param account: account to get recommendations for
        :param show_ids: list of show_ids to no longer recommend for account
        :return: list of added ids
        """
        return []

    def unhide_recommended_for_account(self, account, show_ids, **kwargs):
        # type: (integer_types, List[integer_types], Any) -> List[integer_types]
        """
        unhide recommended show for account

        :param account: account to get recommendations for
        :param show_ids: list of show_ids to be included in possible recommend for account
        :return: list of removed ids
        """
        return []

    def list_hidden_recommended_for_account(self, account, **kwargs):
        # type: (integer_types, Any) -> List[TVInfoShow]
        """
        list hidden recommended show for account

        :param account: account to get recommendations for
        :return: list of hidden shows
        """
        return []

    def get_watchlisted_for_account(self, account, result_count=100, **kwargs):
        # type: (...) -> List[TVInfoShow]
        """
        get most watchlisted shows for account

        :param account: account to get recommendations for
        :param result_count: how many results are supposed to be returned
        """
        return []

    def get_anticipated(self, result_count=100, **kwargs):
        # type: (...) -> List[TVInfoShow]
        """
        get anticipated shows
        :param result_count: how many results are supposed to be returned
        """
        return []

    def __getitem__(self, item):
        # type: (Union[AnyStr, integer_types, Tuple[integer_types, bool]]) -> Union[TVInfoShow, List[Dict], None]
        """Legacy handler (use get_show or search_show instead)
        Handles class_instance['seriesname'] calls.
        The dict index should be the show id
        """
        arg = None
        if isinstance(item, tuple) and 2 == len(item):
            item, arg = item
            if not isinstance(arg, bool):
                arg = None

        if isinstance(item, integer_types):
            # Item is integer, treat as show id
            return self.get_show(item, (True, arg)[None is not arg], old_call=True)

        # maybe adding this to make callee use showname so that I can bring in the new endpoint
        if isinstance(arg, string_types) and 'Tvdb' == self.__class__.__name__:
            return self.search_show(item)

        return self.search_show(item)

    # noinspection PyMethodMayBeStatic
    def search(self, series):
        # type: (AnyStr) -> List
        """This searches for the series name
        and returns the result list
        """
        return []

    @staticmethod
    def _which_type(img_width, img_ratio):
        # type: (integer_types, Union[integer_types, float]) -> Optional[int]
        """

        :param img_width:
        :param img_ratio:
        """

        msg_success = 'Treating image as %s with extracted aspect ratio'
        # most posters are around 0.68 width/height ratio (eg. 680/1000)
        # noinspection DuplicatedCode
        if 0.55 <= img_ratio <= 0.8:
            log.debug(msg_success % 'poster')
            return TVInfoImageType.poster

        # most banners are around 5.4 width/height ratio (eg. 758/140)
        if 5 <= img_ratio <= 6:
            log.debug(msg_success % 'banner')
            return TVInfoImageType.banner

        # most fan art are around 1.7 width/height ratio (eg. 1280/720 or 1920/1080)
        if 1.7 <= img_ratio <= 1.8:
            if 500 < img_width:
                log.debug(msg_success % 'fanart')
                return TVInfoImageType.fanart

            log.warning(u'Skipped image with fanart aspect ratio but less than 500 pixels wide')
        else:
            log.warning(u'Skipped image with useless ratio %s' % img_ratio)

    def _get_languages(self):
        # type: (...) -> None
        """
        overwrite in class to create the language lists
        """
        pass

    def get_languages(self):
        # type: (...) -> List[Dict]
        """
        get all supported languages as list of dicts
        [{'id': 'lang code', 'name': 'english name', 'nativeName': 'native name', 'sg_lang': 'sg lang code'}]
        """
        if not self._supported_languages:
            self._get_languages()
        return self._supported_languages or []

    def __str__(self):
        return '<TVInfo(%s) (containing: %s)>' % (self.__class__.__name__, text_type(self.ti_shows))

    __repr__ = __str__
