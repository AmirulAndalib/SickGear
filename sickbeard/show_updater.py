# Author: Nic Wolfe <nic@wolfeden.ca>
# URL: http://code.google.com/p/sickbeard/
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
#  GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickGear.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import os
import traceback

import exceptions_helper
from exceptions_helper import ex
# noinspection PyPep8Naming
import encodingKludge as ek

import sickbeard
from . import db, logger, network_timezones, properFinder, ui

# noinspection PyUnreachableCode
if False:
    from sickbeard.tv import TVShow


def clean_ignore_require_words():
    """
    removes duplicate ignore/require words from shows and global lists
    """
    try:
        for s in sickbeard.showList:  # type: TVShow
            # test before set to prevent dirty setter from setting unchanged shows to dirty
            if s.rls_ignore_words - sickbeard.IGNORE_WORDS != s.rls_ignore_words:
                s.rls_ignore_words -= sickbeard.IGNORE_WORDS
                if 0 == len(s.rls_ignore_words):
                    s.rls_ignore_words_regex = False
            if s.rls_require_words - sickbeard.REQUIRE_WORDS != s.rls_require_words:
                s.rls_require_words -= sickbeard.REQUIRE_WORDS
                if 0 == len(s.rls_require_words):
                    s.rls_require_words_regex = False
            if s.rls_global_exclude_ignore & sickbeard.IGNORE_WORDS != s.rls_global_exclude_ignore:
                s.rls_global_exclude_ignore &= sickbeard.IGNORE_WORDS
            if s.rls_global_exclude_require & sickbeard.REQUIRE_WORDS != s.rls_global_exclude_require:
                s.rls_global_exclude_require &= sickbeard.REQUIRE_WORDS
            if s.dirty:
                s.save_to_db()
    except (BaseException, Exception):
        pass


class ShowUpdater(object):
    def __init__(self):
        self.amActive = False

    def run(self):

        self.amActive = True

        try:
            update_datetime = datetime.datetime.now()
            update_date = update_datetime.date()

            # backup db's
            if sickbeard.db.db_supports_backup and 0 < sickbeard.BACKUP_DB_MAX_COUNT:
                logger.log('backing up all db\'s')
                try:
                    sickbeard.db.backup_all_dbs(sickbeard.BACKUP_DB_PATH or
                                                ek.ek(os.path.join, sickbeard.DATA_DIR, 'backup'))
                except (BaseException, Exception):
                    logger.log('backup db error', logger.ERROR)

            # refresh network timezones
            try:
                network_timezones.update_network_dict()
            except (BaseException, Exception):
                logger.log('network timezone update error', logger.ERROR)
                logger.log(traceback.format_exc(), logger.ERROR)

            # refresh webdl types
            try:
                properFinder.load_webdl_types()
            except (BaseException, Exception):
                logger.log('error loading webdl_types', logger.DEBUG)

            # update xem id lists
            try:
                sickbeard.scene_exceptions.get_xem_ids()
            except (BaseException, Exception):
                logger.log('xem id list update error', logger.ERROR)
                logger.log(traceback.format_exc(), logger.ERROR)

            # update scene exceptions
            try:
                sickbeard.scene_exceptions.retrieve_exceptions()
            except (BaseException, Exception):
                logger.log('scene exceptions update error', logger.ERROR)
                logger.log(traceback.format_exc(), logger.ERROR)

            # clear the data of unused providers
            try:
                sickbeard.helpers.clear_unused_providers()
            except (BaseException, Exception):
                logger.log('unused provider cleanup error', logger.ERROR)
                logger.log(traceback.format_exc(), logger.ERROR)

            # cleanup image cache
            try:
                sickbeard.helpers.cleanup_cache()
            except (BaseException, Exception):
                logger.log('image cache cleanup error', logger.ERROR)
                logger.log(traceback.format_exc(), logger.ERROR)

            # check tvinfo cache
            try:
                for i in sickbeard.TVInfoAPI().all_sources:
                    sickbeard.TVInfoAPI(i).setup().check_cache()
            except (BaseException, Exception):
                logger.log('tvinfo cache check error', logger.ERROR)
                logger.log(traceback.format_exc(), logger.ERROR)

            # cleanup tvinfo cache
            try:
                for i in sickbeard.TVInfoAPI().all_sources:
                    sickbeard.TVInfoAPI(i).setup().clean_cache()
            except (BaseException, Exception):
                logger.log('tvinfo cache cleanup error', logger.ERROR)
                logger.log(traceback.format_exc(), logger.ERROR)

            # cleanup ignore and require lists
            try:
                clean_ignore_require_words()
            except Exception:
                logger.log('ignore, require words cleanup error', logger.ERROR)
                logger.log(traceback.format_exc(), logger.ERROR)

            # cleanup manual search history
            sickbeard.search_queue.remove_old_fifo(sickbeard.search_queue.MANUAL_SEARCH_HISTORY)

            # add missing mapped ids
            if not sickbeard.background_mapping_task.is_alive():
                logger.log(u'Updating the TV info mappings')
                import threading
                try:
                    sickbeard.background_mapping_task = threading.Thread(
                        name='MAPPINGSUPDATER', target=sickbeard.indexermapper.load_mapped_ids, kwargs={'update': True})
                    sickbeard.background_mapping_task.start()
                except (BaseException, Exception):
                    logger.log('missing mapped ids update error', logger.ERROR)
                    logger.log(traceback.format_exc(), logger.ERROR)

            logger.log(u'Doing full update on all shows')

            # clean out cache directory, remove everything > 12 hours old
            try:
                sickbeard.helpers.clear_cache()
            except (BaseException, Exception):
                logger.log('cache dir cleanup error', logger.ERROR)
                logger.log(traceback.format_exc(), logger.ERROR)

            # select 10 'Ended' tv_shows updated more than 90 days ago
            # and all shows not updated more then 180 days ago to include in this update
            stale_should_update = []
            stale_update_date = (update_date - datetime.timedelta(days=90)).toordinal()
            stale_update_date_max = (update_date - datetime.timedelta(days=180)).toordinal()

            # last_update_date <= 90 days, sorted ASC because dates are ordinal
            from sickbeard.tv import TVidProdid
            my_db = db.DBConnection()
            # noinspection SqlRedundantOrderingDirection
            mass_sql_result = my_db.mass_action([
                ['SELECT indexer || ? || indexer_id AS tvid_prodid'
                 ' FROM tv_shows'
                 ' WHERE last_update_indexer <= ?'
                 ' AND last_update_indexer >= ?'
                 ' ORDER BY last_update_indexer ASC LIMIT 10;',
                 [TVidProdid.glue, stale_update_date, stale_update_date_max]],
                ['SELECT indexer || ? || indexer_id AS tvid_prodid'
                 ' FROM tv_shows'
                 ' WHERE last_update_indexer < ?;',
                 [TVidProdid.glue, stale_update_date_max]]])

            for sql_result in mass_sql_result:
                for cur_result in sql_result:
                    stale_should_update.append(cur_result['tvid_prodid'])

            # start update process
            show_updates = {}
            for src in sickbeard.TVInfoAPI().search_sources:
                tvinfo_config = sickbeard.TVInfoAPI(src).api_params.copy()
                t = sickbeard.TVInfoAPI(src).setup(**tvinfo_config)
                show_updates.update({src: t.get_updated_shows()})

            pi_list = []
            for cur_show_obj in sickbeard.showList:  # type: sickbeard.tv.TVShow

                try:
                    # if should_update returns True (not 'Ended') or show is selected stale 'Ended' then update,
                    # otherwise just refresh
                    if cur_show_obj.should_update(update_date=update_date,
                                                  last_indexer_change=show_updates.get(cur_show_obj.tvid, {}).
                                                          get(cur_show_obj.prodid)) \
                            or cur_show_obj.tvid_prodid in stale_should_update:
                        cur_queue_item = sickbeard.show_queue_scheduler.action.updateShow(cur_show_obj,
                                                                                          scheduled_update=True)
                    else:
                        logger.log(u'Not updating episodes for show %s because it\'s marked as ended and last/next'
                                   u' episode is not within the grace period.' % cur_show_obj.name, logger.DEBUG)
                        cur_queue_item = sickbeard.show_queue_scheduler.action.refreshShow(cur_show_obj, True, True)

                    pi_list.append(cur_queue_item)

                except (exceptions_helper.CantUpdateException, exceptions_helper.CantRefreshException) as e:
                    logger.log(u'Automatic update failed: ' + ex(e), logger.ERROR)

            if len(pi_list):
                sickbeard.show_queue_scheduler.action.daily_update_running = True

            ui.ProgressIndicators.setIndicator('dailyUpdate', ui.QueueProgressIndicator('Daily Update', pi_list))

            logger.log(u'Added all shows to show queue for full update')

        finally:
            self.amActive = False

    def __del__(self):
        pass
