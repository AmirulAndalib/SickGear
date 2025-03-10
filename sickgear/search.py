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
import os
import re
import threading
import traceback

import exceptions_helper
from exceptions_helper import ex
from sg_helpers import write_file

import sickgear
from . import clients, common, db, failed_history, helpers, history, logger, \
    notifiers, nzbget, nzbSplitter, show_name_helpers, sab, ui
from .common import DOWNLOADED, SNATCHED, SNATCHED_BEST, SNATCHED_PROPER, MULTI_EP_RESULT, SEASON_RESULT, Quality
from .providers.generic import GenericProvider
from .tv import TVEpisode, TVShow

from six import iteritems, itervalues, string_types

# noinspection PyUnreachableCode, PyStatementEffect
if False:
    from typing import AnyStr, Dict, List, Optional, Tuple, Union
    from .classes import NZBDataSearchResult, NZBSearchResult, SearchResult, TorrentSearchResult
    search_result_type = Union[NZBDataSearchResult, NZBSearchResult, SearchResult, TorrentSearchResult]


def _download_result(result):
    # type: (search_result_type) -> bool
    """
    Downloads a result to the appropriate black hole folder.

    :param result: SearchResult instance to download.
    :return: bool representing success
    """

    res_provider = result.provider
    if None is res_provider:
        logger.error('Invalid provider name - this is a coding error, report it please')
        return False

    # NZB files with a URL can just be downloaded from the provider
    if 'nzb' == result.resultType:
        new_result = res_provider.download_result(result)
    # if it's an nzb data result
    elif 'nzbdata' == result.resultType:

        # get the final file path to the nzb
        file_name = os.path.join(sickgear.NZB_DIR, f'{result.name}.nzb')

        logger.log(f'Saving NZB to {file_name}')

        new_result = True

        # save the data to disk
        try:
            data = result.get_data()
            if not data:
                new_result = False
            else:
                write_file(file_name, data, raise_exceptions=True)

        except (EnvironmentError, IOError) as e:
            logger.error(f'Error trying to save NZB to black hole: {ex(e)}')
            new_result = False
    elif 'torrent' == res_provider.providerType:
        new_result = res_provider.download_result(result)
    else:
        logger.error('Invalid provider type - this is a coding error, report it please')
        new_result = False

    return new_result


def snatch_episode(result, end_status=SNATCHED):
    # type: (search_result_type, int) -> bool
    """
    Contains the internal logic necessary to actually "snatch" a result that
    has been found.

    :param result: SearchResult instance to be snatched.
    :param end_status: the episode status that should be used for the episode object once it's snatched.
    :return: bool representing success
    """

    if None is result:
        return False

    if sickgear.ALLOW_HIGH_PRIORITY:
        # if it aired recently make it high priority
        for cur_ep_obj in result.ep_obj_list:
            if datetime.date.today() - cur_ep_obj.airdate <= datetime.timedelta(days=7) or \
                    datetime.date.fromordinal(1) >= cur_ep_obj.airdate:
                result.priority = 1
    if 0 < result.properlevel:
        end_status = SNATCHED_PROPER

    # NZB files can be sent straight to SAB or saved to disk
    if result.resultType in ('nzb', 'nzbdata'):
        if 'blackhole' == sickgear.NZB_METHOD:
            dl_result = _download_result(result)
        elif 'sabnzbd' == sickgear.NZB_METHOD:
            dl_result = sab.send_nzb(result)
        elif 'nzbget' == sickgear.NZB_METHOD:
            dl_result = nzbget.send_nzb(result)
        else:
            logger.error(f'Unknown NZB action specified in config: {sickgear.NZB_METHOD}')
            dl_result = False

    # TORRENT files can be sent to clients or saved to disk
    elif 'torrent' == result.resultType:
        if not result.url.startswith('magnet') and None is not result.get_data_func:
            result.url = result.get_data_func(result.url)
            result.get_data_func = None  # consume only once
            if not result.url:
                return False
        # torrents are saved to disk when blackhole mode
        if 'blackhole' == sickgear.TORRENT_METHOD:
            dl_result = _download_result(result)
        else:
            # make sure we have the torrent file content
            if not result.content and not result.url.startswith('magnet'):
                result.content = result.provider.get_url(result.url, as_binary=True)
                if result.provider.should_skip() or not result.content:
                    logger.error(f'Torrent content failed to download from {result.url}')
                    return False
            # Snatches torrent with client
            dl_result = clients.get_client_instance(sickgear.TORRENT_METHOD)().send_torrent(result)

            if result.cache_filepath:
                helpers.remove_file_perm(result.cache_filepath)
    else:
        logger.error('Unknown result type, unable to download it')
        dl_result = False

    if not dl_result:
        return False

    if sickgear.USE_FAILED_DOWNLOADS:
        failed_history.add_snatched(result)

    ui.notifications.message('Episode snatched', result.name)

    history.log_snatch(result)

    # don't notify when we re-download an episode
    sql_l = []
    update_imdb_data = True
    for cur_ep_obj in result.ep_obj_list:
        with cur_ep_obj.lock:
            if is_first_best_match(cur_ep_obj.status, result):
                cur_ep_obj.status = Quality.composite_status(SNATCHED_BEST, result.quality)
            else:
                cur_ep_obj.status = Quality.composite_status(end_status, result.quality)

            item = cur_ep_obj.get_sql()
            if None is not item:
                sql_l.append(item)

        if cur_ep_obj.status not in Quality.DOWNLOADED:
            notifiers.notify_snatch(cur_ep_obj)

            update_imdb_data = update_imdb_data and cur_ep_obj.show_obj.load_imdb_info()

    if 0 < len(sql_l):
        my_db = db.DBConnection()
        my_db.mass_action(sql_l)

    return True


def pass_show_wordlist_checks(name, show_obj):
    # type: (AnyStr, TVShow) -> bool
    """
    check if string (release name) passes show object ignore/request list

    :param name: string to check
    :param show_obj: show object
    :return: passed check
    """
    re_extras = dict(re_prefix='.*', re_suffix='.*')
    result = show_name_helpers.contains_any(name, show_obj.rls_ignore_words, rx=show_obj.rls_ignore_words_regex,
                                            **re_extras)
    if None is not result and result:
        logger.log(f'Ignored: {name} for containing ignore word')
        return False

    result = show_name_helpers.contains_any(name, show_obj.rls_require_words, rx=show_obj.rls_require_words_regex,
                                            **re_extras)
    if None is not result and not result:
        logger.log(f'Ignored: {name} for not containing any required word match')
        return False
    return True


def pick_best_result(
        results,  # type: List[search_result_type]
        show_obj,  # type: TVShow
        quality_list=None,  # type: List[int]
        filter_rls=''  # type: AnyStr
):
    # type: (...) -> search_result_type
    """
    picks best result from given search result list for given show object

    :param results: list of search result lists
    :param show_obj: show object
    :param quality_list: optional list of qualities
    :param filter_rls: optional thread name
    :return: best search result
    """
    msg = ('Picking the best result out of %s', 'Checking the best result %s')[1 == len(results)]
    logger.debug(msg % [x.name for x in results])

    # find the best result for the current episode
    best_result = None
    best_fallback_result = None
    scene_only = scene_or_contain = non_scene_fallback = scene_rej_nuked = scene_nuked_active = False
    if filter_rls:
        try:
            provider = getattr(results[0], 'provider', None)
            scene_only = getattr(provider, 'scene_only', False)
            scene_or_contain = getattr(provider, 'scene_or_contain', '')
            recent_task = 'RECENT' in filter_rls
            non_scene_fallback = (getattr(provider, 'scene_loose', False) and recent_task) \
                or (getattr(provider, 'scene_loose_active', False) and not recent_task)
            scene_rej_nuked = getattr(provider, 'scene_rej_nuked', False)
            scene_nuked_active = getattr(provider, 'scene_nuked_active', False) and not recent_task
        except (BaseException, Exception):
            filter_rls = False

    addendum = ''
    for cur_result in results:

        if show_obj.is_anime and not show_obj.release_groups.is_valid(cur_result):
            continue

        if quality_list and cur_result.quality not in quality_list:
            logger.debug(f'Rejecting unwanted quality {Quality.qualityStrings[cur_result.quality]}'
                         f' for [{cur_result.name}]')
            continue

        if not pass_show_wordlist_checks(cur_result.name, show_obj):
            continue

        cur_size = getattr(cur_result, 'size', None)
        if sickgear.USE_FAILED_DOWNLOADS and None is not cur_size and failed_history.has_failed(
                cur_result.name, cur_size, cur_result.provider.name):
            logger.log(f'Rejecting previously failed [{cur_result.name}]')
            continue

        if filter_rls and any([scene_only, non_scene_fallback, scene_rej_nuked, scene_nuked_active]):
            if show_obj.is_anime:
                addendum = 'anime (skipping scene/nuke filter) '
            else:
                scene_contains = False
                if scene_only and scene_or_contain:
                    re_extras = dict(re_prefix='.*', re_suffix='.*')
                    r = show_name_helpers.contains_any(cur_result.name, scene_or_contain, **re_extras)
                    if None is not r and r:
                        scene_contains = True

                if scene_contains and not scene_rej_nuked:
                    logger.debug(f'Considering title match to \'or contain\' [{cur_result.name}]')
                    reject = False
                else:
                    reject, url = can_reject(cur_result.name)
                    if reject:
                        if isinstance(reject, string_types):
                            if scene_rej_nuked and not scene_nuked_active:
                                logger.debug(f'Rejecting nuked release. Nuke reason [{reject}] source [{url}]')
                            elif scene_nuked_active:
                                best_fallback_result = best_candidate(best_fallback_result, cur_result)
                            else:
                                logger.debug(f'Considering nuked release. Nuke reason [{reject}] source [{url}]')
                                reject = False
                        elif scene_contains or non_scene_fallback:
                            best_fallback_result = best_candidate(best_fallback_result, cur_result)
                        else:
                            logger.debug(f'Rejecting as not scene release listed at any [{url}]')

                if reject:
                    continue

        best_result = best_candidate(best_result, cur_result)

    if best_result and scene_only and not show_obj.is_anime:
        addendum = 'scene release filtered '
    elif not best_result and best_fallback_result:
        addendum = 'non scene release filtered '
        best_result = best_fallback_result

    if best_result:
        msg = ('Picked as the best %s[%s]', 'Confirmed as the best %s[%s]')[1 == len(results)]
        logger.debug(msg % (addendum, best_result.name))
    else:
        logger.debug('No result picked.')

    return best_result


def best_candidate(best_result, cur_result):
    # type: (search_result_type, search_result_type) -> search_result_type
    """
    compare 2 search results and return best

    :param best_result: possible best search result
    :param cur_result: current best search result
    :return: new best search result
    """
    logger.log(f'Quality is {Quality.qualityStrings[cur_result.quality]} for [{cur_result.name}]')

    if not best_result or best_result.quality < cur_result.quality != Quality.UNKNOWN:
        best_result = cur_result

    elif best_result.quality == cur_result.quality:
        if cur_result.properlevel > best_result.properlevel and \
                (not cur_result.is_repack or cur_result.release_group == best_result.release_group):
            best_result = cur_result
        elif cur_result.properlevel == best_result.properlevel:
            if 'xvid' in best_result.name.lower() and 'x264' in cur_result.name.lower():
                logger.log(f'Preferring (x264 over xvid) [{cur_result.name}]')
                best_result = cur_result
            elif re.search('(?i)(h.?|x)264', best_result.name) and re.search('(?i)((h.?|x)265|hevc)', cur_result.name):
                logger.log(f'Preferring (x265 over x264) [{cur_result.name}]')
                best_result = cur_result
            elif 'internal' in best_result.name.lower() and 'internal' not in cur_result.name.lower():
                best_result = cur_result

    return best_result


def is_final_result(result):
    # type: (search_result_type) -> bool
    """
    Checks if the given result is good enough quality that we can stop searching for other ones.

    :param result: search result to check
    :return: If the result is the highest quality in both any and best quality lists then this function
             returns True, if not then it's False
    """

    logger.debug(f'Checking if searching should continue after finding {result.name}')

    show_obj = result.ep_obj_list[0].show_obj

    any_qualities, best_qualities = Quality.split_quality(show_obj.quality)

    # if there is a download that's higher than this then we definitely need to keep looking
    if best_qualities and max(best_qualities) > result.quality:
        return False

    # if it does not match the shows block and allow list its no good
    elif show_obj.is_anime and show_obj.release_groups.is_valid(result):
        return False

    # if there's no download that's higher (above) and this is the highest initial download then we're good
    elif any_qualities and result.quality in any_qualities:
        return True

    elif best_qualities and max(best_qualities) == result.quality:

        # if this is the best download, but we have a higher initial download then keep looking
        if any_qualities and max(any_qualities) > result.quality:
            return False

        # if this is the best download, and we don't have a higher initial download then we're done
        return True

    # if we got here than it's either not on the lists, they're empty, or it's lower than the highest required
    return False


def is_first_best_match(ep_status, result):
    # type: (int, search_result_type) -> bool
    """
    Checks if the given result is the best quality match and if we want to archive the episode on first match.

    :param ep_status: current episode object status
    :param result: search result to check
    :return:
    """

    logger.debug(f'Checking if the first best quality match should be archived for episode {result.name}')

    show_obj = result.ep_obj_list[0].show_obj
    cur_status, cur_quality = Quality.split_composite_status(ep_status)

    any_qualities, best_qualities = Quality.split_quality(show_obj.quality)

    # if there is a download that's a match to one of our best qualities, and
    # we want to archive the episode then we are done
    if best_qualities and show_obj.upgrade_once and \
            (result.quality in best_qualities and
             (cur_status in (SNATCHED, SNATCHED_PROPER, SNATCHED_BEST, DOWNLOADED) or
              result.quality not in any_qualities)):
        return True

    return False


def set_wanted_aired(ep_obj,  # type: TVEpisode
                     unaired,  # type: bool
                     ep_count,  # type: Dict[int, int]
                     ep_count_scene,  # type: Dict[int, int]
                     manual=False  # type: bool
                     ):
    """
    set wanted properties for given episode object

    :param ep_obj: episode object
    :param unaired: include unaried episodes
    :param ep_count: count of episodes in seasons
    :param ep_count_scene: count of episodes in scene seasons
    :param manual: manual search
    """
    ep_status, ep_quality = common.Quality.split_composite_status(ep_obj.status)
    ep_obj.wanted_quality = get_wanted_qualities(ep_obj, ep_status, ep_quality, unaired=unaired, manual=manual)
    ep_obj.eps_aired_in_season = ep_count.get(ep_obj.season, 0)
    ep_obj.eps_aired_in_scene_season = ep_count_scene.get(
        ep_obj.scene_season, 0) if ep_obj.scene_season else ep_obj.eps_aired_in_season


def get_wanted_qualities(ep_obj,  # type: TVEpisode
                         cur_status,  # type: int
                         cur_quality,  # type: int
                         unaired=False,  # type: bool
                         manual=False  # type: bool
                         ):  # type: (...) -> List[int]
    """
    get list of wanted qualities for given episode object

    :param ep_obj: episode object
    :param cur_status: current episode status
    :param cur_quality: current episode quality
    :param unaired: include unaired episodes
    :param manual: manual search
    :return: list of wanted qualities for episode object
    """
    if isinstance(ep_obj, TVEpisode):
        return sickgear.WANTEDLIST_CACHE.get_wantedlist(ep_obj.show_obj.quality, ep_obj.show_obj.upgrade_once,
                                                        cur_quality, cur_status, unaired, manual)

    return []


def get_aired_in_season(show_obj, return_sql=False):
    # type: (TVShow, bool) -> Union[Tuple[Dict[int, int], Dict[int, int]], Tuple[Dict[int, int], Dict[int, int], List]]
    """
    returns tuple of dicts with episode count per (scene) season and optional sql results

    :param show_obj: show object
    :param return_sql: return sql
    :return: returns tuple of dicts with episode count per (scene) season
    """
    ep_count = {}
    ep_count_scene = {}
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).toordinal()
    my_db = db.DBConnection()

    if show_obj.air_by_date:
        sql_string = 'SELECT ep.status, ep.season, ep.scene_season, ep.episode, ep.airdate ' + \
                     'FROM [tv_episodes] AS ep, [tv_shows] AS show ' + \
                     'WHERE ep.showid = show.indexer_id AND show.paused = 0 AND season != 0 AND' \
                     ' ep.indexer = ? AND ep.showid = ?' \
                     ' AND show.air_by_date = 1'
    else:
        sql_string = 'SELECT status, season, scene_season, episode, airdate ' + \
                     'FROM [tv_episodes] ' + \
                     'WHERE indexer = ? AND showid = ?' \
                     ' AND season > 0'

    sql_result = my_db.select(sql_string, [show_obj.tvid, show_obj.prodid])
    for cur_result in sql_result:
        if 1 < helpers.try_int(cur_result['airdate']) <= tomorrow:
            cur_season = helpers.try_int(cur_result['season'])
            ep_count[cur_season] = ep_count.setdefault(cur_season, 0) + 1
            cur_scene_season = helpers.try_int(cur_result['scene_season'], -1)
            if -1 != cur_scene_season:
                ep_count_scene[cur_scene_season] = ep_count.setdefault(cur_scene_season, 0) + 1

    if return_sql:
        return ep_count, ep_count_scene, sql_result

    return ep_count, ep_count_scene


def wanted_episodes(show_obj,  # type: TVShow
                    from_date,  # type: datetime.date
                    make_dict=False,  # type: bool
                    unaired=False  # type: bool
                    ):  # type: (...) -> Union[List[TVEpisode], Dict[int, TVEpisode]]
    """

    :param show_obj: tv show object
    :param from_date: start date
    :param make_dict: make dict result
    :param unaired: include unaired episodes
    :return: list or dict of wanted episode objects
    """
    ep_count, ep_count_scene, sql_result_org = get_aired_in_season(show_obj, return_sql=True)

    from_date_ord = from_date.toordinal()
    if unaired:
        sql_result = [s for s in sql_result_org if s['airdate'] > from_date_ord or s['airdate'] == 1]
    else:
        sql_result = [s for s in sql_result_org if s['airdate'] > from_date_ord]

    if make_dict:
        wanted = {}
    else:
        wanted = []

    total_wanted = total_replacing = total_unaired = 0

    if 0 < len(sql_result) and 2 < len(sql_result) - len(show_obj.sxe_ep_obj):
        my_db = db.DBConnection()
        ep_sql_result = my_db.select(
            'SELECT * FROM tv_episodes'
            ' WHERE indexer = ? AND showid = ?',
            [show_obj.tvid, show_obj.prodid])
    else:
        ep_sql_result = None

    for result in sql_result:
        ep_obj = show_obj.get_episode(int(result['season']), int(result['episode']), ep_result=ep_sql_result)
        cur_status, cur_quality = common.Quality.split_composite_status(ep_obj.status)
        ep_obj.wanted_quality = get_wanted_qualities(ep_obj, cur_status, cur_quality, unaired=unaired)
        if not ep_obj.wanted_quality:
            continue

        ep_obj.eps_aired_in_season = ep_count.get(helpers.try_int(result['season']), 0)
        ep_obj.eps_aired_in_scene_season = ep_count_scene.get(
            helpers.try_int(result['scene_season']), 0) if result['scene_season'] else ep_obj.eps_aired_in_season
        if make_dict:
            wanted.setdefault(ep_obj.scene_season if ep_obj.show_obj.is_scene else ep_obj.season, []).append(ep_obj)
        else:
            wanted.append(ep_obj)

        if cur_status in (common.WANTED, common.FAILED):
            total_wanted += 1
        elif cur_status in (common.UNAIRED, common.SKIPPED, common.IGNORED, common.UNKNOWN):
            total_unaired += 1
        else:
            total_replacing += 1

    if 0 < total_wanted + total_replacing + total_unaired:
        actions = []
        for msg, total in ['%d episode%s', total_wanted], \
                          ['to upgrade %d episode%s', total_replacing], \
                          ['%d unaired episode%s', total_unaired]:
            if 0 < total:
                actions.append(msg % (total, helpers.maybe_plural(total)))
        logger.log(f'We want {" and ".join(actions)} for {show_obj.unique_name}')

    return wanted


def search_for_needed_episodes(ep_obj_list):
    # type: (List[TVEpisode]) -> List[search_result_type]
    """
    search for episodes in list

    :param ep_obj_list: list of episode objects
    :return: list of found search results
    """
    found_results = {}

    search_done = False

    orig_thread_name = threading.current_thread().name

    providers = list(filter(lambda x: x.is_active() and x.enable_recentsearch, sickgear.providers.sorted_sources()))

    for cur_provider in providers:
        threading.current_thread().name = '%s :: [%s]' % (orig_thread_name, cur_provider.name)

        ep_obj_search_result_list = cur_provider.search_rss(ep_obj_list)

        search_done = True

        # pick a single result for each episode, respecting existing results
        for cur_ep_obj in ep_obj_search_result_list:

            if cur_ep_obj.show_obj.paused:
                logger.debug(f'Show {cur_ep_obj.show_obj.unique_name} is paused,'
                             f' ignoring all RSS items for {cur_ep_obj.pretty_name()}')
                continue

            # find the best result for the current episode
            best_result = pick_best_result(ep_obj_search_result_list[cur_ep_obj], cur_ep_obj.show_obj,
                                           filter_rls=orig_thread_name)

            # if all results were rejected move on to the next episode
            if not best_result:
                logger.debug(f'All found results for {cur_ep_obj.pretty_name()} were rejected.')
                continue

            # if it's already in the list (from another provider) and the newly found quality is no better, then skip it
            if cur_ep_obj in found_results and best_result.quality <= found_results[cur_ep_obj].quality:
                continue

            # filter out possible bad torrents from providers
            if 'torrent' == best_result.resultType and 'blackhole' != sickgear.TORRENT_METHOD:
                best_result.content = None
                if not best_result.url.startswith('magnet'):
                    best_result.content = best_result.provider.get_url(best_result.url, as_binary=True)
                    if best_result.provider.should_skip():
                        break
                    if not best_result.content:
                        continue

            found_results[cur_ep_obj] = best_result

            try:
                cur_provider.fails.save_list()
            except (BaseException, Exception):
                pass

    threading.current_thread().name = orig_thread_name

    if not len(providers):
        logger.warning('No NZB/Torrent providers in Media Providers/Options are enabled to match recent episodes')
    elif not search_done:
        logger.error(f'Failed recent search of {len(providers)} enabled provider{helpers.maybe_plural(providers)}.'
                     f' More info in debug log.')

    return list(found_results.values())


def can_reject(release_name):
    # type: (AnyStr) -> Union[Tuple[None, None],Tuple[True or AnyStr, AnyStr]]
    """
    Check if a release name should be rejected at external services.
    If any site reports result as a valid scene release, then return None, None.
    If predb reports result as nuked, then return nuke reason and url attempted.
    If fail to find result at all services, return reject and url details for each site.

    :param release_name: Release title
    :return: None, None if release has no issue otherwise True/Nuke reason, URLs that rejected
    """
    rej_urls = []
    srrdb_url = 'https://www.srrdb.com/api/search/r:%s/order:date-desc' % re.sub(r'[][]', '', release_name)
    resp = helpers.get_url(srrdb_url, parse_json=True)
    if not resp:
        srrdb_rej = True
        rej_urls += ['Failed contact \'%s\'' % srrdb_url]
    else:
        srrdb_rej = (not len(resp.get('results', []))
                     or release_name.lower() != resp.get('results', [{}])[0].get('release', '').lower())
        rej_urls += ([], ['\'%s\'' % srrdb_url])[srrdb_rej]

    sane_name = helpers.full_sanitize_scene_name(release_name)
    # predb_url = 'https://predb.ovh/api/v1/?q=@name "%s"' % sane_name
    predb_url = 'https://predb.de/api/?q=%s' % release_name
    resp = helpers.get_url(predb_url, parse_json=True)
    predb_rej = True
    if not resp:
        rej_urls += ['Failed contact \'%s\'' % predb_url]
    elif 'success' == resp.get('status', '').lower():
        rows = resp and resp.get('data') or []
        for data in rows:
            if sane_name == helpers.full_sanitize_scene_name((data.get('release') or '').strip()):
                nuke_type = helpers.try_int(data.get('status'))
                if not nuke_type:
                    predb_rej = not helpers.try_int(data.get('pretime'))
                else:
                    predb_rej = nuke_type not in (2, 4) and (data.get('reason') or 'Reason not set')
                break
        rej_urls += ([], ['\'%s\'' % predb_url])[bool(predb_rej)]

    pred = any([not srrdb_rej, not predb_rej])

    return pred and (None, None) or (predb_rej or True,  ', '.join(rej_urls))


def _search_provider_thread(provider, provider_results, show_obj, ep_obj_list, manual_search, try_other_searches):
    # type: (GenericProvider, Dict, TVShow, List[TVEpisode], bool, bool) -> None
    """
    perform a search on a provider for specified show, episodes

    :param provider: Provider to search
    :param provider_results: reference to dict to return results
    :param show_obj: show to search for
    :param ep_obj_list: list of episodes to search for
    :param manual_search: is manual search
    :param try_other_searches: try other search methods
    """
    search_count = 0
    search_mode = getattr(provider, 'search_mode', 'eponly')

    while True:
        search_count += 1

        if 'eponly' == search_mode:
            logger.log(f'Performing episode search for {show_obj.unique_name}')
        else:
            logger.log(f'Performing season pack search for {show_obj.unique_name}')

        try:
            provider.cache.clear_cache()
            search_result_list = provider.find_search_results(show_obj, ep_obj_list, search_mode, manual_search,
                                                              try_other_searches=try_other_searches)
            if any(search_result_list):
                logger.log(', '.join(['%s %s candidate%s' % (
                    len(v), (('multiep', 'season')[SEASON_RESULT == k], 'episode')['ep' in search_mode],
                    helpers.maybe_plural(v)) for (k, v) in iteritems(search_result_list)]))
        except exceptions_helper.AuthException as e:
            logger.error(f'Authentication error: {ex(e)}')
            break
        except (BaseException, Exception) as e:
            logger.error(f'Error while searching {provider.name}, skipping: {ex(e)}')
            logger.error(traceback.format_exc())
            break

        if len(search_result_list):
            # make a list of all the results for this provider
            for cur_search_result in search_result_list:
                # skip non-tv crap
                search_result_list[cur_search_result] = list(filter(
                    lambda ep_item: ep_item.show_obj == show_obj and show_name_helpers.pass_wordlist_checks(
                        ep_item.name, parse=False, indexer_lookup=False, show_obj=ep_item.show_obj),
                    search_result_list[cur_search_result]))

                if cur_search_result in provider_results:
                    provider_results[cur_search_result] += search_result_list[cur_search_result]
                else:
                    provider_results[cur_search_result] = search_result_list[cur_search_result]

            break
        elif not getattr(provider, 'search_fallback', False) or 2 == search_count:
            break

        search_mode = '%sonly' % ('ep', 'sp')['ep' in search_mode]
        logger.log(f'Falling back to {("season pack", "episode")["ep" in search_mode]} search ...')

    if not provider_results:
        logger.log('No suitable result at [%s]' % provider.name)


def cache_torrent_file(
        search_result,  # type: Union[sickgear.classes.SearchResult, TorrentSearchResult]
        show_obj,  # type: TVShow
        **kwargs
):
    # type: (...) -> Optional[TorrentSearchResult]

    cache_file = os.path.join(sickgear.CACHE_DIR or helpers.get_system_temp_dir(),
                              '%s.torrent' % (helpers.sanitize_filename(search_result.name)))

    if not helpers.download_file(
            search_result.url, cache_file, session=search_result.provider.session, failure_monitor=False):
        return

    try:
        with open(cache_file, 'rb') as fh:
            torrent_content = fh.read()
    except (BaseException, Exception):
        return

    try:
        # verify header
        re.findall(r'\w+\d+:', ('%s' % torrent_content)[0:6])[0]
    except (BaseException, Exception):
        return

    try:
        import torrent_parser as tp
        torrent_meta = tp.decode(torrent_content, use_ordered_dict=True, errors='usebytes')
    except (BaseException, Exception):
        return

    search_result.cache_filepath = cache_file
    search_result.content = torrent_content

    if isinstance(torrent_meta, dict):
        torrent_name = torrent_meta.get('info', {}).get('name')
        if torrent_name:
            # verify the name in torrent also passes filtration
            result_name = search_result.name
            search_result.name = torrent_name
            if search_result.provider.get_id() in ['tvchaosuk'] \
                    and hasattr(search_result.provider, 'regulate_cache_torrent_file'):
                torrent_name = search_result.provider.regulate_cache_torrent_file(torrent_name)
            if not _pick_best_result_helper([search_result], show_obj=show_obj, **kwargs) or \
                    not show_name_helpers.pass_wordlist_checks(torrent_name, indexer_lookup=False, show_obj=show_obj):
                logger.log(f'Ignored {result_name} that contains {torrent_name} (debug log has detail)')
                return

    return search_result


def _pick_best_result_helper(
        results,  # type: List[search_result_type]
        show_obj,  # type: TVShow
        old_status=None,  # type: int
        use_quality_list=None,  # type: List[int]
        best_qualities=None,  # type: List[int]
        orig_thread_name=''  # type: AnyStr
    ):
    # type: (...) -> search_result_type
    """
    helper to apply pick_best_result with filters

    :param results: SearchResults
    :param show_obj: show object
    :param old_status: old status of checked episode
    :param use_quality_list: default quality list
    :param best_qualities: best qualites for the episode
    :param orig_thread_name: original thread name
    :return: best matching result
    """
    internal_quality_list = None
    if None is not use_quality_list and any([results[0].ep_obj_list]):
        old_status = old_status or \
                     failed_history.find_old_status(results[0].ep_obj_list[0]) or results[0].ep_obj_list[0].status
        if old_status:
            status, quality = Quality.split_composite_status(old_status)
            internal_quality_list = (status not in (
                common.WANTED, common.FAILED, common.UNAIRED, common.SKIPPED, common.IGNORED, common.UNKNOWN))

    quality_list = use_quality_list or (internal_quality_list and (None, best_qualities)[any(best_qualities)] or None)

    return pick_best_result(results=results, show_obj=show_obj, quality_list=quality_list, filter_rls=orig_thread_name)


def search_providers(
        show_obj,  # type: TVShow
        ep_obj_list,  # type: List[TVEpisode]
        manual_search=False,  # type: bool
        torrent_only=False,  # type: bool
        try_other_searches=False,  # type: bool
        old_status=None,  # type: int
        scheduled=False  # type: bool
):
    # type: (...) -> List[search_result_type]
    """
    search provider for given episode objects from given show object

    :param show_obj: tv show object
    :param ep_obj_list: list of episode objects
    :param manual_search: manual search
    :param torrent_only: torrents only
    :param try_other_searches: try other searches
    :param old_status: old status
    :param scheduled: scheduled search
    :return: list of search result objects
    """
    found_results = {}
    final_results = []  # type: List[search_result_type]

    search_done = False
    search_threads = []

    orig_thread_name = threading.current_thread().name

    provider_list = [x for x in sickgear.providers.sorted_sources() if x.is_active() and
                     getattr(x, 'enable_backlog', None) and
                     (not torrent_only or GenericProvider.TORRENT == x.providerType) and
                     (not scheduled or getattr(x, 'enable_scheduled_backlog', None))]

    # create a thread for each provider to search
    for cur_provider in provider_list:
        if cur_provider.anime_only and not show_obj.is_anime:
            logger.debug(f'{show_obj.unique_name} is not an anime, skipping')
            continue

        provider_id = cur_provider.get_id()

        found_results[provider_id] = {}
        search_threads.append(threading.Thread(target=_search_provider_thread,
                                               kwargs=dict(provider=cur_provider,
                                                           provider_results=found_results[provider_id],
                                                           show_obj=show_obj, ep_obj_list=ep_obj_list,
                                                           manual_search=manual_search,
                                                           try_other_searches=try_other_searches),
                                               name='%s :: [%s]' % (orig_thread_name, cur_provider.name)))

        # start the provider search thread
        search_threads[-1].start()
        search_done = True

    # wait for all searches to finish
    for s_t in search_threads:
        s_t.join()

    any_qualities, best_qualities = Quality.split_quality(show_obj.quality)
    params = dict(show_obj=show_obj, old_status=old_status, best_qualities=best_qualities,
                  orig_thread_name=orig_thread_name)

    # now look in all the results
    for cur_provider in provider_list:
        provider_id = cur_provider.get_id()

        # skip to next provider if we have no results to process
        if provider_id not in found_results or not len(found_results[provider_id]):
            continue

        # pick the best season NZB
        best_season_result = None
        if SEASON_RESULT in found_results[provider_id] and found_results[provider_id][SEASON_RESULT]:
            best_season_result = _pick_best_result_helper(
                found_results[provider_id][SEASON_RESULT], show_obj=show_obj,
                use_quality_list=any_qualities + best_qualities, orig_thread_name=orig_thread_name)

        highest_quality_overall = 0
        for cur_episode in found_results[provider_id]:
            for cur_result in found_results[provider_id][cur_episode]:
                if Quality.UNKNOWN != cur_result.quality and highest_quality_overall < cur_result.quality:
                    highest_quality_overall = cur_result.quality
        logger.debug(f'{Quality.qualityStrings[highest_quality_overall]} is the highest quality of any match')

        # see if every episode is wanted
        if best_season_result:
            # get the quality of the season nzb
            season_qual = best_season_result.quality
            logger.debug(f'{Quality.qualityStrings[season_qual]} is the quality of the season'
                         f' {best_season_result.provider.providerType}')

            my_db = db.DBConnection()
            sql = 'SELECT season, episode' \
                  ' FROM tv_episodes' \
                  ' WHERE indexer = %s AND showid = %s AND (season IN (%s))' % \
                  (show_obj.tvid, show_obj.prodid, ','.join([str(x.season) for x in ep_obj_list]))
            ep_nums = [(int(x['season']), int(x['episode'])) for x in my_db.select(sql)]

            logger.log(f'Executed query: [{sql}]')
            logger.debug(f'Episode list: {ep_nums}')

            all_wanted = True
            any_wanted = False
            for ep_num in ep_nums:
                if not show_obj.want_episode(ep_num[0], ep_num[1], season_qual):
                    all_wanted = False
                else:
                    any_wanted = True

            # if we need every ep in the season and there's nothing better,
            # then download this and be done with it (unless single episodes are preferred)
            if all_wanted and highest_quality_overall == best_season_result.quality:
                logger.log(f'Every episode in this season is needed, downloading the whole'
                           f' {best_season_result.provider.providerType} {best_season_result.name}')
                ep_obj_list = []
                for ep_num in ep_nums:
                    ep_obj_list.append(show_obj.get_episode(ep_num[0], ep_num[1]))
                best_season_result.ep_obj_list = ep_obj_list

                return [best_season_result]

            elif not any_wanted:
                logger.debug(f'No episodes from this season are wanted at this quality,'
                             f' ignoring the result of {best_season_result.name}')
            else:
                if GenericProvider.NZB == best_season_result.provider.providerType:
                    logger.debug('Breaking apart the NZB and adding the individual ones to our results')

                    # if not, break it apart and add them as the lowest priority results
                    individual_results = nzbSplitter.split_result(best_season_result)

                    if isinstance(individual_results, list):
                        for cur_result in filter(
                            lambda r: r.show_obj == show_obj and show_name_helpers.pass_wordlist_checks(
                                r.name, parse=False, indexer_lookup=False, show_obj=r.show_obj), individual_results):
                            ep_num = None
                            if 1 == len(cur_result.ep_obj_list):
                                ep_num = cur_result.ep_obj_list[0].episode
                            elif 1 < len(cur_result.ep_obj_list):
                                ep_num = MULTI_EP_RESULT

                            if ep_num in found_results[provider_id]:
                                found_results[provider_id][ep_num].append(cur_result)
                            else:
                                found_results[provider_id][ep_num] = [cur_result]

                # If this is a torrent all we can do is leech the entire torrent,
                # user will have to select which eps not do download in his torrent client
                else:

                    # Season result from Torrent Provider must be a full-season torrent, creating multi-ep result for it
                    logger.log('Adding multi episode result for full season torrent. In your torrent client,'
                               ' set the episodes that you do not want to "don\'t download"')
                    ep_obj_list = []
                    for ep_num in ep_nums:
                        ep_obj_list.append(show_obj.get_episode(ep_num[0], ep_num[1]))
                    best_season_result.ep_obj_list = ep_obj_list

                    if not best_season_result.url.startswith('magnet'):
                        best_season_result = cache_torrent_file(
                            best_season_result, show_obj=show_obj, orig_thread_name=orig_thread_name)

                    if best_season_result:
                        ep_num = MULTI_EP_RESULT
                        if ep_num in found_results[provider_id]:
                            found_results[provider_id][ep_num].append(best_season_result)
                        else:
                            found_results[provider_id][ep_num] = [best_season_result]

        # go through multi-ep results and see if we really want them or not, get rid of the rest
        multi_result_groups = {}  # type: Dict[AnyStr, Union[List, search_result_type]]
        if MULTI_EP_RESULT in found_results[provider_id]:
            for multi_result in found_results[provider_id][MULTI_EP_RESULT]:

                logger.debug(f'Checking usefulness of multi episode result [{multi_result.name}]')

                if sickgear.USE_FAILED_DOWNLOADS and failed_history.has_failed(multi_result.name, multi_result.size,
                                                                               multi_result.provider.name):
                    logger.log(f'Rejecting previously failed multi episode result [{multi_result.name}]')
                    continue

                group_name = '-'.join(f'{_num}' for _num in sorted(_ep.episode for _ep in multi_result.ep_obj_list))
                multi_result_groups.setdefault(group_name, []).append(multi_result)

            remove_list = []
            for multi_group_name, multi_group_result in multi_result_groups.items():
                best_result = _pick_best_result_helper(multi_group_result, **params)
                if best_result:
                    multi_result_groups[multi_group_name] = best_result
                else:
                    remove_list.append(multi_group_name)
            if remove_list:
                multi_result_groups = {k: v for k, v in multi_result_groups.items() if k not in remove_list}

        for cur_search_result in found_results[provider_id]:  # type: int
            if cur_search_result in (MULTI_EP_RESULT, SEASON_RESULT):
                continue

            if 0 == len(found_results[provider_id][cur_search_result]):
                continue

            best_result = _pick_best_result_helper(results=found_results[provider_id][cur_search_result], **params)

            # if all results were rejected move on to the next episode
            if not best_result:
                continue

            # filter out possible bad torrents from providers
            if 'torrent' == best_result.resultType:
                if not best_result.url.startswith('magnet') and None is not best_result.get_data_func:
                    best_result.url = best_result.get_data_func(best_result.url)
                    best_result.get_data_func = None  # consume only once
                    if not best_result.url:
                        continue
                if best_result.url.startswith('magnet'):
                    if 'blackhole' != sickgear.TORRENT_METHOD:
                        best_result.content = None
                else:
                    best_result = cache_torrent_file(best_result, **params)
                    if not best_result:
                        continue

                    if 'blackhole' == sickgear.TORRENT_METHOD:
                        best_result.content = None

                if None is not best_result.after_get_data_func:
                    best_result.after_get_data_func(best_result)
                    best_result.after_get_data_func = None  # consume only once

            # add result if it's not a duplicate
            found = False
            for i, result in enumerate(final_results):
                for best_result_ep in best_result.ep_obj_list:
                    if best_result_ep in result.ep_obj_list:
                        if best_result.quality > result.quality:
                            final_results.pop(i)
                        else:
                            found = True
            if not found:
                final_results += [best_result]

        # check if we have multi episode results that should be taken
        if len(multi_result_groups):
            found_eps = {_ep: _res.quality for _res in final_results for _ep in _res.ep_obj_list}
            for multi_group_name, multi_group_result in multi_result_groups.items():  # type: AnyStr, search_result_type
                # if a episode result is only available in multi result or is better quality then single
                if (any(_ep not in found_eps for _ep in multi_group_result.ep_obj_list) or
                        any(multi_group_result.quality > found_eps[_ep]
                            for _ep in multi_group_result.ep_obj_list if _ep in found_eps)):
                    final_results = [_res for _res in final_results
                                     if not any(_ep in _res.ep_obj_list for _ep in multi_group_result.ep_obj_list)]
                    final_results += [multi_group_result]

        # check that we got all the episodes we wanted first before doing a match and snatch
        wanted_ep_count = 0
        for wanted_ep in ep_obj_list:
            for result in final_results:
                if wanted_ep in result.ep_obj_list and is_final_result(result):
                    wanted_ep_count += 1

        # make sure we search every provider for results unless we found everything we wanted
        if len(ep_obj_list) == wanted_ep_count:
            break

    if not len(provider_list):
        logger.warning('No NZB/Torrent providers in Media Providers/Options are allowed for active searching')
    elif not search_done:
        logger.error(f'Failed active search of {len(provider_list)}'
                     f' enabled provider{helpers.maybe_plural(provider_list)}. More info in debug log.')
    elif not any(final_results):
        logger.log('No suitable candidates')

    return final_results
