# encoding:utf-8
# author:Prinz23
# project:tvmaze_api

__author__ = 'Prinz23'
__version__ = '1.0'
__api_version__ = '1.0.0'

import datetime
import logging
import re

import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from _23 import filter_iter
from six import integer_types, iteritems, string_types
from sg_helpers import get_url, try_int
from lib.dateutil.parser import parser
# noinspection PyProtectedMember
from lib.dateutil.tz.tz import _datetime_to_timestamp
from lib.exceptions_helper import ConnectionSkipException, ex
# from .tvmaze_exceptions import *
from lib.tvinfo_base import TVInfoBase, TVInfoImage, TVInfoImageSize, TVInfoImageType, Character, Crew, \
    crew_type_names, Person, RoleTypes, TVInfoShow, TVInfoEpisode, TVInfoIDs, TVInfoSeason, PersonGenders, \
    TVINFO_TVMAZE, TVINFO_TVDB, TVINFO_IMDB
from lib.pytvmaze import tvmaze

# noinspection PyUnreachableCode
if False:
    from typing import Any, AnyStr, Dict, List, Optional
    from lib.pytvmaze.tvmaze import Episode as TVMazeEpisode, Show as TVMazeShow

log = logging.getLogger('tvmaze.api')
log.addHandler(logging.NullHandler())


# Query TVmaze free endpoints
def tvmaze_endpoint_standard_get(url):
    s = requests.Session()
    retries = Retry(total=5,
                    backoff_factor=0.1,
                    status_forcelist=[429])
    # noinspection HttpUrlsUsage
    s.mount('http://', HTTPAdapter(max_retries=retries))
    s.mount('https://', HTTPAdapter(max_retries=retries))
    # noinspection PyProtectedMember
    return get_url(url, json=True, session=s, hooks={'response': tvmaze._record_hook}, raise_skip_exception=True)


tvmaze.TVmaze.endpoint_standard_get = staticmethod(tvmaze_endpoint_standard_get)
tvm_obj = tvmaze.TVmaze()
empty_ep = TVInfoEpisode()
empty_se = TVInfoSeason()
tz_p = parser()

img_type_map = {
    'poster': TVInfoImageType.poster,
    'banner': TVInfoImageType.banner,
    'background': TVInfoImageType.fanart,
    'typography': TVInfoImageType.typography,
}

img_size_map = {
    'original': TVInfoImageSize.original,
    'medium': TVInfoImageSize.medium,
}

show_map = {
    'id': 'maze_id',
    'ids': 'externals',
    # 'slug': '',
    'seriesid': 'maze_id',
    'seriesname': 'name',
    'aliases': 'akas',
    # 'season': '',
    'classification': 'type',
    # 'genre': '',
    'genre_list': 'genres',
    # 'actors': '',
    # 'cast': '',
    # 'show_type': '',
    # 'network': 'network',
    # 'network_id': '',
    # 'network_timezone': '',
    # 'network_country': '',
    # 'network_country_code': '',
    # 'network_is_stream': '',
    # 'runtime': 'runtime',
    'language': 'language',
    'official_site': 'official_site',
    # 'imdb_id': '',
    # 'zap2itid': '',
    # 'airs_dayofweek': '',
    # 'airs_time': '',
    # 'time': '',
    'firstaired': 'premiered',
    # 'added': '',
    # 'addedby': '',
    # 'siteratingcount': '',
    # 'lastupdated': '',
    # 'contentrating': '',
    'rating': 'rating',
    'status': 'status',
    'overview': 'summary',
    # 'poster': 'image',
    # 'poster_thumb': '',
    # 'banner': '',
    # 'banner_thumb': '',
    # 'fanart': '',
    # 'banners': '',
    'updated_timestamp': 'updated',
}
season_map = {
    'id': 'id',
    'number': 'season_number',
    'name': 'name',
    # 'actors': '',
    # 'cast': '',
    # 'network': '',
    # 'network_id': '',
    # 'network_timezone': '',
    # 'network_country': '',
    # 'network_country_code': '',
    # 'network_is_stream': '',
    'ordered': '',
    'start_date': 'premiere_date',
    'end_date': 'end_date',
    # 'poster': '',
    'summery': 'summary',
    'episode_order': 'episode_order',
}


class TvMaze(TVInfoBase):
    supported_id_searches = [TVINFO_TVMAZE, TVINFO_TVDB, TVINFO_IMDB]
    supported_person_id_searches = [TVINFO_TVMAZE]

    def __init__(self, *args, **kwargs):
        super(TvMaze, self).__init__(*args, **kwargs)

    def _search_show(self, name=None, ids=None, **kwargs):
        def _make_result_dict(s):
            return {'seriesname': s.name, 'id': s.id, 'firstaired': s.premiered,
                    'network': (s.network and s.network.name) or (s.web_channel and s.web_channel.name),
                    'genres': isinstance(s.genres, list) and ', '.join(g.lower() for g in s.genres) or s.genres,
                    'overview': s.summary, 'language': s.language, 'runtime': s.average_runtime or s.runtime,
                    'type': s.type, 'schedule': s.schedule, 'status': s.status, 'official_site': s.official_site,
                    'aliases': [a.name for a in s.akas], 'image': s.image and s.image.get('original'),
                    'ids': TVInfoIDs(
                        tvdb=s.externals.get('thetvdb'), rage=s.externals.get('tvrage'), tvmaze=s.id,
                        imdb=s.externals.get('imdb') and try_int(s.externals.get('imdb').replace('tt', ''), None))}
        results = []
        if ids:
            for t, p in iteritems(ids):
                if t in self.supported_id_searches:
                    cache_id_key = 's-id-%s-%s' % (t, ids[t])
                    is_none, shows = self._get_cache_entry(cache_id_key)
                    if t == TVINFO_TVDB:
                        if not self.config.get('cache_search') or (None is shows and not is_none):
                            try:
                                show = tvmaze.lookup_tvdb(p)
                                self._set_cache_entry(cache_id_key, show, expire=self.search_cache_expire)
                            except (BaseException, Exception):
                                continue
                        else:
                            show = shows
                    elif t == TVINFO_IMDB:
                        if not self.config.get('cache_search') or (None is shows and not is_none):
                            try:
                                show = tvmaze.lookup_imdb((p, 'tt%07d' % p)[not str(p).startswith('tt')])
                                self._set_cache_entry(cache_id_key, show, expire=self.search_cache_expire)
                            except (BaseException, Exception):
                                continue
                        else:
                            show = shows
                    elif t == TVINFO_TVMAZE:
                        if not self.config.get('cache_search') or (None is shows and not is_none):
                            try:
                                show = tvm_obj.get_show(maze_id=p)
                                self._set_cache_entry(cache_id_key, show, expire=self.search_cache_expire)
                            except (BaseException, Exception):
                                continue
                        else:
                            show = shows
                    else:
                        continue
                    if show:
                        try:
                            if show.id not in [i['id'] for i in results]:
                                results.append(_make_result_dict(show))
                        except (BaseException, Exception) as e:
                            log.debug('Error creating result dict: %s' % ex(e))
        if name:
            for n in ([name], name)[isinstance(name, list)]:
                cache_name_key = 's-name-%s' % n
                is_none, shows = self._get_cache_entry(cache_name_key)
                if not self.config.get('cache_search') or (None is shows and not is_none):
                    try:
                        shows = tvmaze.show_search(n)
                    except (BaseException, Exception) as e:
                        log.debug('Error searching for show: %s' % ex(e))
                        continue
                results.extend([_make_result_dict(s) for s in shows or []])

        seen = set()
        results = [seen.add(r['id']) or r for r in results if r['id'] not in seen]
        return results

    def _set_episode(self, sid, ep_obj):
        for _k, _s in (
                ('seasonnumber', 'season_number'), ('episodenumber', 'episode_number'),
                ('episodename', 'title'), ('overview', 'summary'), ('firstaired', 'airdate'),
                ('airtime', 'airtime'), ('runtime', 'runtime'),
                ('seriesid', 'maze_id'), ('id', 'maze_id'), ('is_special', 'special'), ('filename', 'image')):
            if 'filename' == _k:
                image = getattr(ep_obj, _s, {}) or {}
                image = image.get('original') or image.get('medium')
                self._set_item(sid, ep_obj.season_number, ep_obj.episode_number, _k, image)
            else:
                self._set_item(sid, ep_obj.season_number, ep_obj.episode_number, _k,
                               getattr(ep_obj, _s, getattr(empty_ep, _k)))

        if ep_obj.airstamp:
            try:
                at = _datetime_to_timestamp(tz_p.parse(ep_obj.airstamp))
                self._set_item(sid, ep_obj.season_number, ep_obj.episode_number, 'timestamp', at)
            except (BaseException, Exception):
                pass

    @staticmethod
    def _set_network(show_obj, network, is_stream):
        show_obj['network'] = network.name
        show_obj['network_timezone'] = network.timezone
        show_obj['network_country'] = network.country
        show_obj['network_country_code'] = network.code
        show_obj['network_id'] = network.maze_id
        show_obj['network_is_stream'] = is_stream

    def _get_tvm_show(self, show_id, get_ep_info):
        try:
            self.show_not_found = False
            return tvm_obj.get_show(maze_id=show_id, embed='cast%s' % ('', ',episodeswithspecials')[get_ep_info])
        except tvmaze.ShowNotFound:
            self.show_not_found = True
        except (BaseException, Exception):
            log.debug('Error getting data for tvmaze show id: %s' % show_id)

    def _get_show_data(self, sid, language, get_ep_info=False, banners=False, posters=False, seasons=False,
                       seasonwides=False, fanart=False, actors=False, **kwargs):
        log.debug('Getting all series data for %s' % sid)

        show_data = self._get_tvm_show(sid, get_ep_info)
        if not show_data:
            return False

        show_obj = self.shows[sid].__dict__
        for k, v in iteritems(show_obj):
            if k not in ('cast', 'crew', 'images'):
                show_obj[k] = getattr(show_data, show_map.get(k, k), show_obj[k])
        show_obj['runtime'] = show_data.average_runtime or show_data.runtime
        p_set = False
        if show_data.image:
            p_set = True
            show_obj['poster'] = show_data.image.get('original')
            show_obj['poster_thumb'] = show_data.image.get('medium')

        if (banners or posters or fanart or
                any(self.config.get('%s_enabled' % t, False) for t in ('banners', 'posters', 'fanart'))) and \
                not all(getattr(self.shows[sid], '%s_loaded' % t, False) for t in ('poster', 'banner', 'fanart')):
            if show_data.images:
                b_set, f_set = False, False
                self.shows[sid].poster_loaded = True
                self.shows[sid].banner_loaded = True
                self.shows[sid].fanart_loaded = True
                for img in show_data.images:
                    img_type = img_type_map.get(img.type, TVInfoImageType.other)
                    img_width, img_height = img.resolutions['original'].get('width'), \
                        img.resolutions['original'].get('height')
                    img_ar = img_width and img_height and float(img_width) / float(img_height)
                    img_ar_type = self._which_type(img_width, img_ar)
                    if TVInfoImageType.poster == img_type and img_ar and img_ar_type != img_type and \
                            show_obj['poster'] == img.resolutions.get('original')['url']:
                        p_set = False
                        show_obj['poster'] = None
                        show_obj['poster_thumb'] = None
                    img_type = (TVInfoImageType.other, img_type)[
                        not img_ar or img_ar_type == img_type or
                        img_type not in (TVInfoImageType.banner, TVInfoImageType.poster, TVInfoImageType.fanart)]
                    img_src = {}
                    for res, img_url in iteritems(img.resolutions):
                        img_size = img_size_map.get(res)
                        if img_size:
                            img_src[img_size] = img_url.get('url')
                    show_obj['images'].setdefault(img_type, []).append(
                        TVInfoImage(
                            image_type=img_type, sizes=img_src, img_id=img.id, main_image=img.main,
                            type_str=img.type, width=img_width, height=img_height, aspect_ratio=img_ar))
                    if not p_set and TVInfoImageType.poster == img_type:
                        p_set = True
                        show_obj['poster'] = img.resolutions.get('original')['url']
                        show_obj['poster_thumb'] = img.resolutions.get('original')['url']
                    elif not b_set and 'banner' == img.type and TVInfoImageType.banner == img_type:
                        b_set = True
                        show_obj['banner'] = img.resolutions.get('original')['url']
                        show_obj['banner_thumb'] = img.resolutions.get('medium')['url']
                    elif not f_set and 'background' == img.type and TVInfoImageType.fanart == img_type:
                        f_set = True
                        show_obj['fanart'] = img.resolutions.get('original')['url']

        if show_data.schedule:
            if 'time' in show_data.schedule:
                show_obj['airs_time'] = show_data.schedule['time']
                try:
                    h, m = show_data.schedule['time'].split(':')
                    h, m = try_int(h, None), try_int(m, None)
                    if None is not h and None is not m:
                        show_obj['time'] = datetime.time(hour=h, minute=m)
                except (BaseException, Exception):
                    pass
            if 'days' in show_data.schedule:
                show_obj['airs_dayofweek'] = ', '.join(show_data.schedule['days'])
        if show_data.genres:
            show_obj['genre'] = '|%s|' % '|'.join(show_data.genres).lower()

        if (actors or self.config['actors_enabled']) and not getattr(self.shows.get(sid), 'actors_loaded', False):
            if show_data.cast:
                character_person_ids = {}
                for ch in show_obj['cast'][RoleTypes.ActorMain]:
                    character_person_ids.setdefault(ch.id, []).extend([p.id for p in ch.person])
                for ch in show_data.cast.characters:
                    existing_character = next((c for c in show_obj['cast'][RoleTypes.ActorMain] if c.id == ch.id),
                                              None)  # type: Optional[Character]
                    person = self._convert_person(ch.person)
                    if existing_character:
                        existing_person = next((p for p in existing_character.person
                                                if person.id == p.ids.get(TVINFO_TVMAZE)),
                                               None)  # type: Person
                        if existing_person:
                            try:
                                character_person_ids[ch.id].remove(existing_person.id)
                            except (BaseException, Exception):
                                print('error')
                                pass
                            (existing_person.p_id, existing_person.name, existing_person.image, existing_person.gender,
                             existing_person.birthdate, existing_person.deathdate, existing_person.country,
                             existing_person.country_code, existing_person.country_timezone, existing_person.thumb_url,
                             existing_person.url, existing_person.ids) = \
                                (ch.person.id, ch.person.name,
                                 ch.person.image and ch.person.image.get('original'),
                                 PersonGenders.named.get(
                                     ch.person.gender and ch.person.gender.lower(), PersonGenders.unknown),
                                 person.birthdate, person.deathdate,
                                 ch.person.country and ch.person.country.get('name'),
                                 ch.person.country and ch.person.country.get('code'),
                                 ch.person.country and ch.person.country.get('timezone'),
                                 ch.person.image and ch.person.image.get('medium'),
                                 ch.person.url, {TVINFO_TVMAZE: ch.person.id})
                        else:
                            existing_character.person.append(person)
                    else:
                        show_obj['cast'][RoleTypes.ActorMain].append(
                            Character(p_id=ch.id, name=ch.name, image=ch.image and ch.image.get('original'),
                                      person=[person],
                                      plays_self=ch.plays_self, thumb_url=ch.image and ch.image.get('medium')
                                      ))

                if character_person_ids:
                    for c, p_ids in iteritems(character_person_ids):
                        if p_ids:
                            char = next((mc for mc in show_obj['cast'][RoleTypes.ActorMain] if mc.id == c),
                                        None)  # type: Optional[Character]
                            if char:
                                char.person = [p for p in char.person if p.id not in p_ids]

                if show_data.cast:
                    show_obj['actors'] = [
                        {'character': {'id': ch.id,
                                       'name': ch.name,
                                       'url': 'https://www.tvmaze.com/character/view?id=%s' % ch.id,
                                       'image': ch.image and ch.image.get('original'),
                                       },
                         'person': {'id': ch.person and ch.person.id,
                                    'name': ch.person and ch.person.name,
                                    'url': ch.person and 'https://www.tvmaze.com/person/view?id=%s' % ch.person.id,
                                    'image': ch.person and ch.person.image and ch.person.image.get('original'),
                                    'birthday': None,  # not sure about format
                                    'deathday': None,  # not sure about format
                                    'gender': ch.person and ch.person.gender and ch.person.gender,
                                    'country': ch.person and ch.person.country and ch.person.country.get('name'),
                                    },
                         } for ch in show_data.cast.characters]

            if show_data.crew:
                for cw in show_data.crew:
                    rt = crew_type_names.get(cw.type.lower(), RoleTypes.CrewOther)
                    show_obj['crew'][rt].append(
                        Crew(p_id=cw.person.id, name=cw.person.name,
                             image=cw.person.image and cw.person.image.get('original'),
                             gender=cw.person.gender, birthdate=cw.person.birthday, deathdate=cw.person.death_day,
                             country=cw.person.country and cw.person.country.get('name'),
                             country_code=cw.person.country and cw.person.country.get('code'),
                             country_timezone=cw.person.country and cw.person.country.get('timezone'),
                             crew_type_name=cw.type,
                             )
                    )

        if show_data.externals:
            show_obj['ids'] = TVInfoIDs(tvdb=show_data.externals.get('thetvdb'),
                                        rage=show_data.externals.get('tvrage'),
                                        imdb=show_data.externals.get('imdb') and
                                        try_int(show_data.externals.get('imdb').replace('tt', ''), None))

        if show_data.network:
            self._set_network(show_obj, show_data.network, False)
        elif show_data.web_channel:
            self._set_network(show_obj, show_data.web_channel, True)

        if get_ep_info and not getattr(self.shows.get(sid), 'ep_loaded', False):
            log.debug('Getting all episodes of %s' % sid)
            if None is show_data:
                show_data = self._get_tvm_show(sid, get_ep_info)
                if not show_data:
                    return False

            if show_data.episodes:
                specials = []
                for cur_ep in show_data.episodes:
                    if cur_ep.is_special():
                        specials.append(cur_ep)
                    else:
                        self._set_episode(sid, cur_ep)

                if specials:
                    specials.sort(key=lambda ep: ep.airstamp or 'Last')
                    for ep_n, cur_sp in enumerate(specials, start=1):
                        cur_sp.season_number, cur_sp.episode_number = 0, ep_n
                        self._set_episode(sid, cur_sp)

            if show_data.seasons:
                for cur_s_k, cur_s_v in iteritems(show_data.seasons):
                    season_obj = None
                    if cur_s_v.season_number not in self.shows[sid]:
                        if all(_e.is_special() for _e in cur_s_v.episodes or []):
                            season_obj = self.shows[sid][0].__dict__
                        else:
                            log.error('error episodes have no numbers')
                    season_obj = season_obj or self.shows[sid][cur_s_v.season_number].__dict__
                    for k, v in iteritems(season_map):
                        season_obj[k] = getattr(cur_s_v, v, None) or empty_se.get(v)
                    if cur_s_v.network:
                        self._set_network(season_obj, cur_s_v.network, False)
                    elif cur_s_v.web_channel:
                        self._set_network(season_obj, cur_s_v.web_channel, True)
                    if cur_s_v.image:
                        season_obj['poster'] = cur_s_v.image.get('original')
                self.shows[sid].season_images_loaded = True

            self.shows[sid].ep_loaded = True

        return True

    def get_updated_shows(self):
        # type: (...) -> Dict[integer_types, integer_types]
        return {sid: v.seconds_since_epoch for sid, v in iteritems(tvmaze.show_updates().updates)}

    @staticmethod
    def _convert_person(person_obj):
        # type: (tvmaze.Person) -> Person
        ch = []
        for c in person_obj.castcredits or []:
            show = TVInfoShow()
            show.seriesname = c.show.name
            show.id = c.show.id
            show.firstaired = c.show.premiered
            show.ids = TVInfoIDs(ids={TVINFO_TVMAZE: show.id})
            show.overview = c.show.summary
            show.status = c.show.status
            net = c.show.network or c.show.web_channel
            show.network = net.name
            show.network_id = net.maze_id
            show.network_country = net.country
            show.network_timezone = net.timezone
            show.network_country_code = net.code
            show.network_is_stream = None is not c.show.web_channel
            ch.append(Character(name=c.character.name, show=show))
        try:
            birthdate = person_obj.birthday and tz_p.parse(person_obj.birthday).date()
        except (BaseException, Exception):
            birthdate = None
        try:
            deathdate = person_obj.death_day and tz_p.parse(person_obj.death_day).date()
        except (BaseException, Exception):
            deathdate = None
        return Person(p_id=person_obj.id, name=person_obj.name,
                      image=person_obj.image and person_obj.image.get('original'),
                      gender=PersonGenders.named.get(person_obj.gender and person_obj.gender.lower(),
                                                     PersonGenders.unknown),
                      birthdate=birthdate, deathdate=deathdate,
                      country=person_obj.country and person_obj.country.get('name'),
                      country_code=person_obj.country and person_obj.country.get('code'),
                      country_timezone=person_obj.country and person_obj.country.get('timezone'),
                      thumb_url=person_obj.image and person_obj.image.get('medium'),
                      url=person_obj.url, ids={TVINFO_TVMAZE: person_obj.id}, characters=ch
                      )

    def _search_person(self, name=None, ids=None):
        # type: (AnyStr, Dict[integer_types, integer_types]) -> List[Person]
        urls, result, ids = [], [], ids or {}
        for tv_src in self.supported_person_id_searches:
            if tv_src in ids:
                if TVINFO_TVMAZE == tv_src:
                    try:
                        r = self.get_person(ids[tv_src])
                    except ConnectionSkipException as e:
                        raise e
                    except (BaseException, Exception):
                        r = None
                    if r:
                        result.append(r)
        if name:
            try:
                r = tvmaze.people_search(name)
            except ConnectionSkipException as e:
                raise e
            except (BaseException, Exception):
                r = None
            if r:
                for p in r:
                    if not any(1 for ep in result if p.id == ep.id):
                        result.append(self._convert_person(p))
        return result

    def get_person(self, p_id, get_show_credits=False, get_images=False, **kwargs):
        # type: (integer_types, bool, bool, Any) -> Optional[Person]
        if not p_id:
            return
        kw = {}
        to_embed = []
        if get_show_credits:
            to_embed.append('castcredits')
        if to_embed:
            kw['embed'] = ','.join(to_embed)
        try:
            p = tvmaze.person_main_info(p_id, **kw)
        except ConnectionSkipException as e:
            raise e
        except (BaseException, Exception):
            p = None
        if p:
            return self._convert_person(p)

    def get_premieres(self, **kwargs):
        # type: (...) -> List[TVInfoEpisode]
        return self._filtered_schedule(**kwargs).get('premieres')

    def get_returning(self, **kwargs):
        # type: (...) -> List[TVInfoEpisode]
        return self._filtered_schedule(**kwargs).get('returning')

    def _make_episode(self, episode_data, show_data=None, get_images=False, get_akas=False):
        # type: (TVMazeEpisode, TVMazeShow, bool, bool) -> TVInfoEpisode
        """
        make out of TVMazeEpisode object and optionally TVMazeShow a TVInfoEpisode
        """
        ti_show = TVInfoShow()
        ti_show.seriesname = show_data.name
        ti_show.id = show_data.maze_id
        ti_show.seriesid = ti_show.id
        ti_show.language = show_data.language
        ti_show.overview = show_data.summary
        ti_show.firstaired = show_data.premiered
        ti_show.runtime = show_data.average_runtime or show_data.runtime
        ti_show.vote_average = show_data.rating and show_data.rating.get('average')
        ti_show.popularity = show_data.weight
        ti_show.genre_list = show_data.genres or []
        ti_show.genre = '|%s|' % '|'.join(ti_show.genre_list).lower()
        ti_show.official_site = show_data.official_site
        ti_show.status = show_data.status
        ti_show.show_type = (isinstance(show_data.type, string_types) and [show_data.type.lower()] or
                             isinstance(show_data.type, list) and [x.lower() for x in show_data.type] or [])
        ti_show.lastupdated = show_data.updated
        ti_show.poster = show_data.image and show_data.image.get('original')
        if get_akas:
            ti_show.aliases = [a.name for a in show_data.akas]
        if 'days' in show_data.schedule:
            ti_show.airs_dayofweek = ', '.join(show_data.schedule['days'])
        network = show_data.network or show_data.web_channel
        if network:
            ti_show.network_is_stream = None is not show_data.web_channel
            ti_show.network = network.name
            ti_show.network_id = network.maze_id
            ti_show.network_country = network.country
            ti_show.network_country_code = network.code
            ti_show.network_timezone = network.timezone
        if get_images and show_data.images:
            b_set, f_set, p_set = False, False, False
            for cur_img in show_data.images:
                img_type = img_type_map.get(cur_img.type, TVInfoImageType.other)
                img_width, img_height = cur_img.resolutions['original'].get('width'), \
                                        cur_img.resolutions['original'].get('height')
                img_ar = img_width and img_height and float(img_width) / float(img_height)
                img_ar_type = self._which_type(img_width, img_ar)
                if TVInfoImageType.poster == img_type and img_ar and img_ar_type != img_type and \
                        ti_show.poster == cur_img.resolutions.get('original')['url']:
                    p_set = False
                    ti_show.poster = None
                    ti_show.poster_thumb = None
                img_type = (TVInfoImageType.other, img_type)[
                    not img_ar or img_ar_type == img_type or
                    img_type not in (TVInfoImageType.banner, TVInfoImageType.poster, TVInfoImageType.fanart)]
                img_src = {}
                for cur_res, cur_img_url in iteritems(cur_img.resolutions):
                    img_size = img_size_map.get(cur_res)
                    if img_size:
                        img_src[img_size] = cur_img_url.get('url')
                ti_show.images.setdefault(img_type, []).append(
                    TVInfoImage(
                        image_type=img_type, sizes=img_src, img_id=cur_img.id, main_image=cur_img.main,
                        type_str=cur_img.type, width=img_width, height=img_height, aspect_ratio=img_ar))
                if not p_set and TVInfoImageType.poster == img_type:
                    p_set = True
                    ti_show.poster = cur_img.resolutions.get('original')['url']
                    ti_show.poster_thumb = cur_img.resolutions.get('original')['url']
                elif not b_set and 'banner' == cur_img.type and TVInfoImageType.banner == img_type:
                    b_set = True
                    ti_show.banner = cur_img.resolutions.get('original')['url']
                    ti_show.banner_thumb = cur_img.resolutions.get('medium')['url']
                elif not f_set and 'background' == cur_img.type and TVInfoImageType.fanart == img_type:
                    f_set = True
                    ti_show.fanart = cur_img.resolutions.get('original')['url']
        ti_show.ids = TVInfoIDs(
            tvdb=show_data.externals.get('thetvdb'), rage=show_data.externals.get('tvrage'), tvmaze=show_data.id,
            imdb=show_data.externals.get('imdb') and try_int(show_data.externals.get('imdb').replace('tt', ''), None))
        ti_show.imdb_id = show_data.externals.get('imdb')
        if isinstance(ti_show.imdb_id, integer_types):
            ti_show.imdb_id = 'tt%07d' % ti_show.imdb_id

        ti_episode = TVInfoEpisode()
        ti_episode.id = episode_data.maze_id
        ti_episode.seasonnumber = episode_data.season_number
        ti_episode.episodenumber = episode_data.episode_number
        ti_episode.episodename = episode_data.title
        ti_episode.airtime = episode_data.airtime
        ti_episode.firstaired = episode_data.airdate
        if episode_data.airstamp:
            try:
                at = _datetime_to_timestamp(tz_p.parse(episode_data.airstamp))
                ti_episode.timestamp = at
            except (BaseException, Exception):
                pass
        ti_episode.filename = episode_data.image and (episode_data.image.get('original') or
                                                      episode_data.image.get('medium'))
        ti_episode.is_special = episode_data.is_special()
        ti_episode.overview = episode_data.summary
        ti_episode.runtime = episode_data.runtime
        ti_episode.show = ti_show
        return ti_episode

    def _filtered_schedule(self, **kwargs):
        cache_name_key = 'tvmaze_schedule'
        is_none, schedule = self._get_cache_entry(cache_name_key)
        if None is schedule and not is_none:
            schedule = []
            try:
                schedule = tvmaze.get_full_schedule()
            except(BaseException, Exception):
                pass

            premieres = []
            returning = []
            rc_lang = re.compile('(?i)eng|jap')
            for cur_show in filter_iter(lambda s: 1 == s.episode_number and (
                    None is s.show.language or rc_lang.search(s.show.language)), schedule):
                if 1 == cur_show.season_number:
                    premieres += [cur_show]
                else:
                    returning += [cur_show]

            premieres = [self._make_episode(r, r.show, **kwargs)
                         for r in sorted(premieres, key=lambda e: e.show.premiered)]
            returning = [self._make_episode(r, r.show, **kwargs)
                         for r in sorted(returning, key=lambda e: e.airstamp)]

            schedule = dict(premieres=premieres, returning=returning)
            self._set_cache_entry(cache_name_key, schedule, expire=self.schedule_cache_expire)

        return schedule
