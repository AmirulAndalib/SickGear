# encoding:utf-8
# author:Prinz23
# project:imdb_api

__author__ = 'Prinz23'
__version__ = '1.0'
__api_version__ = '1.0.0'

import logging
import re

# from .imdb_exceptions import *
from bs4_parser import BS4Parser
from exceptions_helper import ex
from lib import imdbpie
from lib.dateutil.parser import parser
# from lib.tvinfo_base.exceptions import BaseTVinfoShownotfound
from lib.tvinfo_base import (
    TVInfoCharacter, TVInfoPerson, PersonGenders, TVINFO_IMDB,
    # TVINFO_FACEBOOK, TVINFO_INSTAGRAM, TVINFO_TMDB, TVINFO_TRAKT,
    # TVINFO_TVDB, TVINFO_TVRAGE, TVINFO_X, TVINFO_WIKIPEDIA,
    TVInfoBase, TVInfoIDs, TVInfoShow)
from sg_helpers import clean_data, enforce_type, get_url, try_int
from json_helper import json_loads

from six import iteritems
from six.moves import http_client as httplib
from six.moves.urllib.parse import urlencode, urljoin, quote, unquote


# noinspection PyUnreachableCode
if False:
    from typing import Any, AnyStr, Dict, List, Optional
    from six import integer_types

tz_p = parser()
log = logging.getLogger('imdb.api')
log.addHandler(logging.NullHandler())


def _get_imdb(self, url, query=None, params=None):
    headers = {'Accept-Language': self.locale}
    if params:
        full_url = '{0}?{1}'.format(url, urlencode(params))
    else:
        full_url = url
    headers.update(self.get_auth_headers(full_url))
    resp = get_url(url, headers=headers, params=params, return_response=True)

    if not resp.ok:
        if resp.status_code == httplib.NOT_FOUND:
            raise LookupError('Resource {0} not found'.format(url))
        else:
            msg = '{0} {1}'.format(resp.status_code, resp.text)
            raise imdbpie.ImdbAPIError(msg)
    resp_data = resp.content.decode('utf-8')
    try:
        resp_dict = json_loads(resp_data)
    except ValueError:
        resp_dict = self._parse_dirty_json(
            data=resp_data, query=query
        )

    if resp_dict.get('error'):
        return None
    return resp_dict


imdbpie.Imdb._get = _get_imdb


class IMDbIndexer(TVInfoBase):
    # supported_id_searches = [TVINFO_IMDB]
    supported_person_id_searches = [TVINFO_IMDB]
    supported_id_searches = [TVINFO_IMDB]

    # noinspection PyUnusedLocal
    # noinspection PyDefaultArgument
    def __init__(self, *args, **kwargs):
        super(IMDbIndexer, self).__init__(*args, **kwargs)

    def search(self, series):
        # type: (AnyStr) -> List
        """This searches for the series name
        and returns the result list
        """
        result = []
        cache_name_key = 's-title-%s' % series
        is_none, shows = self._get_cache_entry(cache_name_key)
        if not self.config.get('cache_search') or (None is shows and not is_none):
            try:
                result = imdbpie.Imdb().search_for_title(series)
            except (BaseException, Exception):
                pass
            self._set_cache_entry(cache_name_key, result, expire=self.search_cache_expire)
        else:
            result = shows
        return result

    def _search_show(self, name=None, ids=None, **kwargs):
        # type: (AnyStr, Dict[integer_types, integer_types], Optional[Any]) -> List[TVInfoShow]
        """This searches IMDB for the series name,
        """
        def _make_result_dict(s):
            imdb_id = try_int(re.search(r'tt(\d+)', s.get('id') or s.get('imdb_id')).group(1), None)
            ti_show = TVInfoShow()
            ti_show.seriesname, ti_show.id, ti_show.firstaired, ti_show.genre_list, ti_show.overview, \
                ti_show.poster, ti_show.ids = \
                clean_data(s['title']), imdb_id, s.get('releaseDetails', {}).get('date') or s.get('year'), \
                s.get('genres'), enforce_type(clean_data(s.get('plot', {}).get('outline', {}).get('text')), str, ''), \
                s.get('image') and s['image'].get('url'), TVInfoIDs(imdb=imdb_id)
            return ti_show

        results = []
        if ids:
            for t, p in iteritems(ids):
                if t in self.supported_id_searches:
                    if t == TVINFO_IMDB:
                        cache_id_key = 's-id-%s-%s' % (TVINFO_IMDB, p)
                        is_none, shows = self._get_cache_entry(cache_id_key)
                        if not self.config.get('cache_search') or (None is shows and not is_none):
                            try:
                                show = imdbpie.Imdb().get_title_auxiliary('tt%07d' % p)
                            except (BaseException, Exception):
                                continue
                            self._set_cache_entry(cache_id_key, show, expire=self.search_cache_expire)
                        else:
                            show = shows
                        if show:
                            results.extend([_make_result_dict(show)])
        if name:
            for n in ([name], name)[isinstance(name, list)]:
                try:
                    shows = self.search(n)
                    results.extend([_make_result_dict(s) for s in shows])
                except (BaseException, Exception) as e:
                    log.debug('Error searching for show: %s' % ex(e))
        seen = set()
        results = [seen.add(r.id) or r for r in results if r.id not in seen]
        return results

    @staticmethod
    def _convert_person(person_obj, filmography=None, bio=None):
        if isinstance(person_obj, dict) and 'imdb_id' in person_obj:
            imdb_id = try_int(re.search(r'(\d+)', person_obj['imdb_id']).group(1))
            return TVInfoPerson(p_id=imdb_id, name=person_obj['name'], ids=TVInfoIDs(ids={TVINFO_IMDB: imdb_id}))
        characters = []
        for known_for in (filmography and filmography['filmography']) or []:
            if known_for['titleType'] not in ('tvSeries', 'tvMiniSeries'):
                continue
            for character in known_for.get('characters') or ['unknown name']:
                ti_show = TVInfoShow()
                ti_show.id = try_int(re.search(r'(\d+)', known_for.get('id')).group(1))
                ti_show.ids.imdb = ti_show.id
                ti_show.seriesname = known_for.get('title')
                ti_show.firstaired = known_for.get('year')
                characters.append(
                    TVInfoCharacter(name=character, ti_show=ti_show, start_year=known_for.get('startYear'),
                                    end_year=known_for.get('endYear'))
                )
        try:
            birthdate = person_obj['base']['birthDate'] and tz_p.parse(person_obj['base']['birthDate']).date()
        except (BaseException, Exception):
            birthdate = None
        try:
            deathdate = person_obj['base']['deathDate'] and tz_p.parse(person_obj['base']['deathDate']).date()
        except (BaseException, Exception):
            deathdate = None
        imdb_id = try_int(re.search(r'(\d+)', person_obj['id']).group(1))
        return TVInfoPerson(
            p_id=imdb_id, ids=TVInfoIDs(ids={TVINFO_IMDB: imdb_id}), characters=characters,
            name=person_obj['base'].get('name'), real_name=person_obj['base'].get('realName'),
            nicknames=set((person_obj['base'].get('nicknames') and person_obj['base'].get('nicknames')) or []),
            akas=set((person_obj['base'].get('akas') and person_obj['base'].get('akas')) or []),
            bio=bio, gender=PersonGenders.imdb_map.get(person_obj['base'].get('gender'), PersonGenders.unknown),
            image=person_obj['base'].get('image', {}).get('url'),
            birthdate=birthdate, birthplace=person_obj['base'].get('birthPlace'),
            deathdate=deathdate, deathplace=person_obj['base'].get('deathPlace'),
            height=person_obj['base'].get('heightCentimeters')
        )

    def _search_person(self, name=None, ids=None):
        # type: (AnyStr, Dict[integer_types, integer_types]) -> List[TVInfoPerson]
        """
        search for person by name
        :param name: name to search for
        :param ids: dict of ids to search
        :return: list of found person's
        """
        results, ids = [], ids or {}
        for tv_src in self.supported_person_id_searches:
            if tv_src in ids:
                if TVINFO_IMDB == tv_src:
                    try:
                        p = self.get_person(ids[tv_src])
                    except (BaseException, Exception):
                        p = None
                    if p:
                        results.append(p)
        if name:
            cache_name_key = 'p-name-%s' % name
            is_none, ps = self._get_cache_entry(cache_name_key)
            if None is ps and not is_none:
                try:
                    ps = imdbpie.Imdb().search_for_name(name)
                except (BaseException, Exception):
                    ps = None
                self._set_cache_entry(cache_name_key, ps)
            if ps:
                for cp in ps:
                    if not any(1 for c in results if cp['imdb_id'] == 'nm%07d' % c.id):
                        results.append(self._convert_person(cp))
        return results

    @staticmethod
    def _get_bio(p_id):
        try:
            bio = get_url('https://www.imdb.com/name/nm%07d/bio' % p_id, headers={'Accept-Language': 'en'})
            if not bio:
                return
            with BS4Parser(bio) as bio_item:
                bv = bio_item.find('div', attrs={'data-testid': re.compile('mini_bio$')}, recursive=True)
                for a in bv.findAll('a'):
                    a.replaceWithChildren()
                for b in bv.findAll('br'):
                    b.replaceWith('\n')
                return bv.get_text().strip()
        except (BaseException, Exception):
            return

    def get_person(self, p_id, get_show_credits=False, get_images=False, **kwargs):
        # type: (integer_types, bool, bool, Any) -> Optional[TVInfoPerson]
        if not p_id:
            return
        cache_main_key, cache_bio_key, cache_credits_key = 'p-main-%s' % p_id, 'p-bio-%s' % p_id, 'p-credits-%s' % p_id
        is_none, p = self._get_cache_entry(cache_main_key)
        if None is p and not is_none:
            try:
                p = imdbpie.Imdb().get_name(imdb_id='nm%07d' % p_id)
            except (BaseException, Exception):
                p = None
            self._set_cache_entry(cache_main_key, p)
        is_none, bio = self._get_cache_entry(cache_bio_key)
        if None is bio and not is_none:
            bio = self._get_bio(p_id)
            self._set_cache_entry(cache_bio_key, bio)
        fg = None
        if get_show_credits:
            is_none, fg = self._get_cache_entry(cache_credits_key)
            if None is fg and not is_none:
                try:
                    fg = imdbpie.Imdb().get_name_filmography(imdb_id='nm%07d' % p_id)
                except (BaseException, Exception):
                    fg = None
                self._set_cache_entry(cache_credits_key, fg)
        if p:
            return self._convert_person(p, filmography=fg, bio=bio)
