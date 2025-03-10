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
import io
import os

from . import generic
from .. import logger
import sg_helpers
from ..indexers.indexer_config import TVINFO_IMDB, TVINFO_TVDB
from lib.tvinfo_base import RoleTypes
from lib.tvinfo_base.exceptions import *
import sickgear
import exceptions_helper
from exceptions_helper import ex
from lxml_etree import etree

from _23 import decode_str
from six import string_types

# noinspection PyUnreachableCode
if False:
    from typing import AnyStr, Dict, Optional, Union
    from lib.tvinfo_base import PersonBase


class KODIMetadata(generic.GenericMetadata):
    """
    Metadata generation class for Kodi.

    The following file structure is used:

    show_root/tvshow.nfo                    (show metadata)
    show_root/fanart.jpg                    (fanart)
    show_root/poster.jpg                    (poster)
    show_root/banner.jpg                    (banner)
    show_root/Season ##/filename.ext        (*)
    show_root/Season ##/filename.nfo        (episode metadata)
    show_root/Season ##/filename-thumb.jpg  (episode thumb)
    show_root/season##-poster.jpg           (season posters)
    show_root/season##-banner.jpg           (season banners)
    show_root/season-all-poster.jpg         (season all poster)
    show_root/season-all-banner.jpg         (season all banner)
    """

    def __init__(self,
                 show_metadata=False,  # type: bool
                 episode_metadata=False,  # type: bool
                 use_fanart=False,  # type: bool
                 use_poster=False,  # type: bool
                 use_banner=False,  # type: bool
                 episode_thumbnails=False,  # type: bool
                 season_posters=False,  # type: bool
                 season_banners=False,  # type: bool
                 season_all_poster=False,  # type: bool
                 season_all_banner=False  # type: bool
                 ):

        generic.GenericMetadata.__init__(self,
                                         show_metadata,
                                         episode_metadata,
                                         use_fanart,
                                         use_poster,
                                         use_banner,
                                         episode_thumbnails,
                                         season_posters,
                                         season_banners,
                                         season_all_poster,
                                         season_all_banner)

        self.name = 'Kodi'  # type: AnyStr

        self.poster_name = 'poster.jpg'  # type: AnyStr
        self.season_all_poster_name = 'season-all-poster.jpg'  # type: AnyStr

        # web-ui metadata template
        self.eg_show_metadata = 'tvshow.nfo'  # type: AnyStr
        self.eg_episode_metadata = 'Season##\\<i>filename</i>.nfo'  # type: AnyStr
        self.eg_fanart = 'fanart.jpg'  # type: AnyStr
        self.eg_poster = 'poster.jpg'  # type: AnyStr
        self.eg_banner = 'banner.jpg'  # type: AnyStr
        self.eg_episode_thumbnails = 'Season##\\<i>filename</i>-thumb.jpg'  # type: AnyStr
        self.eg_season_posters = 'season##-poster.jpg'  # type: AnyStr
        self.eg_season_banners = 'season##-banner.jpg'  # type: AnyStr
        self.eg_season_all_poster = 'season-all-poster.jpg'  # type: AnyStr
        self.eg_season_all_banner = 'season-all-banner.jpg'  # type: AnyStr

    def _show_data(self, show_obj):
        # type: (sickgear.tv.TVShow) -> Optional[Union[bool, AnyStr]]
        """
        Creates an elementTree XML structure for a Kodi-style tvshow.nfo and
        returns the resulting data object.

        show_obj: a TVShow instance to create the NFO for
        """

        show_id = show_obj.prodid

        show_lang = show_obj.lang
        tvinfo_config = sickgear.TVInfoAPI(show_obj.tvid).api_params.copy()

        tvinfo_config['actors'] = True

        if show_lang and not 'en' == show_lang:
            tvinfo_config['language'] = show_lang

        if 0 != show_obj.dvdorder:
            tvinfo_config['dvdorder'] = True

        t = sickgear.TVInfoAPI(show_obj.tvid).setup(**tvinfo_config)

        tv_node = etree.Element('tvshow')

        try:
            show_info = t.get_show(show_id, language=show_obj.lang)
        except BaseTVinfoShownotfound as e:
            logger.error(f'Unable to find show with id {show_id} on {sickgear.TVInfoAPI(show_obj.tvid).name},'
                         f' skipping it')
            raise e
        except BaseTVinfoError as e:
            logger.error(f'{sickgear.TVInfoAPI(show_obj.tvid).name} is down, can\'t use its data to add this show')
            raise e

        if not self._valid_show(show_info, show_obj):
            return

        # check for title and id
        if None is getattr(show_info, 'seriesname', None) or None is getattr(show_info, 'id', None):
            logger.error(f'Incomplete info for show with id {show_id} on {sickgear.TVInfoAPI(show_obj.tvid).name},'
                         f' skipping it')
            return False

        title = etree.SubElement(tv_node, 'title')
        if None is not getattr(show_info, 'seriesname', None):
            title.text = '%s' % show_info['seriesname']

        # year = etree.SubElement(tv_node, 'year')
        premiered = etree.SubElement(tv_node, 'premiered')
        premiered_text = self.get_show_year(show_obj, show_info, year_only=False)
        if premiered_text:
            premiered.text = '%s' % premiered_text

        has_id = False
        tvdb_id = None
        for tvid, slug in map(
                lambda _tvid: (_tvid, sickgear.TVInfoAPI(_tvid).config.get('kodi_slug')),
                list(sickgear.TVInfoAPI().all_sources)):
            mid = slug and show_obj.ids[tvid].get('id')
            if mid:
                has_id = True
                kwargs = dict(type=slug)
                if tvid == show_obj.tvid:
                    kwargs.update(dict(default='true'))
                if TVINFO_TVDB == tvid == show_obj.tvid:
                    tvdb_id = str(mid)
                uniqueid = etree.SubElement(tv_node, 'uniqueid', **kwargs)
                uniqueid.text = '%s%s' % (('', 'tt')[TVINFO_IMDB == tvid], mid)
        if not has_id:
            logger.error(f'Incomplete info for show with id {show_id} on {sickgear.TVInfoAPI(show_obj.tvid).name},'
                         f' skipping it')
            return False

        ratings = etree.SubElement(tv_node, 'ratings')
        if None is not getattr(show_info, 'rating', None):
            # todo: name dynamic depending on source
            rating = etree.SubElement(ratings, 'rating', name='thetvdb', max='10')
            rating_value = etree.SubElement(rating, 'value')
            rating_value.text = '%s' % show_info['rating']
            if None is not getattr(show_info, 'siteratingcount', None):
                ratings_votes = etree.SubElement(rating, 'votes')
                ratings_votes.text = '%s' % show_info['siteratingcount']

        plot = etree.SubElement(tv_node, 'plot')
        if None is not getattr(show_info, 'overview', None):
            plot.text = '%s' % show_info['overview']

        if tvdb_id:
            episodeguide = etree.SubElement(tv_node, 'episodeguide')
            episodeguideurl = etree.SubElement(episodeguide, 'url', post='yes', cache='auth.json')
            episodeguideurl.text = sickgear.TVInfoAPI(TVINFO_TVDB).config['epg_url'].replace('{MID}', tvdb_id)

        mpaa = etree.SubElement(tv_node, 'mpaa')
        if None is not getattr(show_info, 'contentrating', None):
            mpaa.text = '%s' % show_info['contentrating']

        genre = etree.SubElement(tv_node, 'genre')
        if None is not getattr(show_info, 'genre', None):
            if isinstance(show_info['genre'], string_types):
                genre.text = ' / '.join([x.strip() for x in show_info['genre'].split('|') if x.strip()])

        studio = etree.SubElement(tv_node, 'studio')
        if None is not getattr(show_info, 'network', None):
            studio.text = '%s' % show_info['network']

        self.add_actor_element(show_info, etree, tv_node)

        # Make it purdy
        sg_helpers.indent_xml(tv_node)

        # output valid xml
        # data = etree.ElementTree(tv_node)
        # output non valid xml that Kodi accepts
        data = decode_str(etree.tostring(tv_node))
        parts = data.split('episodeguide')
        if 3 == len(parts):
            data = 'episodeguide'.join([parts[0], parts[1].replace('&amp;quot;', '&quot;'), parts[2]])

        return data

    def write_show_file(self, show_obj):
        # type: (sickgear.tv.TVShow) -> bool
        """
        This method overrides and handles _show_data as a string
        instead of an ElementTree.
        """
        data = self._show_data(show_obj)

        if not data:
            return False

        nfo_file_path = self.get_show_file_path(show_obj)

        logger.debug(f'Writing Kodi metadata file: {nfo_file_path}')

        data = '<?xml version="1.0" encoding="UTF-8"?>\n%s' % data
        return sg_helpers.write_file(nfo_file_path, data, utf8=True)

    def write_ep_file(self, ep_obj):
        # type: (sickgear.tv.TVEpisode) -> bool
        """
        Generates and writes ep_obj's metadata under the given path with the
        given filename root. Uses the episode's name with the extension in
        _ep_nfo_extension.

        ep_obj: TVEpisode object for which to create the metadata

        file_name_path: The file name to use for this metadata. Note that the extension
                will be automatically added based on _ep_nfo_extension. This should
                include an absolute path.
        """

        data = self._ep_data(ep_obj)

        if not data:
            return False

        nfo_file_path = self.get_episode_file_path(ep_obj)

        logger.debug(f'Writing episode metadata file: {nfo_file_path}')

        return sg_helpers.write_file(nfo_file_path, data, xmltree=True, xml_header=True, utf8=True)

    def _ep_data(self, ep_obj):
        # type: (sickgear.tv.TVEpisode) -> Optional[etree.Element]
        """
        Creates an elementTree XML structure for a Kodi-style episode.nfo and
        returns the resulting data object.
            show_obj: a TVEpisode instance to create the NFO for
        """
        ep_obj_list_to_write = [ep_obj] + ep_obj.related_ep_obj

        show_lang = ep_obj.show_obj.lang

        tvinfo_config = sickgear.TVInfoAPI(ep_obj.show_obj.tvid).api_params.copy()

        tvinfo_config['actors'] = True

        if show_lang and not 'en' == show_lang:
            tvinfo_config['language'] = show_lang

        if 0 != ep_obj.show_obj.dvdorder:
            tvinfo_config['dvdorder'] = True

        try:
            t = sickgear.TVInfoAPI(ep_obj.show_obj.tvid).setup(**tvinfo_config)
            show_info = t.get_show(ep_obj.show_obj.prodid, language=ep_obj.show_obj.lang)
        except BaseTVinfoShownotfound as e:
            raise exceptions_helper.ShowNotFoundException(ex(e))
        except BaseTVinfoError as e:
            logger.error(f'Unable to connect to {sickgear.TVInfoAPI(ep_obj.show_obj.tvid).name}'
                         f' while creating meta files - skipping - {ex(e)}')
            return

        if not self._valid_show(show_info, ep_obj.show_obj):
            return

        if 1 < len(ep_obj_list_to_write):
            root_node = etree.Element('xbmcmultiepisode')
        else:
            root_node = etree.Element('episodedetails')

        # write an NFO containing info for all matching episodes
        for cur_ep_obj in ep_obj_list_to_write:

            try:
                ep_info = show_info[cur_ep_obj.season][cur_ep_obj.episode]
            except (BaseException, Exception):
                logger.log('Unable to find episode %sx%s on %s.. has it been removed? Should I delete from db?' %
                           (cur_ep_obj.season, cur_ep_obj.episode, sickgear.TVInfoAPI(ep_obj.show_obj.tvid).name))
                return None

            if None is getattr(ep_info, 'firstaired', None):
                ep_info['firstaired'] = str(datetime.date.fromordinal(1))

            if None is getattr(ep_info, 'episodename', None):
                logger.debug('Not generating nfo because the episode has no title')
                return None

            logger.debug('Creating metadata for episode %sx%s' % (ep_obj.season, ep_obj.episode))

            if 1 < len(ep_obj_list_to_write):
                ep_node = etree.SubElement(root_node, 'episodedetails')
            else:
                ep_node = root_node

            title = etree.SubElement(ep_node, 'title')
            if None is not cur_ep_obj.name:
                title.text = '%s' % cur_ep_obj.name

            showtitle = etree.SubElement(ep_node, 'showtitle')
            if None is not cur_ep_obj.show_obj.name:
                showtitle.text = '%s' % cur_ep_obj.show_obj.name

            season = etree.SubElement(ep_node, 'season')
            season.text = str(cur_ep_obj.season)

            episodenum = etree.SubElement(ep_node, 'episode')
            episodenum.text = str(cur_ep_obj.episode)

            slug = sickgear.TVInfoAPI(cur_ep_obj.indexer).config.get('kodi_slug')
            if slug:
                uniqueid = etree.SubElement(ep_node, 'uniqueid', type=slug, default='true')
                uniqueid.text = str(cur_ep_obj.epid)

            aired = etree.SubElement(ep_node, 'aired')
            if cur_ep_obj.airdate != datetime.date.fromordinal(1):
                aired.text = str(cur_ep_obj.airdate)
            else:
                aired.text = ''

            plot = etree.SubElement(ep_node, 'plot')
            if None is not cur_ep_obj.description:
                plot.text = '%s' % cur_ep_obj.description

            runtime = etree.SubElement(ep_node, 'runtime')
            if 0 != cur_ep_obj.season:
                if None is not getattr(show_info, 'runtime', None):
                    runtime.text = '%s' % show_info['runtime']

            displayseason = etree.SubElement(ep_node, 'displayseason')
            if None is not getattr(ep_info, 'airsbefore_season', None):
                displayseason_text = ep_info['airsbefore_season']
                if None is not displayseason_text:
                    displayseason.text = '%s' % displayseason_text

            displayepisode = etree.SubElement(ep_node, 'displayepisode')
            if None is not getattr(ep_info, 'airsbefore_episode', None):
                displayepisode_text = ep_info['airsbefore_episode']
                if None is not displayepisode_text:
                    displayepisode.text = '%s' % displayepisode_text

            thumb = etree.SubElement(ep_node, 'thumb')
            thumb_text = getattr(ep_info, 'filename', None)
            if None is not thumb_text:
                thumb.text = '%s' % thumb_text

            watched = etree.SubElement(ep_node, 'watched')
            watched.text = 'false'

            crew = getattr(ep_info, 'crew', None)
            if None is not crew:
                for role_type, sub_el_name in [(RoleTypes.CrewWriter, 'credits'), (RoleTypes.CrewDirector, 'director')]:
                    for credit in (crew[role_type] or []):  # type: PersonBase
                        if credit.name:
                            sub_el = etree.SubElement(ep_node, sub_el_name)
                            sub_el.text = '%s' % credit.name

            # credits_text = getattr(ep_info, 'writer', None)
            # if None is not credits_text and (
            #         credits_list := [_c.strip() for _c in credits_text.split('|') if _c.strip()]):
            #     for credit in credits_list:
            #         credits = etree.SubElement(ep_node, 'credits')
            #         credits.text = '%s' % credit

            # director = etree.SubElement(ep_node, 'director')
            # director_text = getattr(ep_info, 'director', None)
            # if None is not director_text:
            #     director.text = '%s' % director_text

            ratings = etree.SubElement(ep_node, 'ratings')
            if None is not getattr(ep_info, 'rating', None):
                # todo: name dynamic depending on source
                rating = etree.SubElement(ratings, 'rating', name='thetvdb', max='10')
                rating_value = etree.SubElement(rating, 'value')
                rating_value.text = '%s' % ep_info['rating']
                if None is not getattr(show_info, 'siteratingcount', None):
                    ratings_votes = etree.SubElement(rating, 'votes')
                    ratings_votes.text = '%s' % show_info['siteratingcount']

            gueststar_text = getattr(ep_info, 'gueststars', None)
            if isinstance(gueststar_text, string_types):
                for actor in [x.strip() for x in gueststar_text.split('|') if x.strip()]:
                    cur_actor = etree.SubElement(ep_node, 'actor')
                    cur_actor_name = etree.SubElement(cur_actor, 'name')
                    cur_actor_name.text = '%s' % actor

            self.add_actor_element(show_info, etree, ep_node)

        # Make it purdy
        sg_helpers.indent_xml(root_node)

        data = etree.ElementTree(root_node)

        return data

    @staticmethod
    def add_actor_element(show_info, et, node):
        # type: (Dict, etree, etree.Element) -> None
        for actor in getattr(show_info, 'actors', []):
            cur_actor = et.SubElement(node, 'actor')

            cur_actor_name = et.SubElement(cur_actor, 'name')
            cur_actor_name_text = actor['person']['name']
            if cur_actor_name_text:
                cur_actor_name.text = '%s' % cur_actor_name_text

            cur_actor_role = et.SubElement(cur_actor, 'role')
            cur_actor_role_text = actor['character']['name']
            if cur_actor_role_text:
                cur_actor_role.text = '%s' % cur_actor_role_text

            cur_actor_thumb = et.SubElement(cur_actor, 'thumb')
            cur_actor_thumb_text = actor['character']['image']
            if None is not cur_actor_thumb_text:
                cur_actor_thumb.text = '%s' % cur_actor_thumb_text


def set_nfo_uid_updated(*args, **kwargs):
    from .. import db
    if not db.DBConnection().has_flag('kodi_nfo_uid'):
        db.DBConnection().set_flag('kodi_nfo_uid')
    sickgear.show_queue_scheduler.action.remove_event(sickgear.show_queue.DAILY_SHOW_UPDATE_FINISHED_EVENT,
                                                       set_nfo_uid_updated)


def remove_default_attr(*args, **kwargs):
    try:
        from .. import db
        msg = 'Updating Kodi Nfo'
        sickgear.classes.loading_msg.set_msg_progress(msg, '0%')

        kodi = metadata_class()
        num_shows = len(sickgear.showList)
        for n, cur_show_obj in enumerate(sickgear.showList):
            try:
                changed = False
                with cur_show_obj.lock:
                    # call for progress with value
                    sickgear.classes.loading_msg.set_msg_progress(msg, '{:6.2f}%'.format(float(n)/num_shows * 100))

                    try:
                        nfo_path = kodi.get_show_file_path(cur_show_obj)
                    except(BaseException, Exception):
                        nfo_path = None
                    if nfo_path:
                        # show
                        try:
                            if os.path.isfile(nfo_path):
                                with io.open(nfo_path, 'r', encoding='utf8') as xml_file_obj:
                                    xmltree = etree.ElementTree(file=xml_file_obj)

                                # remove default="" attributes
                                default = False
                                ratings = xmltree.find('ratings')
                                r = None is not ratings and ratings.findall('rating') or []
                                for element in r:
                                    if not element.attrib.get('default'):
                                        changed |= None is not element.attrib.pop('default', None)
                                    else:
                                        default = True
                                if len(r) and not default:
                                    ratings.find('rating').attrib['default'] = 'true'
                                    changed = True

                                # remove default="" attributes
                                default = False
                                uniques = xmltree.findall('uniqueid')
                                for element in uniques:
                                    if not element.attrib.get('default'):
                                        changed |= None is not element.attrib.pop('default', None)
                                    else:
                                        default = True
                                if len(uniques) and not default:
                                    xmltree.find('uniqueid').attrib['default'] = 'true'
                                    changed = True

                                # remove redundant duplicate tags
                                root = xmltree.getroot()
                                for element in xmltree.findall('premiered')[1:]:
                                    root.remove(element)
                                    changed = True

                                if changed:
                                    sg_helpers.indent_xml(root)
                                    sg_helpers.write_file(nfo_path, xmltree, xmltree=True, xml_header=True, utf8=True)
                        except(BaseException, Exception):
                            pass

                        # episodes
                        episodes = cur_show_obj.get_all_episodes(has_location=True)
                        for cur_ep_obj in episodes:
                            try:
                                changed = False
                                nfo_path = kodi.get_episode_file_path(cur_ep_obj)
                                if nfo_path and os.path.isfile(nfo_path):
                                    with io.open(nfo_path, 'r', encoding='utf8') as xml_file_obj:
                                        xmltree = etree.ElementTree(file=xml_file_obj)

                                    # remove default="" attributes
                                    default = False
                                    ratings = xmltree.find('ratings')
                                    r = None is not ratings and ratings.findall('rating') or []
                                    for element in r:
                                        if not element.attrib.get('default'):
                                            changed |= None is not element.attrib.pop('default', None)
                                        else:
                                            default = True
                                    if len(r) and not default:
                                        ratings.find('rating').attrib['default'] = 'true'
                                        changed = True

                                if changed:
                                    sg_helpers.indent_xml(xmltree.getroot())
                                    sg_helpers.write_file(nfo_path, xmltree, xmltree=True, xml_header=True, utf8=True)

                            except(BaseException, Exception):
                                pass
            except(BaseException, Exception):
                pass

        db.DBConnection().set_flag('kodi_nfo_default_removed')
        sickgear.classes.loading_msg.set_msg_progress(msg, '100%')

    except(BaseException, Exception):
        pass


def rebuild_nfo(*args, **kwargs):
    """
    General meta .nfo rebuilder no matter the source of the .nfo

    case 1, rebuild missing uniqueids and set default="true" to correct uid type
    """
    try:
        from .. import db
        msg = 'Rebuilding Kodi Nfo'
        sickgear.classes.loading_msg.set_msg_progress(msg, '0%')

        kodi = metadata_class()
        num_shows = len(sickgear.showList)
        for n, cur_show_obj in enumerate(sickgear.showList):
            try:
                with cur_show_obj.lock:
                    # call for progress with value
                    sickgear.classes.loading_msg.set_msg_progress(msg, '{:6.2f}%'.format(float(n)/num_shows * 100))

                    try:
                        nfo_path = kodi.get_show_file_path(cur_show_obj)
                        if nfo_path and os.path.isfile(nfo_path):
                            with io.open(nfo_path, 'r', encoding='utf8') as xml_file_obj:
                                xmltree = etree.ElementTree(file=xml_file_obj)

                            # check xml keys exist to validate file as type Kodi episode or tvshow .nfo
                            if ((('show' in xmltree.getroot().tag) and bool(xmltree.findall('title')))
                                    or ((bool(xmltree.findall('showtitle')) or bool(xmltree.findall('title')))
                                        and bool(xmltree.findall('season')))) \
                                    and sg_helpers.remove_file_perm(nfo_path):
                                kodi.write_show_file(cur_show_obj)
                    except(BaseException, Exception):
                        pass

            except(BaseException, Exception):
                pass

        db.DBConnection().set_flag('kodi_nfo_rebuild_uniqueid')
        sickgear.classes.loading_msg.set_msg_progress(msg, '100%')

    except(BaseException, Exception):
        pass


# present a standard "interface" from the module
metadata_class = KODIMetadata
